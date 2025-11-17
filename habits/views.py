from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import Habit, HabitLog
from .serializers import HabitLogSerializer
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .forms import HabitForm
from .repository import HabitRepository
from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required


class HabitLogCreateView(generics.CreateAPIView):
    queryset = HabitLog.objects.all()
    serializer_class = HabitLogSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        habit = serializer.validated_data['habit']
        if habit.user != self.request.user:
            raise PermissionDenied("You do not have permission to log this habit.")
        serializer.save()


class HabitListView(LoginRequiredMixin, ListView):
    model = Habit
    template_name = 'habits/habit_list.html'
    context_object_name = 'habits'

    def get_queryset(self):
        repo = HabitRepository()
        return repo.get_all_habits_for_user(self.request.user).order_by('-created_at')


class HabitCreateView(LoginRequiredMixin, CreateView):
    model = Habit
    form_class = HabitForm
    template_name = 'habits/habit_form.html'
    success_url = reverse_lazy('habits:habit-list')

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class HabitDeleteView(LoginRequiredMixin, DeleteView):
    model = Habit
    template_name = 'habits/habit_confirm_delete.html'
    success_url = reverse_lazy('habits:habit-list')

    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)


@login_required
def complete_habit_view(request, pk):
    habit = get_object_or_404(Habit, pk=pk, user=request.user)
    habit.complete_habit()
    return redirect('habits:habit-list')
