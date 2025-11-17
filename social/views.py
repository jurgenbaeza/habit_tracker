from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import DetailView, ListView
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from .models import Follow
from habits.models import Habit

class UserListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'social/user_list.html'
    context_object_name = 'users'

    def get_queryset(self):
        return User.objects.exclude(username=self.request.user.username)

class UserProfileView(DetailView):
    model = User
    template_name = 'social/user_profile.html'
    context_object_name = 'profile_user'
    slug_field = 'username'
    slug_url_kwarg = 'username'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        profile_user = self.get_object()
        
        context['habits'] = Habit.objects.filter(user=profile_user)
        
        if user.is_authenticated:
            context['is_following'] = Follow.objects.filter(follower=user, following=profile_user).exists()
        else:
            context['is_following'] = False
            
        return context

class FollowToggle(LoginRequiredMixin, View):
    def post(self, request, username):
        follower = request.user
        following = get_object_or_404(User, username=username)

        follow, created = Follow.objects.get_or_create(follower=follower, following=following)

        if not created:
            follow.delete()

        return redirect('social:user_profile', username=username)

class FollowListView(ListView):
    model = Follow
    template_name = 'social/follow_list.html'
    context_object_name = 'follow_list'

    def get_queryset(self):
        profile_user = get_object_or_404(User, username=self.kwargs['username'])
        list_type = self.kwargs.get('list_type')

        if list_type == 'followers':
            return Follow.objects.filter(following=profile_user)
        elif list_type == 'following':
            return Follow.objects.filter(follower=profile_user)
        return Follow.objects.none()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['profile_user'] = get_object_or_404(User, username=self.kwargs['username'])
        context['list_type'] = self.kwargs.get('list_type')
        return context
