"""Tests covering Programs utilities."""
import json
from unittest import skipUnless

from django.conf import settings
from django.core.cache import cache
from django.test import TestCase
import httpretty
import mock
from nose.plugins.attrib import attr
from edx_oauth2_provider.tests.factories import ClientFactory
from provider.constants import CONFIDENTIAL

from certificates.models import CertificateStatuses, GeneratedCertificate  # pylint: disable=import-error
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory
from openedx.core.djangoapps.credentials.tests.mixins import CredentialsApiConfigMixin
from openedx.core.djangoapps.programs.models import ProgramsApiConfig
from openedx.core.djangoapps.programs.tests import factories
from openedx.core.djangoapps.programs.tests.mixins import ProgramsApiConfigMixin, ProgramsDataMixin
from openedx.core.djangoapps.programs.utils import (
    get_programs,
    get_programs_for_dashboard,
    get_programs_for_credentials,
    get_display_category,
    get_completed_courses,
    ProgramProgressMeter,
)
from student.tests.factories import UserFactory, CourseEnrollmentFactory


@skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
@attr('shard_2')
class TestProgramRetrieval(ProgramsApiConfigMixin, ProgramsDataMixin,
                           CredentialsApiConfigMixin, TestCase):
    """Tests covering the retrieval of programs from the Programs service."""
    def setUp(self):
        super(TestProgramRetrieval, self).setUp()

        ClientFactory(name=ProgramsApiConfig.OAUTH2_CLIENT_NAME, client_type=CONFIDENTIAL)
        self.user = UserFactory()

        cache.clear()

    @httpretty.activate
    def test_get_programs(self):
        """Verify programs data can be retrieved."""
        self.create_programs_config()
        self.mock_programs_api()

        actual = get_programs(self.user)
        self.assertEqual(
            actual,
            self.PROGRAMS_API_RESPONSE['results']
        )

        # Verify the API was actually hit (not the cache).
        self.assertEqual(len(httpretty.httpretty.latest_requests), 1)

    @httpretty.activate
    def test_get_programs_caching(self):
        """Verify that when enabled, the cache is used for non-staff users."""
        self.create_programs_config(cache_ttl=1)
        self.mock_programs_api()

        # Warm up the cache.
        get_programs(self.user)

        # Hit the cache.
        get_programs(self.user)

        # Verify only one request was made.
        self.assertEqual(len(httpretty.httpretty.latest_requests), 1)

        staff_user = UserFactory(is_staff=True)

        # Hit the Programs API twice.
        for _ in range(2):
            get_programs(staff_user)

        # Verify that three requests have been made (one for student, two for staff).
        self.assertEqual(len(httpretty.httpretty.latest_requests), 3)

    def test_get_programs_programs_disabled(self):
        """Verify behavior when programs is disabled."""
        self.create_programs_config(enabled=False)

        actual = get_programs(self.user)
        self.assertEqual(actual, [])

    @mock.patch('edx_rest_api_client.client.EdxRestApiClient.__init__')
    def test_get_programs_client_initialization_failure(self, mock_init):
        """Verify behavior when API client fails to initialize."""
        self.create_programs_config()
        mock_init.side_effect = Exception

        actual = get_programs(self.user)
        self.assertEqual(actual, [])
        self.assertTrue(mock_init.called)

    @httpretty.activate
    def test_get_programs_data_retrieval_failure(self):
        """Verify behavior when data can't be retrieved from Programs."""
        self.create_programs_config()
        self.mock_programs_api(status_code=500)

        actual = get_programs(self.user)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_programs_for_dashboard(self):
        """Verify programs data can be retrieved and parsed correctly."""
        self.create_programs_config()
        self.mock_programs_api()

        actual = get_programs_for_dashboard(self.user, self.COURSE_KEYS)
        expected = {}
        for program in self.PROGRAMS_API_RESPONSE['results']:
            for course_code in program['course_codes']:
                for run in course_code['run_modes']:
                    course_key = run['course_key']
                    expected.setdefault(course_key, []).append(program)

        self.assertEqual(actual, expected)

    def test_get_programs_for_dashboard_dashboard_display_disabled(self):
        """Verify behavior when student dashboard display is disabled."""
        self.create_programs_config(enable_student_dashboard=False)

        actual = get_programs_for_dashboard(self.user, self.COURSE_KEYS)
        self.assertEqual(actual, {})

    @httpretty.activate
    def test_get_programs_for_dashboard_no_data(self):
        """Verify behavior when no programs data is found for the user."""
        self.create_programs_config()
        self.mock_programs_api(data={'results': []})

        actual = get_programs_for_dashboard(self.user, self.COURSE_KEYS)
        self.assertEqual(actual, {})

    @httpretty.activate
    def test_get_programs_for_dashboard_invalid_data(self):
        """Verify behavior when the Programs API returns invalid data and parsing fails."""
        self.create_programs_config()
        invalid_program = {'invalid_key': 'invalid_data'}
        self.mock_programs_api(data={'results': [invalid_program]})

        actual = get_programs_for_dashboard(self.user, self.COURSE_KEYS)
        self.assertEqual(actual, {})

    @httpretty.activate
    def test_get_program_for_certificates(self):
        """Verify programs data can be retrieved and parsed correctly for certificates."""
        self.create_programs_config()
        self.mock_programs_api()

        actual = get_programs_for_credentials(self.user, self.PROGRAMS_CREDENTIALS_DATA)
        expected = self.PROGRAMS_API_RESPONSE['results'][:2]
        expected[0]['credential_url'] = self.PROGRAMS_CREDENTIALS_DATA[0]['certificate_url']
        expected[1]['credential_url'] = self.PROGRAMS_CREDENTIALS_DATA[1]['certificate_url']

        self.assertEqual(len(actual), 2)
        self.assertEqual(actual, expected)

    @httpretty.activate
    def test_get_program_for_certificates_no_data(self):
        """Verify behavior when no programs data is found for the user."""
        self.create_programs_config()
        self.create_credentials_config()
        self.mock_programs_api(data={'results': []})

        actual = get_programs_for_credentials(self.user, self.PROGRAMS_CREDENTIALS_DATA)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_program_for_certificates_id_not_exist(self):
        """Verify behavior when no program with the given program_id in
        credentials exists.
        """
        self.create_programs_config()
        self.create_credentials_config()
        self.mock_programs_api()
        credential_data = [
            {
                "id": 1,
                "username": "test",
                "credential": {
                    "credential_id": 1,
                    "program_id": 100
                },
                "status": "awarded",
                "credential_url": "www.example.com"
            }
        ]
        actual = get_programs_for_credentials(self.user, credential_data)
        self.assertEqual(actual, [])

    @httpretty.activate
    def test_get_display_category_success(self):
        self.create_programs_config()
        self.mock_programs_api()
        actual_programs = get_programs(self.user)
        for program in actual_programs:
            expected = 'XSeries'
            self.assertEqual(expected, get_display_category(program))

    def test_get_display_category_none(self):
        self.assertEqual('', get_display_category(None))
        self.assertEqual('', get_display_category({"id": "test"}))


@skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
class GetCompletedCoursesTestCase(TestCase):
    """
    Test the get_completed_courses function
    """

    def make_cert_result(self, **kwargs):
        """
        Helper to create dummy results from the certificates API
        """
        result = {
            'username': 'dummy-username',
            'course_key': 'dummy-course',
            'type': 'dummy-type',
            'status': 'dummy-status',
            'download_url': 'http://www.example.com/cert.pdf',
            'grade': '0.98',
            'created': '2015-07-31T00:00:00Z',
            'modified': '2015-07-31T00:00:00Z',
        }
        result.update(**kwargs)
        return result

    @mock.patch('openedx.core.djangoapps.programs.utils.get_certificates_for_user')
    def test_get_completed_courses(self, mock_get_certs_for_user):
        """
        Ensure the function correctly calls to and handles results from the
        certificates API
        """
        student = UserFactory(username='test-username')
        mock_get_certs_for_user.return_value = [
            self.make_cert_result(status='downloadable', type='verified', course_key='downloadable-course'),
            self.make_cert_result(status='generating', type='professional', course_key='generating-course'),
            self.make_cert_result(status='unknown', type='honor', course_key='unknown-course'),
        ]

        result = get_completed_courses(student)
        self.assertEqual(mock_get_certs_for_user.call_args[0], (student.username, ))
        self.assertEqual(result, [
            {'course_id': 'downloadable-course', 'mode': 'verified'},
            {'course_id': 'generating-course', 'mode': 'professional'},
        ])


@skipUnless(settings.ROOT_URLCONF == 'lms.urls', 'Test only valid in lms')
@attr('shard_2')
class TestProgramProgressMeter(ProgramsApiConfigMixin, TestCase):
    """Tests of the program progress utility class."""
    def setUp(self):
        super(TestProgramProgressMeter, self).setUp()

        self.user = UserFactory()
        self.create_programs_config()

        ClientFactory(name=ProgramsApiConfig.OAUTH2_CLIENT_NAME, client_type=CONFIDENTIAL)

    def _mock_programs_api(self, data, status_code=200):
        """Helper for mocking out Programs API URLs."""
        self.assertTrue(httpretty.is_enabled(), msg='httpretty must be enabled to mock Programs API calls.')

        url = ProgramsApiConfig.current().internal_api_url.strip('/') + '/programs/'
        body = json.dumps({'results': data})

        httpretty.register_uri(httpretty.GET, url, body=body, content_type='application/json', status=status_code)

    def _create_enrollments(self, *course_ids):
        """Variadic helper used to create course enrollments."""
        return [CourseEnrollmentFactory(user=self.user, course_id=c) for c in course_ids]

    def _grant_certificate(self, course_id,
                           mode=GeneratedCertificate.MODES.verified, status=CertificateStatuses.downloadable):
        """Helper used to grant certificates."""
        return GeneratedCertificateFactory(
            user=self.user,
            course_id=course_id,
            mode=mode,
            status=status,
        )

    def _assert_progress(self, meter, *progresses):
        """Variadic helper used to verify progress calculations."""
        self.assertEqual(meter.progress, list(progresses))

    @httpretty.activate
    def test_no_enrollments(self):
        """Verify behavior when programs exist, but no relevant enrollments do."""
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[factories.RunMode()]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        meter = ProgramProgressMeter(self.user, [])

        self.assertEqual(meter.engaged_programs, [])
        self._assert_progress(meter)

    @httpretty.activate
    def test_no_programs(self):
        """Verify behavior when enrollments exist, but no matching programs do."""
        self._mock_programs_api([])

        enrollments = self._create_enrollments('org/course/run')
        meter = ProgramProgressMeter(self.user, enrollments)

        self.assertEqual(meter.engaged_programs, [])
        self._assert_progress(meter)

    @httpretty.activate
    def test_single_program_engagement(self):
        """
        Verify that correct program is returned when the user has a single enrollment
        appearing in one program.
        """
        course_id = 'org/course/run'
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[factories.RunMode()]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        enrollments = self._create_enrollments(course_id)
        meter = ProgramProgressMeter(self.user, enrollments)

        program = data[0]
        self.assertEqual(meter.engaged_programs, [program])
        self._assert_progress(
            meter,
            factories.Progress(id=program['id'], in_progress=1)
        )

    @httpretty.activate
    def test_mutiple_program_engagement(self):
        """
        Verify that correct programs are returned in the correct order when the user
        has multiple enrollments.
        """
        first_course_id, second_course_id = 'org/first-course/run', 'org/second-course/run'
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=first_course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=second_course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[factories.RunMode()]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        enrollments = self._create_enrollments(second_course_id, first_course_id)
        meter = ProgramProgressMeter(self.user, enrollments)

        programs = data[:2]
        self.assertEqual(meter.engaged_programs, programs)
        self._assert_progress(
            meter,
            factories.Progress(id=programs[0]['id'], in_progress=1),
            factories.Progress(id=programs[1]['id'], in_progress=1)
        )

    @httpretty.activate
    def test_shared_enrollment_engagement(self):
        """
        Verify that correct programs are returned when the user has a single enrollment
        appearing in multiple programs.
        """
        shared_course_id, solo_course_id = 'org/shared-course/run', 'org/solo-course/run'
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=shared_course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=shared_course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=solo_course_id),
                    ]),
                ]
            ),
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[factories.RunMode()]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        # Enrollment for the shared course ID created last (most recently).
        enrollments = self._create_enrollments(solo_course_id, shared_course_id)
        meter = ProgramProgressMeter(self.user, enrollments)

        programs = data[:3]
        self.assertEqual(meter.engaged_programs, programs)
        self._assert_progress(
            meter,
            factories.Progress(id=programs[0]['id'], in_progress=1),
            factories.Progress(id=programs[1]['id'], in_progress=1),
            factories.Progress(id=programs[2]['id'], in_progress=1)
        )

    @httpretty.activate
    def test_simulate_progress(self):
        """Simulate the entirety of a user's progress through a program."""
        first_course_id, second_course_id = 'org/first-course/run', 'org/second-course/run'
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=first_course_id),
                    ]),
                    factories.CourseCode(run_modes=[
                        factories.RunMode(course_key=second_course_id),
                    ]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        # No enrollments, no program engaged.
        meter = ProgramProgressMeter(self.user, [])
        self._assert_progress(meter)

        # One enrollment, program engaged.
        enrollments = self._create_enrollments(first_course_id)
        meter = ProgramProgressMeter(self.user, enrollments)
        program_id = data[0]['id']
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, in_progress=1, not_started=1)
        )

        # Two enrollments, program in progress.
        enrollments += self._create_enrollments(second_course_id)
        meter = ProgramProgressMeter(self.user, enrollments)
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, in_progress=2)
        )

        # One valid certificate earned, one course code complete.
        self._grant_certificate(first_course_id)
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, completed=1, in_progress=1)
        )

        # Invalid certificate earned, still one course code to complete.
        second_certificate = self._grant_certificate(second_course_id, mode=GeneratedCertificate.MODES.honor)
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, completed=1, in_progress=1)
        )

        # Certificate still invalid, still one course code to complete.
        second_certificate.mode = GeneratedCertificate.MODES.verified
        second_certificate.status = CertificateStatuses.audit_passing
        second_certificate.save()  # pylint: disable=no-member
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, completed=1, in_progress=1)
        )

        # Second valid certificate obtained, all course codes complete.
        second_certificate.status = CertificateStatuses.downloadable
        second_certificate.save()  # pylint: disable=no-member
        self._assert_progress(
            meter,
            factories.Progress(id=program_id, completed=2)
        )

    @httpretty.activate
    def test_nonstandard_run_mode_completion(self):
        """
        A valid run mode isn't necessarily verified. Verify that the program can
        still be completed when this is the case.
        """
        course_id = 'org/course/run'
        data = [
            factories.Program(
                organizations=[factories.Organization()],
                course_codes=[
                    factories.CourseCode(run_modes=[
                        factories.RunMode(
                            course_key=course_id,
                            mode_slug=GeneratedCertificate.MODES.honor
                        ),
                    ]),
                ]
            ),
        ]
        self._mock_programs_api(data)

        enrollments = self._create_enrollments(course_id)
        meter = ProgramProgressMeter(self.user, enrollments)

        self._grant_certificate(course_id, mode=GeneratedCertificate.MODES.honor)

        self._assert_progress(
            meter,
            factories.Progress(id=data[0]['id'], completed=1)
        )
