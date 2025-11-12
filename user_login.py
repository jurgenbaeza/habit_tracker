# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator, EmailValidator
from django.core.exceptions import ValidationError
import uuid
import re

class User(AbstractUser):
    """Extended user model for the habit tracker app"""
    user_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    email = models.EmailField(unique=True, db_index=True, validators=[EmailValidator()])
    email_verified = models.BooleanField(default=False)
    verification_token = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    registration_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.IntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    def clean(self):
        super().clean()
        # Normalize email to lowercase
        if self.email:
            self.email = self.email.lower().strip()
        
        # Validate username format (alphanumeric and underscores only)
        if self.username:
            self.username = self.username.lower().strip()
            if not re.match(r'^[a-zA-Z0-9_]+

class Habit(models.Model):
    """Model for user habits"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    habit_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    target_count = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    color = models.CharField(max_length=7, default='#007AFF')  # Hex color
    icon = models.CharField(max_length=50, blank=True)  # SF Symbol name for iOS
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"

class HabitLog(models.Model):
    """Model for tracking habit completions"""
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='logs')
    date = models.DateField()
    completed_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['habit', 'date']
    
    def __str__(self):
        return f"{self.habit.name} - {self.date}"

# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Q
from .models import User, Habit, HabitLog

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('user_id', 'username', 'email', 'password', 'first_name', 'last_name')
        read_only_fields = ('user_id',)
    
    def validate_email(self, value):
        """Normalize and validate email uniqueness"""
        normalized_email = value.lower().strip()
        
        # Check for existing email (case-insensitive)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        
        # Check for common email variations (optional - can be stricter)
        # This prevents tricks like user+1@gmail.com, user+2@gmail.com
        base_email = normalized_email.split('+')[0] if '+' in normalized_email else normalized_email
        if '@gmail.com' in normalized_email or '@googlemail.com' in normalized_email:
            # Gmail ignores dots in email addresses
            local_part = base_email.split('@')[0].replace('.', '')
            domain = base_email.split('@')[1]
            canonical_gmail = f"{local_part}@{domain}"
            
            if User.objects.filter(
                Q(email__icontains=canonical_gmail.split('@')[0]) & 
                Q(email__icontains='gmail.com') | Q(email__icontains='googlemail.com')
            ).exists():
                raise serializers.ValidationError("An account with a similar email may already exist.")
        
        return normalized_email
    
    def validate_username(self, value):
        """Validate username uniqueness (case-insensitive)"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value.lower()
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        # Ensure email is stored in lowercase
        validated_data['email'] = validated_data['email'].lower()
        validated_data['username'] = validated_data['username'].lower()
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            if user:
                if user.is_active:
                    data['user'] = user
                else:
                    raise serializers.ValidationError('User account is disabled.')
            else:
                raise serializers.ValidationError('Unable to login with provided credentials.')
        else:
            raise serializers.ValidationError('Must include "email" and "password".')
        
        return data

class HabitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = '__all__'
        read_only_fields = ('habit_id', 'user', 'created_at', 'updated_at')

class HabitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = '__all__'
        read_only_fields = ('log_id', 'created_at')

# views.py
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import login, logout
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib
from .models import User, Habit, HabitLog
from .serializers import UserSerializer, LoginSerializer, HabitSerializer, HabitLogSerializer

class RegistrationThrottle(AnonRateThrottle):
    """Custom throttle for registration endpoint"""
    rate = '5/hour'  # Max 5 registration attempts per hour per IP

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    """Register a new user with duplicate prevention"""
    # Get client IP for rate limiting and tracking
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or \
                request.META.get('REMOTE_ADDR', '')
    
    # Check for rapid registration attempts from same IP
    cache_key = f"register_ip_{client_ip}"
    recent_attempts = cache.get(cache_key, 0)
    
    if recent_attempts >= 3:
        return Response({
            'error': 'Too many registration attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Device fingerprinting (optional - requires frontend support)
    device_fingerprint = request.data.get('device_fingerprint', '')
    if device_fingerprint:
        fingerprint_key = f"register_device_{device_fingerprint}"
        if cache.get(fingerprint_key):
            return Response({
                'error': 'A registration was recently attempted from this device.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    with transaction.atomic():
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            # Additional duplicate check before creation
            email = serializer.validated_data.get('email').lower()
            username = serializer.validated_data.get('username').lower()
            
            if User.objects.filter(email__iexact=email).exists():
                return Response({
                    'error': 'An account with this email already exists.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects.filter(username__iexact=username).exists():
                return Response({
                    'error': 'This username is already taken.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check for recently deleted accounts (soft delete pattern)
            # This prevents immediate re-registration of deleted accounts
            recently_deleted_key = f"deleted_email_{hashlib.md5(email.encode()).hexdigest()}"
            if cache.get(recently_deleted_key):
                return Response({
                    'error': 'This email was recently associated with a deleted account. Please wait 24 hours.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            
            # Update rate limiting cache
            cache.set(cache_key, recent_attempts + 1, 3600)  # Reset after 1 hour
            if device_fingerprint:
                cache.set(fingerprint_key, True, 300)  # 5 minute cooldown per device
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login user and return token"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user and delete token"""
    try:
        request.user.auth_token.delete()
    except:
        pass
    logout(request)
    return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)

class HabitListCreateView(generics.ListCreateAPIView):
    """List all habits for a user or create a new one"""
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class HabitDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a specific habit"""
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'habit_id'
    
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)

# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/auth/register/', views.register, name='register'),
    path('api/auth/login/', views.login_view, name='login'),
    path('api/auth/logout/', views.logout_view, name='logout'),
    path('api/habits/', views.HabitListCreateView.as_view(), name='habit-list-create'),
    path('api/habits/<uuid:habit_id>/', views.HabitDetailView.as_view(), name='habit-detail'),
]

# settings.py additions
"""
Add these to your Django settings.py:

INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_ratelimit',  # pip install django-ratelimit
    'your_app_name',
]

MIDDLEWARE = [
    ...
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django_ratelimit.middleware.RatelimitMiddleware',  # Rate limiting
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
        'register': '5/hour',  # Custom rate for registration
    }
}

# Cache configuration (for rate limiting and duplicate prevention)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
        # Or use database cache if Redis not available:
        # 'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        # 'LOCATION': 'cache_table',
    }
}

# Email verification settings
EMAIL_VERIFICATION_REQUIRED = True
EMAIL_VERIFICATION_TIMEOUT_HOURS = 24

# Security settings
ACCOUNT_LOCKOUT_ATTEMPTS = 5
ACCOUNT_LOCKOUT_DURATION_MINUTES = 30

# CORS settings for iOS app
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# For development only - be more restrictive in production
CORS_ALLOW_ALL_ORIGINS = True

AUTH_USER_MODEL = 'your_app_name.User'

# Additional security settings
SECURE_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
"""

# utils.py - Additional utility functions for duplicate prevention
import hashlib
import secrets
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

def generate_verification_token():
    """Generate a secure random verification token"""
    return secrets.token_urlsafe(32)

def send_verification_email(user):
    """Send email verification link to user"""
    token = generate_verification_token()
    user.verification_token = token
    user.save()
    
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    
    send_mail(
        'Verify your Habit Tracker account',
        f'Please click the link to verify your email: {verification_url}',
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )

def check_suspicious_pattern(email, username, ip_address):
    """
    Check for suspicious registration patterns that might indicate bot or spam accounts
    """
    from .models import User
    
    # Check for multiple accounts from same IP in short time
    recent_cutoff = timezone.now() - timedelta(hours=1)
    same_ip_count = User.objects.filter(
        registration_ip=ip_address,
        created_at__gte=recent_cutoff
    ).count()
    
    if same_ip_count >= 3:
        return True, "Multiple registrations from same IP address"
    
    # Check for sequential usernames (bot pattern)
    if username and any(char.isdigit() for char in username):
        base_username = ''.join([c for c in username if not c.isdigit()])
        if base_username and User.objects.filter(username__startswith=base_username).count() > 5:
            return True, "Suspicious username pattern detected"
    
    # Check for disposable email domains
    disposable_domains = [
        'tempmail.com', 'throwaway.email', '10minutemail.com',
        'guerrillamail.com', 'mailinator.com', 'trashmail.com'
    ]
    
    email_domain = email.split('@')[1].lower()
    if email_domain in disposable_domains:
        return True, "Disposable email addresses are not allowed"
    
    return False, None

def normalize_email(email):
    """
    Normalize email to prevent duplicate accounts with email variations
    """
    email = email.lower().strip()
    local, domain = email.split('@')
    
    # Handle Gmail aliases (dots and plus signs)
    if domain in ['gmail.com', 'googlemail.com']:
        # Remove dots from local part
        local = local.replace('.', '')
        # Remove everything after + sign
        if '+' in local:
            local = local.split('+')[0]
        domain = 'gmail.com'  # Normalize googlemail to gmail
    
    # Handle Outlook/Hotmail aliases
    elif domain in ['outlook.com', 'hotmail.com', 'live.com']:
        if '+' in local:
            local = local.split('+')[0]
    
    return f"{local}@{domain}", self.username):
                raise ValidationError('Username can only contain letters, numbers, and underscores.')
            if len(self.username) < 3:
                raise ValidationError('Username must be at least 3 characters long.')
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
        ]

class Habit(models.Model):
    """Model for user habits"""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    habit_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='habits')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='daily')
    target_count = models.IntegerField(default=1, validators=[MinValueValidator(1)])
    color = models.CharField(max_length=7, default='#007AFF')  # Hex color
    icon = models.CharField(max_length=50, blank=True)  # SF Symbol name for iOS
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"

class HabitLog(models.Model):
    """Model for tracking habit completions"""
    log_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    habit = models.ForeignKey(Habit, on_delete=models.CASCADE, related_name='logs')
    date = models.DateField()
    completed_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        unique_together = ['habit', 'date']
    
    def __str__(self):
        return f"{self.habit.name} - {self.date}"

# serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from django.db.models import Q
from .models import User, Habit, HabitLog

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    email = serializers.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ('user_id', 'username', 'email', 'password', 'first_name', 'last_name')
        read_only_fields = ('user_id',)
    
    def validate_email(self, value):
        """Normalize and validate email uniqueness"""
        normalized_email = value.lower().strip()
        
        # Check for existing email (case-insensitive)
        if User.objects.filter(email__iexact=normalized_email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        
        # Check for common email variations (optional - can be stricter)
        # This prevents tricks like user+1@gmail.com, user+2@gmail.com
        base_email = normalized_email.split('+')[0] if '+' in normalized_email else normalized_email
        if '@gmail.com' in normalized_email or '@googlemail.com' in normalized_email:
            # Gmail ignores dots in email addresses
            local_part = base_email.split('@')[0].replace('.', '')
            domain = base_email.split('@')[1]
            canonical_gmail = f"{local_part}@{domain}"
            
            if User.objects.filter(
                Q(email__icontains=canonical_gmail.split('@')[0]) & 
                Q(email__icontains='gmail.com') | Q(email__icontains='googlemail.com')
            ).exists():
                raise serializers.ValidationError("An account with a similar email may already exist.")
        
        return normalized_email
    
    def validate_username(self, value):
        """Validate username uniqueness (case-insensitive)"""
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value.lower()
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        # Ensure email is stored in lowercase
        validated_data['email'] = validated_data['email'].lower()
        validated_data['username'] = validated_data['username'].lower()
        
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            if user:
                if user.is_active:
                    data['user'] = user
                else:
                    raise serializers.ValidationError('User account is disabled.')
            else:
                raise serializers.ValidationError('Unable to login with provided credentials.')
        else:
            raise serializers.ValidationError('Must include "email" and "password".')
        
        return data

class HabitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habit
        fields = '__all__'
        read_only_fields = ('habit_id', 'user', 'created_at', 'updated_at')

class HabitLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = HabitLog
        fields = '__all__'
        read_only_fields = ('log_id', 'created_at')

# views.py
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework.throttling import AnonRateThrottle
from django.contrib.auth import login, logout
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import hashlib
from .models import User, Habit, HabitLog
from .serializers import UserSerializer, LoginSerializer, HabitSerializer, HabitLogSerializer

class RegistrationThrottle(AnonRateThrottle):
    """Custom throttle for registration endpoint"""
    rate = '5/hour'  # Max 5 registration attempts per hour per IP

@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([RegistrationThrottle])
def register(request):
    """Register a new user with duplicate prevention"""
    # Get client IP for rate limiting and tracking
    client_ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0] or \
                request.META.get('REMOTE_ADDR', '')
    
    # Check for rapid registration attempts from same IP
    cache_key = f"register_ip_{client_ip}"
    recent_attempts = cache.get(cache_key, 0)
    
    if recent_attempts >= 3:
        return Response({
            'error': 'Too many registration attempts. Please try again later.'
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Device fingerprinting (optional - requires frontend support)
    device_fingerprint = request.data.get('device_fingerprint', '')
    if device_fingerprint:
        fingerprint_key = f"register_device_{device_fingerprint}"
        if cache.get(fingerprint_key):
            return Response({
                'error': 'A registration was recently attempted from this device.'
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    with transaction.atomic():
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            # Additional duplicate check before creation
            email = serializer.validated_data.get('email').lower()
            username = serializer.validated_data.get('username').lower()
            
            if User.objects.filter(email__iexact=email).exists():
                return Response({
                    'error': 'An account with this email already exists.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            if User.objects.filter(username__iexact=username).exists():
                return Response({
                    'error': 'This username is already taken.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check for recently deleted accounts (soft delete pattern)
            # This prevents immediate re-registration of deleted accounts
            recently_deleted_key = f"deleted_email_{hashlib.md5(email.encode()).hexdigest()}"
            if cache.get(recently_deleted_key):
                return Response({
                    'error': 'This email was recently associated with a deleted account. Please wait 24 hours.'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            
            # Update rate limiting cache
            cache.set(cache_key, recent_attempts + 1, 3600)  # Reset after 1 hour
            if device_fingerprint:
                cache.set(fingerprint_key, True, 300)  # 5 minute cooldown per device
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login user and return token"""
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.validated_data['user']
        login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({
            'token': token.key,
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """Logout user and delete token"""
    try:
        request.user.auth_token.delete()
    except:
        pass
    logout(request)
    return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)

class HabitListCreateView(generics.ListCreateAPIView):
    """List all habits for a user or create a new one"""
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user, is_active=True)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

class HabitDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update or delete a specific habit"""
    serializer_class = HabitSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'habit_id'
    
    def get_queryset(self):
        return Habit.objects.filter(user=self.request.user)

# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/auth/register/', views.register, name='register'),
    path('api/auth/login/', views.login_view, name='login'),
    path('api/auth/logout/', views.logout_view, name='logout'),
    path('api/habits/', views.HabitListCreateView.as_view(), name='habit-list-create'),
    path('api/habits/<uuid:habit_id>/', views.HabitDetailView.as_view(), name='habit-detail'),
]

# settings.py additions
"""
Add these to your Django settings.py:

INSTALLED_APPS = [
    ...
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'your_app_name',
]

MIDDLEWARE = [
    ...
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
]

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# CORS settings for iOS app
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# For development only - be more restrictive in production
CORS_ALLOW_ALL_ORIGINS = True

AUTH_USER_MODEL = 'your_app_name.User'
"""