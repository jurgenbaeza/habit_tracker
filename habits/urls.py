from django.urls import path
from .views import HabitLogCreateView, HabitListView, HabitCreateView, complete_habit_view

app_name = 'habits'

urlpatterns = [
    path('api/log/', HabitLogCreateView.as_view(), name='habit-log-create'),
    path('', HabitListView.as_view(), name='habit-list'),
    path('create/', HabitCreateView.as_view(), name='habit-create'),
    path('complete/<int:pk>/', complete_habit_view, name='complete-habit'),
]
