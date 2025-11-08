from .models import Habit
from django.contrib.auth.models import User

class HabitRepository:
    def get_all_habits_for_user(self, user: User):
        return Habit.objects.filter(user=user)

    def create_habit(self, user: User, name: str, description: str, duration: str):
        return Habit.objects.create(user=user, name=name, description=description, duration=duration)

    def get_habit_by_id_for_user(self, user: User, habit_id: int):
        return Habit.objects.get(pk=habit_id, user=user)
