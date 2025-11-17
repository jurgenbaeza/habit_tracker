from django.urls import path
from .views import RegisterView, ProtectedView, SignUpView
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = 'users'

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'), # This is for API registration
    path('signup/', SignUpView.as_view(), name='signup'), # This is for UI registration
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('login/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('protected/', ProtectedView.as_view(), name='protected'),
]
