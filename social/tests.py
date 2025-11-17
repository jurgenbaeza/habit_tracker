import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status # Added import for status
from rest_framework.test import APIClient

from .models import Follow
from habits.models import Habit, Tag

# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


# --- Fixtures ---
@pytest.fixture
def test_user():
    """Fixture to create a standard user."""
    return User.objects.create_user(username='testuser', password='testpassword')

@pytest.fixture
def other_user():
    """Fixture to create a second user for interaction tests."""
    return User.objects.create_user(username='otheruser', password='otherpassword')

@pytest.fixture
def another_user():
    """Fixture to create a third user for additional test cases."""
    return User.objects.create_user(username='anotheruser', password='anotherpassword')

@pytest.fixture(scope="session") # Changed scope to session
def health_tag(django_db_setup, django_db_blocker): # Added django_db_setup, django_db_blocker
    """Fixture to create a 'Health' tag, scoped to the session."""
    with django_db_blocker.unblock(): # Use django_db_blocker to allow DB access in session-scoped fixture
        return Tag.objects.get_or_create(name='Health')[0]

@pytest.fixture
def habit_for_other_user(other_user, health_tag):
    """Fixture to create a habit associated with the other_user."""
    habit = Habit.objects.create(user=other_user, name='Run Daily', duration='daily')
    habit.tags.add(health_tag)
    return habit

@pytest.fixture
def followed_by_test_user(test_user, other_user):
    """Fixture to create a Follow instance where test_user follows other_user."""
    return Follow.objects.create(follower=test_user, following=other_user)


# --- Unit Tests for Models ---

class TestFollowModel:
    """Unit tests for the Follow model."""

    def test_follow_str_representation(self, test_user, other_user):
        """Test the __str__ method of the Follow model."""
        follow_instance = Follow.objects.create(follower=test_user, following=other_user)
        assert str(follow_instance) == f'{test_user} follows {other_user}'

    def test_unique_follow_constraint(self, test_user, other_user):
        """Test that a user cannot follow another user more than once."""
        Follow.objects.create(follower=test_user, following=other_user)
        with pytest.raises(Exception): # Expecting an IntegrityError
            Follow.objects.create(follower=test_user, following=other_user)


# --- Integration Tests for Views ---

# --- Integration Tests for Views ---



class TestSocialViews:

    """Integration tests for the social app's views."""



    def test_user_list_view_displays_other_users(self, client, test_user, other_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:user_list')



        # Act

        response = client.get(url)



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert other_user in response.context['users']

        assert test_user not in response.context['users'] # Should not list self



    def test_user_profile_view_displays_profile_and_habits(self, client, test_user, other_user, habit_for_other_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:user_profile', kwargs={'username': other_user.username})



        # Act

        response = client.get(url)



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert response.context['profile_user'] == other_user

        assert habit_for_other_user in response.context['habits']

        assert response.context['is_following'] is False # test_user is not following other_user yet



    def test_follow_toggle_follows_user(self, client, test_user, other_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:follow_toggle', kwargs={'username': other_user.username})

        assert not Follow.objects.filter(follower=test_user, following=other_user).exists()



        # Act

        response = client.post(url)



        # Assert

        assert response.status_code == status.HTTP_302_FOUND # Redirect to profile

        assert Follow.objects.filter(follower=test_user, following=other_user).exists()



    def test_follow_toggle_unfollows_user(self, client, test_user, other_user, followed_by_test_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:follow_toggle', kwargs={'username': other_user.username})

        assert Follow.objects.filter(follower=test_user, following=other_user).exists()



        # Act

        response = client.post(url)



        # Assert

        assert response.status_code == status.HTTP_302_FOUND # Redirect to profile

        assert not Follow.objects.filter(follower=test_user, following=other_user).exists()



    def test_followers_list_displays_followers(self, client, test_user, other_user, followed_by_test_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:followers_list', kwargs={'username': other_user.username})



        # Act

        response = client.get(url)



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert response.context['profile_user'] == other_user

        assert len(response.context['follow_list']) == 1

        assert response.context['follow_list'][0].follower == test_user



    def test_following_list_displays_followed_users(self, client, test_user, other_user, followed_by_test_user):

        # Arrange

        client.force_login(test_user)

        url = reverse('social:following_list', kwargs={'username': test_user.username})



        # Act

        response = client.get(url)



        # Assert

        assert response.status_code == status.HTTP_200_OK

        assert response.context['profile_user'] == test_user

        assert len(response.context['follow_list']) == 1

        assert response.context['follow_list'][0].following == other_user
