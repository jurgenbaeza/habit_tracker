from django.urls import path
from .views import UserProfileView, FollowToggle, FollowListView, UserListView

app_name = 'social'

urlpatterns = [
    path('', UserListView.as_view(), name='user_list'),
    path('<str:username>/', UserProfileView.as_view(), name='user_profile'),
    path('<str:username>/follow/', FollowToggle.as_view(), name='follow_toggle'),
    path('<str:username>/followers/', FollowListView.as_view(), {'list_type': 'followers'}, name='followers_list'),
    path('<str:username>/following/', FollowListView.as_view(), {'list_type': 'following'}, name='following_list'),
]
