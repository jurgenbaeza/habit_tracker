import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


# --- Fixtures ---
@pytest.fixture
def api_client():
    """Fixture for DRF's APIClient."""
    return APIClient()

@pytest.fixture
def test_user_data():
    """Fixture for new user data."""
    return {
        'username': 'newuser',
        'password': 'newpassword123',
        'email': 'new@example.com'
    }

@pytest.fixture
def existing_user():
    """Fixture to create a user that already exists for login tests."""
    return User.objects.create_user(username='testuser', password='testpassword')


# --- Tests ---

class TestUserAPIs:

    """Integration tests for the user-related API endpoints."""



    def test_user_registration_api(self, api_client, test_user_data):

        """

        Tests that a new user can be created via the registration API endpoint.

        """

        # Arrange

        url = reverse('users:register')



        # Act

        response = api_client.post(url, test_user_data, format='json')



        # Assert

        assert response.status_code == status.HTTP_201_CREATED

        assert User.objects.count() == 1

        assert User.objects.get(username='newuser').email == 'new@example.com'



    def test_user_login_api_and_get_token(self, api_client, existing_user):

        """

        Tests that an existing user can log in and receive an access and refresh token.

        """

        # Arrange

        url = reverse('users:token_obtain_pair') # from rest_framework_simplejwt

        data = {

            'username': 'testuser',

            'password': 'testpassword'

        }



        # Act

        response = api_client.post(url, data, format='json')



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert 'access' in response.data

        assert 'refresh' in response.data



    def test_access_protected_endpoint_with_valid_token(self, api_client, existing_user):

        """

        Tests that a protected endpoint can be accessed with a valid JWT token.

        """

        # Arrange: First, get the token

        login_url = reverse('users:token_obtain_pair')

        login_data = {'username': 'testuser', 'password': 'testpassword'}

        login_response = api_client.post(login_url, login_data, format='json')

        token = login_response.data['access']



        # Act: Then, access the protected endpoint with the token

        protected_url = reverse('users:protected')

        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        response = api_client.get(protected_url)



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert response.data['message'] == 'This is a protected endpoint for authenticated users only.'



    def test_access_protected_endpoint_without_token(self, api_client):

        """

        Tests that a protected endpoint cannot be accessed without a token.

        """

        # Arrange

        url = reverse('users:protected')



        # Act

        response = api_client.get(url)



        # Assert

        assert response.status_code == status.HTTP_401_UNAUTHORIZED



    def test_access_protected_endpoint_with_invalid_token(self, api_client):

        """

        Tests that a protected endpoint cannot be accessed with an invalid token.

        """

        # Arrange

        url = reverse('users:protected')

        api_client.credentials(HTTP_AUTHORIZATION='Bearer invalidtoken')



        # Act

        response = api_client.get(url)



        # Assert

        assert response.status_code == status.HTTP_401_UNAUTHORIZED