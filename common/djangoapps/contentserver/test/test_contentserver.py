"""
Tests for StaticContentServer
"""
import copy

import datetime
import ddt
import logging
import unittest
from uuid import uuid4

from django.conf import settings
from django.test import RequestFactory
from django.test.client import Client
from django.test.utils import override_settings
from mock import patch

from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.xml_importer import import_course_from_xml

from contentserver.middleware import parse_range_header, HTTP_DATE_FORMAT, StaticContentServer
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, AdminFactory

log = logging.getLogger(__name__)

TEST_DATA_CONTENTSTORE = copy.deepcopy(settings.CONTENTSTORE)
TEST_DATA_CONTENTSTORE['DOC_STORE_CONFIG']['db'] = 'test_xcontent_%s' % uuid4().hex

TEST_DATA_DIR = settings.COMMON_TEST_DATA_ROOT


@ddt.ddt
@override_settings(CONTENTSTORE=TEST_DATA_CONTENTSTORE)
class ContentStoreToyCourseTest(SharedModuleStoreTestCase):
    """
    Tests that use the toy course.
    """

    @classmethod
    def setUpClass(cls):
        super(ContentStoreToyCourseTest, cls).setUpClass()

        cls.contentstore = contentstore()
        cls.modulestore = modulestore()

        cls.course_key = cls.modulestore.make_course_key('edX', 'toy', '2012_Fall')

        import_course_from_xml(
            cls.modulestore, 1, TEST_DATA_DIR, ['toy'],
            static_content_store=cls.contentstore, verbose=True
        )

        # A locked asset
        cls.locked_asset = cls.course_key.make_asset_key('asset', 'sample_static.txt')
        cls.url_locked = unicode(cls.locked_asset)
        cls.contentstore.set_attr(cls.locked_asset, 'locked', True)

        # An unlocked asset
        cls.unlocked_asset = cls.course_key.make_asset_key('asset', 'another_static.txt')
        cls.url_unlocked = unicode(cls.unlocked_asset)
        cls.length_unlocked = cls.contentstore.get_attr(cls.unlocked_asset, 'length')

    def setUp(self):
        """
        Create user and login.
        """
        super(ContentStoreToyCourseTest, self).setUp()
        self.staff_usr = AdminFactory.create()
        self.non_staff_usr = UserFactory.create()

        self.client = Client()

    def test_unlocked_asset(self):
        """
        Test that unlocked assets are being served.
        """
        self.client.logout()
        resp = self.client.get(self.url_unlocked)
        self.assertEqual(resp.status_code, 200)

    def test_locked_asset_not_logged_in(self):
        """
        Test that locked assets behave appropriately in case the user is not
        logged in.
        """
        self.client.logout()
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 403)

    def test_locked_asset_not_registered(self):
        """
        Test that locked assets behave appropriately in case user is logged in
        in but not registered for the course.
        """
        self.client.login(username=self.non_staff_usr, password='test')
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 403)

    def test_locked_asset_registered(self):
        """
        Test that locked assets behave appropriately in case user is logged in
        and registered for the course.
        """
        CourseEnrollment.enroll(self.non_staff_usr, self.course_key)
        self.assertTrue(CourseEnrollment.is_enrolled(self.non_staff_usr, self.course_key))

        self.client.login(username=self.non_staff_usr, password='test')
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 200)

    def test_locked_asset_staff(self):
        """
        Test that locked assets behave appropriately in case user is staff.
        """
        self.client.login(username=self.staff_usr, password='test')
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 200)

    def test_range_request_full_file(self):
        """
        Test that a range request from byte 0 to last,
        outputs partial content status code and valid Content-Range and Content-Length.
        """
        resp = self.client.get(self.url_unlocked, HTTP_RANGE='bytes=0-')

        self.assertEqual(resp.status_code, 206)  # HTTP_206_PARTIAL_CONTENT
        self.assertEqual(
            resp['Content-Range'],
            'bytes {first}-{last}/{length}'.format(
                first=0, last=self.length_unlocked - 1,
                length=self.length_unlocked
            )
        )
        self.assertEqual(resp['Content-Length'], str(self.length_unlocked))

    def test_range_request_partial_file(self):
        """
        Test that a range request for a partial file,
        outputs partial content status code and valid Content-Range and Content-Length.
        first_byte and last_byte are chosen to be simple but non trivial values.
        """
        first_byte = self.length_unlocked / 4
        last_byte = self.length_unlocked / 2
        resp = self.client.get(self.url_unlocked, HTTP_RANGE='bytes={first}-{last}'.format(
            first=first_byte, last=last_byte))

        self.assertEqual(resp.status_code, 206)  # HTTP_206_PARTIAL_CONTENT
        self.assertEqual(resp['Content-Range'], 'bytes {first}-{last}/{length}'.format(
            first=first_byte, last=last_byte, length=self.length_unlocked))
        self.assertEqual(resp['Content-Length'], str(last_byte - first_byte + 1))

    def test_range_request_multiple_ranges(self):
        """
        Test that multiple ranges in request outputs the full content.
        """
        first_byte = self.length_unlocked / 4
        last_byte = self.length_unlocked / 2
        resp = self.client.get(self.url_unlocked, HTTP_RANGE='bytes={first}-{last}, -100'.format(
            first=first_byte, last=last_byte))

        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Content-Range', resp)
        self.assertEqual(resp['Content-Length'], str(self.length_unlocked))

    @ddt.data(
        'bytes 0-',
        'bits=0-',
        'bytes=0',
        'bytes=one-',
    )
    def test_syntax_errors_in_range(self, header_value):
        """
        Test that syntactically invalid Range values result in a 200 OK full content response.
        """
        resp = self.client.get(self.url_unlocked, HTTP_RANGE=header_value)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Content-Range', resp)

    def test_range_request_malformed_invalid_range(self):
        """
        Test that a range request with malformed Range (first_byte > last_byte) outputs
        416 Requested Range Not Satisfiable.
        """
        resp = self.client.get(self.url_unlocked, HTTP_RANGE='bytes={first}-{last}'.format(
            first=(self.length_unlocked / 2), last=(self.length_unlocked / 4)))
        self.assertEqual(resp.status_code, 416)

    def test_range_request_malformed_out_of_bounds(self):
        """
        Test that a range request with malformed Range (first_byte, last_byte == totalLength, offset by 1 error)
        outputs 416 Requested Range Not Satisfiable.
        """
        resp = self.client.get(self.url_unlocked, HTTP_RANGE='bytes={first}-{last}'.format(
            first=(self.length_unlocked), last=(self.length_unlocked)))
        self.assertEqual(resp.status_code, 416)

    def test_vary_header_sent(self):
        """
        Tests that we're properly setting the Vary header to ensure browser requests don't get
        cached in a way that breaks XHR requests to the same asset.
        """
        resp = self.client.get(self.url_unlocked)
        self.assertEqual(resp.status_code, 200)
        self.assertEquals('Origin', resp['Vary'])

    @patch('contentserver.models.CourseAssetCacheTtlConfig.get_cache_ttl')
    def test_cache_headers_with_ttl_unlocked(self, mock_get_cache_ttl):
        """
        Tests that when a cache TTL is set, an unlocked asset will be sent back with
        the correct cache control/expires headers.
        """
        mock_get_cache_ttl.return_value = 10

        resp = self.client.get(self.url_unlocked)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Expires', resp)
        self.assertEquals('public, max-age=10, s-maxage=10', resp['Cache-Control'])

    @patch('contentserver.models.CourseAssetCacheTtlConfig.get_cache_ttl')
    def test_cache_headers_with_ttl_locked(self, mock_get_cache_ttl):
        """
        Tests that when a cache TTL is set, a locked asset will be sent back without
        any cache control/expires headers.
        """
        mock_get_cache_ttl.return_value = 10

        CourseEnrollment.enroll(self.non_staff_usr, self.course_key)
        self.assertTrue(CourseEnrollment.is_enrolled(self.non_staff_usr, self.course_key))

        self.client.login(username=self.non_staff_usr, password='test')
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Expires', resp)
        self.assertEquals('private, no-cache, no-store', resp['Cache-Control'])

    @patch('contentserver.models.CourseAssetCacheTtlConfig.get_cache_ttl')
    def test_cache_headers_without_ttl_unlocked(self, mock_get_cache_ttl):
        """
        Tests that when a cache TTL is not set, an unlocked asset will be sent back without
        any cache control/expires headers.
        """
        mock_get_cache_ttl.return_value = 0

        resp = self.client.get(self.url_unlocked)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Expires', resp)
        self.assertNotIn('Cache-Control', resp)

    @patch('contentserver.models.CourseAssetCacheTtlConfig.get_cache_ttl')
    def test_cache_headers_without_ttl_locked(self, mock_get_cache_ttl):
        """
        Tests that when a cache TTL is not set, a locked asset will be sent back with a
        cache-control header that indicates this asset should not be cached.
        """
        mock_get_cache_ttl.return_value = 0

        CourseEnrollment.enroll(self.non_staff_usr, self.course_key)
        self.assertTrue(CourseEnrollment.is_enrolled(self.non_staff_usr, self.course_key))

        self.client.login(username=self.non_staff_usr, password='test')
        resp = self.client.get(self.url_locked)
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Expires', resp)
        self.assertEquals('private, no-cache, no-store', resp['Cache-Control'])

    def test_get_expiration_value(self):
        start_dt = datetime.datetime.strptime("Thu, 01 Dec 1983 20:00:00 GMT", HTTP_DATE_FORMAT)
        near_expire_dt = StaticContentServer.get_expiration_value(start_dt, 55)
        self.assertEqual("Thu, 01 Dec 1983 20:00:55 GMT", near_expire_dt)

    @patch('contentserver.models.CdnUserAgentsConfig.get_cdn_user_agents')
    def test_cache_is_cdn_with_normal_request(self, mock_get_cdn_user_agents):
        """
        Tests that when a normal request is made -- i.e. from an end user with their
        browser -- that we don't classify the request as coming from a CDN.
        """
        mock_get_cdn_user_agents.return_value = 'Amazon CloudFront'

        request_factory = RequestFactory()
        browser_request = request_factory.get('/fake', HTTP_USER_AGENT='Chrome 1234')

        is_from_cdn = StaticContentServer.is_cdn_request(browser_request)
        self.assertEqual(is_from_cdn, False)

    @patch('contentserver.models.CdnUserAgentsConfig.get_cdn_user_agents')
    def test_cache_is_cdn_with_cdn_request(self, mock_get_cdn_user_agents):
        """
        Tests that when a CDN request is made -- i.e. from an edge node back to the
        origin -- that we classify the request as coming from a CDN.
        """
        mock_get_cdn_user_agents.return_value = 'Amazon CloudFront'

        request_factory = RequestFactory()
        browser_request = request_factory.get('/fake', HTTP_USER_AGENT='Amazon CloudFront')

        is_from_cdn = StaticContentServer.is_cdn_request(browser_request)
        self.assertEqual(is_from_cdn, True)

    @patch('contentserver.models.CdnUserAgentsConfig.get_cdn_user_agents')
    def test_cache_is_cdn_with_cdn_request_multiple_user_agents(self, mock_get_cdn_user_agents):
        """
        Tests that when a CDN request is made -- i.e. from an edge node back to the
        origin -- that we classify the request as coming from a CDN when multiple UAs
        are configured.
        """
        mock_get_cdn_user_agents.return_value = 'Amazon CloudFront\nAkamai GHost'

        request_factory = RequestFactory()
        browser_request = request_factory.get('/fake', HTTP_USER_AGENT='Amazon CloudFront')

        is_from_cdn = StaticContentServer.is_cdn_request(browser_request)
        self.assertEqual(is_from_cdn, True)


@ddt.ddt
class ParseRangeHeaderTestCase(unittest.TestCase):
    """
    Tests for the parse_range_header function.
    """

    def setUp(self):
        super(ParseRangeHeaderTestCase, self).setUp()
        self.content_length = 10000

    def test_bytes_unit(self):
        unit, __ = parse_range_header('bytes=100-', self.content_length)
        self.assertEqual(unit, 'bytes')

    @ddt.data(
        ('bytes=100-', 1, [(100, 9999)]),
        ('bytes=1000-', 1, [(1000, 9999)]),
        ('bytes=100-199, 200-', 2, [(100, 199), (200, 9999)]),
        ('bytes=100-199, 200-499', 2, [(100, 199), (200, 499)]),
        ('bytes=-100', 1, [(9900, 9999)]),
        ('bytes=-100, -200', 2, [(9900, 9999), (9800, 9999)])
    )
    @ddt.unpack
    def test_valid_syntax(self, header_value, excepted_ranges_length, expected_ranges):
        __, ranges = parse_range_header(header_value, self.content_length)
        self.assertEqual(len(ranges), excepted_ranges_length)
        self.assertEqual(ranges, expected_ranges)

    @ddt.data(
        ('bytes=one-20', ValueError, 'invalid literal for int()'),
        ('bytes=-one', ValueError, 'invalid literal for int()'),
        ('bytes=-', ValueError, 'invalid literal for int()'),
        ('bytes=--', ValueError, 'invalid literal for int()'),
        ('bytes', ValueError, 'Invalid syntax'),
        ('bytes=', ValueError, 'Invalid syntax'),
        ('bytes=0', ValueError, 'Invalid syntax'),
        ('bytes=0-10,0', ValueError, 'Invalid syntax'),
        ('bytes=0=', ValueError, 'too many values to unpack'),
    )
    @ddt.unpack
    def test_invalid_syntax(self, header_value, exception_class, exception_message_regex):
        self.assertRaisesRegexp(
            exception_class, exception_message_regex, parse_range_header, header_value, self.content_length
        )
