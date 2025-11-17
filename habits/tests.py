import pytest
from datetime import timedelta
from django.utils import timezone

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Habit, HabitLog, Tag
from .forms import HabitForm

# Mark all tests in this file as needing database access
pytestmark = pytest.mark.django_db


# --- Fixtures ---
@pytest.fixture
def test_user():
    """Fixture to create a standard user."""
    return User.objects.create_user(username='testuser', password='testpassword')

@pytest.fixture
def another_user():
    """Fixture to create a second user for permission tests."""
    return User.objects.create_user(username='otheruser', password='otherpassword')

@pytest.fixture(scope="session")
def health_tag(django_db_setup, django_db_blocker):
    """Fixture to create a 'Health' tag, scoped to the session."""
    with django_db_blocker.unblock():
        return Tag.objects.get_or_create(name='Health')[0]

@pytest.fixture(scope="session")
def fitness_tag(django_db_setup, django_db_blocker):
    """Fixture to create a 'Fitness' tag, scoped to the session."""
    with django_db_blocker.unblock():
        return Tag.objects.get_or_create(name='Fitness')[0]

@pytest.fixture
def habit_for_user(test_user, health_tag):
    """Fixture to create a habit associated with the test_user."""
    habit = Habit.objects.create(user=test_user, name='Read a book', duration='daily')
    habit.tags.add(health_tag)
    return habit


# --- Unit Tests ---

class TestHabitModel:
    """Unit tests for the Habit model methods."""

    def test_is_completed_today_returns_true_if_log_exists(self, habit_for_user):
        # Arrange
        HabitLog.objects.create(habit=habit_for_user)

        # Act
        result = habit_for_user.is_completed_today()

        # Assert
        assert result is True

    def test_is_completed_today_returns_false_if_no_log_exists(self, habit_for_user):
        # Arrange (no log created)

        # Act
        result = habit_for_user.is_completed_today()

        # Assert
        assert result is False

    def test_complete_habit_creates_log_if_not_completed(self, habit_for_user):
        # Arrange
        assert habit_for_user.is_completed_today() is False

        # Act
        habit_for_user.complete_habit()

        # Assert
        assert habit_for_user.is_completed_today() is True
        assert HabitLog.objects.filter(habit=habit_for_user).count() == 1

    def test_complete_habit_does_not_create_duplicate_log(self, habit_for_user):
        # Arrange
        habit_for_user.complete_habit() # First log
        assert HabitLog.objects.filter(habit=habit_for_user).count() == 1

        # Act
        habit_for_user.complete_habit() # Try to log again

        # Assert
        assert HabitLog.objects.filter(habit=habit_for_user).count() == 1 # Should still be 1

    def test_get_current_streak_is_zero_if_not_completed_today(self, habit_for_user):
        # Arrange (no log for today)
        log = HabitLog(habit=habit_for_user)
        log.completed_at = timezone.now() - timedelta(days=1)
        log.save()

        # Act
        streak = habit_for_user.get_current_streak()

        # Assert
        assert streak == 0

    def test_get_current_streak_is_one_if_only_completed_today(self, habit_for_user):
        # Arrange
        habit_for_user.complete_habit()

        # Act
        streak = habit_for_user.get_current_streak()

        # Assert
        assert streak == 1

    def test_get_current_streak_counts_consecutive_days(self, habit_for_user):
        # Arrange
        today = timezone.now()
        for i in range(5): # Logs for today and the past 4 days
            log = HabitLog(habit=habit_for_user)
            log.completed_at = today - timedelta(days=i)
            log.save()

        # Act
        streak = habit_for_user.get_current_streak()

        # Assert
        assert streak == 5

    def test_get_current_streak_stops_at_break_in_consecutive_days(self, habit_for_user):
        # Arrange
        today = timezone.now()
        log1 = HabitLog(habit=habit_for_user)
        log1.completed_at = today
        log1.save()
        log2 = HabitLog(habit=habit_for_user)
        log2.completed_at = today - timedelta(days=1)
        log2.save()
        log3 = HabitLog(habit=habit_for_user)
        log3.completed_at = today - timedelta(days=3) # Break at day 2
        log3.save()

        # Act
        streak = habit_for_user.get_current_streak()

        # Assert
        assert streak == 2 # Today and yesterday


class TestHabitForm:
    """Unit tests for the HabitForm."""

    def test_habit_form_is_valid_with_all_data(self, health_tag, fitness_tag):
        # Arrange
        data = {
            'name': 'Exercise Daily',
            'description': 'Go to the gym.',
            'duration': 'daily',
            'tags': [health_tag.id, fitness_tag.id]
        }
        form = HabitForm(data=data)

        # Act & Assert
        assert form.is_valid()

    def test_habit_form_is_invalid_without_name(self, health_tag):
        # Arrange
        data = {'duration': 'daily', 'tags': [health_tag.id]}
        form = HabitForm(data=data)

        # Act & Assert
        assert not form.is_valid()
        assert 'name' in form.errors

    def test_habit_form_is_valid_without_tags(self):
        # Arrange
        data = {'name': 'Read a book', 'duration': 'daily'}
        form = HabitForm(data=data)

        # Act & Assert
        assert form.is_valid()


# --- Integration Tests ---

@pytest.fixture
def api_client():
    """Fixture for DRF's APIClient."""
    return APIClient()

class TestHabitAPIs:
    """Integration tests for the API endpoints related to habits."""

    def test_create_habit_log_api_endpoint(self, api_client, test_user, habit_for_user):
        # Arrange
        api_client.force_authenticate(user=test_user)
        url = reverse('habits:habit-log-create')
        data = {'habit': habit_for_user.id}

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_201_CREATED
        assert HabitLog.objects.filter(habit=habit_for_user).count() == 1

    def test_unauthenticated_user_cannot_create_habit_log_api(self, api_client, habit_for_user):
        # Arrange
        url = reverse('habits:habit-log-create')
        data = {'habit': habit_for_user.id}

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_cannot_log_habit_for_another_user_api(self, api_client, test_user, another_user):
        # Arrange
        api_client.force_authenticate(user=test_user)
        other_habit = Habit.objects.create(user=another_user, name='Other User Habit')
        url = reverse('habits:habit-log-create')
        data = {'habit': other_habit.id}

        # Act
        response = api_client.post(url, data, format='json')

        # Assert
        assert response.status_code == status.HTTP_403_FORBIDDEN


class TestHabitUI:
    """Integration tests for the user-facing UI related to habits."""

    def test_habit_list_view_displays_user_habits(self, client, test_user, habit_for_user):
        # Arrange
        client.force_login(test_user)
        url = reverse('habits:habit-list')

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert habit_for_user.name in response.content.decode()
        assert 'Health' in response.content.decode() # Check for tag name

    def test_can_create_habit_via_ui(self, client, test_user, health_tag):
        # Arrange
        client.force_login(test_user)
        url = reverse('habits:habit-create')
        data = {
            'name': 'A Brand New Habit',
            'description': 'Testing UI creation.',
            'duration': 'weekly',
            'tags': [health_tag.id]
        }

        # Act
        response = client.post(url, data, follow=True)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert Habit.objects.filter(name='A Brand New Habit', user=test_user).exists()
        assert 'A Brand New Habit' in response.content.decode()

    def test_can_complete_habit_via_ui(self, client, test_user, habit_for_user):
        # Arrange
        client.force_login(test_user)
        url = reverse('habits:complete-habit', kwargs={'pk': habit_for_user.pk})

        # Act
        response = client.post(url, follow=True)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        habit_for_user.refresh_from_db()
        assert habit_for_user.is_completed_today() is True
        assert 'Logged!' in response.content.decode()

    def test_can_delete_habit_via_ui(self, client, test_user, habit_for_user):
        # Arrange
        client.force_login(test_user)
        url = reverse('habits:habit-delete', kwargs={'pk': habit_for_user.pk})

        # Act
        response = client.post(url, follow=True)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert not Habit.objects.filter(pk=habit_for_user.pk).exists()
        assert habit_for_user.name not in response.content.decode()
