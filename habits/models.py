from django.db import models
from django.contrib.auth.models import User
from abc import ABCMeta, abstractmethod
from datetime import date, timedelta
from django.db.models.base import ModelBase

# Custom metaclass to combine ModelBase and ABCMeta
class CombinedMeta(ModelBase, ABCMeta):
    pass

class AbstractHabit(models.Model, metaclass=CombinedMeta):
    @abstractmethod
    def complete_habit(self, notes=None):
        pass

    @abstractmethod
    def get_current_streak(self):
        pass

    @abstractmethod
    def is_completed_today(self):
        pass

    class Meta:
        abstract = True

class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Habit(AbstractHabit):
    DURATION_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    duration = models.CharField(max_length=10, choices=DURATION_CHOICES, default='daily')
    tags = models.ManyToManyField(Tag, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def complete_habit(self, notes=None):
        """Creates a HabitLog entry for this habit for the current day."""
        if not self.is_completed_today():
            HabitLog.objects.create(habit=self, notes=notes)

    def is_completed_today(self):
        """Checks if the habit has been completed today."""
        return self.habitlog_set.filter(completed_at__date=date.today()).exists()

    def get_current_streak(self):
        """Calculates the current streak of consecutive days the habit was completed."""
        today = date.today()
        
        streak = 0
        current_date = today
        # We check from today backwards
        while self.habitlog_set.filter(completed_at__date=current_date).exists():
            streak += 1
            current_date -= timedelta(days=1)
        
        # If no log today, the streak is 0.
        if not self.is_completed_today():
            return 0
            
        return streak

class HabitLog(models.Model):
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE)
    notes = models.TextField(blank=True, null=True)
    completed_at = models.DateTimeField(auto_now_add=True)
