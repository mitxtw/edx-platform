""" Tests for OAuth 2.0 client credentials support. """
import json

from django.core.urlresolvers import reverse
from django.test import TestCase
from oauth2_provider.models import Application, AccessToken
from student.tests.factories import UserFactory

from . import mixins
from .constants import DUMMY_REDIRECT_URL
from ..adapters import DOTAdapter


class ClientCredentialsTest(mixins.AccessTokenMixin, TestCase):
    """ Tests validating the client credentials grant behavior. """

    def setUp(self):
        super(ClientCredentialsTest, self).setUp()

        self.user = UserFactory()
        self.application = DOTAdapter().create_confidential_client(
            name='test dot application',
            user=self.user,
            authorization_grant_type=Application.GRANT_CLIENT_CREDENTIALS,
            redirect_uri=DUMMY_REDIRECT_URL,
            client_id='dot-app-client-id',
        )

    def test_access_token(self):
        """ Verify the client credentials grant can be used to obtain an access token linked to a user. """
        scopes = ('read', 'write', 'email')
        data = {
            'grant_type': 'client_credentials',
            'client_id': self.application.client_id,
            'client_secret': self.application.client_secret,
            'scope': ' '.join(scopes),
        }

        response = self.client.post(reverse('access_token'), data)
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        access_token = content['access_token']
        payload = self.assert_valid_jwt_access_token(access_token, self.user, scopes)
        expected = AccessToken.objects.filter(application=self.application, user=self.user).first().token
        self.assertEqual(payload['jti'], expected)
        self.assertEqual(content['scope'], data['scope'])
