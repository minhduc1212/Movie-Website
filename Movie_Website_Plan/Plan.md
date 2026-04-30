# FilmSite — Kế Hoạch Kiến Trúc & Xây Dựng Hoàn Chỉnh (v2)

> **Stack:** Django 5 · PostgreSQL 16 · Redis 7 · Celery 5 · DRF · uv · pyproject.toml · Caddy · FFmpeg · HLS  
> **Phiên bản:** 2.0 — Đã bổ sung Auth, Comments, Ratings, Watch History, REST API, Redis Cache, Celery, CDN, Load Test, Monitoring, Security

---

## Mục Lục

1. [Tổng Quan Kiến Trúc](#1-tổng-quan-kiến-trúc)
2. [Công Cụ & Môi Trường — uv + pyproject.toml](#2-công-cụ--môi-trường--uv--pyprojecttoml)
3. [Cấu Trúc Dự Án](#3-cấu-trúc-dự-án)
4. [Database Schema — 22 Bảng](#4-database-schema--22-bảng)
5. [User Authentication & Authorization](#5-user-authentication--authorization)
6. [REST API — Django REST Framework](#6-rest-api--django-rest-framework)
7. [Comments System](#7-comments-system)
8. [Ratings System](#8-ratings-system)
9. [Watch History & Continue Watching](#9-watch-history--continue-watching)
10. [Redis Cache Strategy](#10-redis-cache-strategy)
11. [Celery — Background Tasks](#11-celery--background-tasks)
12. [Video Processing Pipeline](#12-video-processing-pipeline)
13. [CDN Integration](#13-cdn-integration)
14. [Django Models — Code Đầy Đủ](#14-django-models--code-đầy-đủ)
15. [Settings & Configuration](#15-settings--configuration)
16. [Caddy Reverse Proxy](#16-caddy-reverse-proxy)
17. [Security Hardening](#17-security-hardening)
18. [Load Testing — Locust](#18-load-testing--locust)
19. [Monitoring — Prometheus + Grafana](#19-monitoring--prometheus--grafana)
20. [Deployment & Automation](#20-deployment--automation)
21. [Backup & Maintenance](#21-backup--maintenance)
22. [Checklist Hoàn Chỉnh](#22-checklist-hoàn-chỉnh)

---

## 1. Tổng Quan Kiến Trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLIENT LAYER                            │
│   Browser / Mobile  ──  HLS.js Player  ──  REST API calls      │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP/HTTPS
┌──────────────────────────────▼──────────────────────────────────┐
│                      CADDY (Reverse Proxy)                      │
│   TLS termination · Security headers · Static file serving      │
│   Rate limiting · Gzip · Cache-Control headers                  │
└──────┬───────────────────────┬──────────────────────────────────┘
       │                       │
       ▼                       ▼
┌──────────────┐    ┌──────────────────────┐
│  CDN / Media │    │   Django (Gunicorn)  │
│  HLS streams │    │   REST API + Views   │
│  Posters/img │    │   DRF Serializers    │
└──────────────┘    └──────┬───────────────┘
                           │
          ┌────────────────┼───────────────────┐
          ▼                ▼                   ▼
   ┌─────────────┐  ┌───────────┐  ┌────────────────────┐
   │ PostgreSQL  │  │   Redis   │  │   Celery Workers   │
   │  (Primary   │  │  Cache +  │  │  FFmpeg · Metadata │
   │  Database)  │  │  Broker   │  │  Email · Cleanup   │
   └─────────────┘  └───────────┘  └────────────────────┘
                                           │
                                   ┌───────▼────────┐
                                   │  Celery Beat   │
                                   │  (Scheduler)   │
                                   └────────────────┘
```

### Luồng Request Điển Hình

```
User gõ URL
  → Caddy nhận request
    → Check static/media → serve trực tiếp (không qua Django)
    → Còn lại → forward tới Gunicorn:8000
      → Django Router
        → REST API (/api/v1/...) → DRF View → Redis Cache? → DB → Response JSON
        → Web Views (/...)       → Django View → Template → Response HTML
```

---

## 2. Công Cụ & Môi Trường — uv + pyproject.toml

> **uv** là package manager Python thế hệ mới (viết bằng Rust), nhanh hơn pip 10-100x. Thay thế hoàn toàn `pip` + `venv`.

### 2.1 Cài đặt uv

```powershell
# Windows — PowerShell (chạy một lần duy nhất)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Kiểm tra
uv --version   # uv 0.x.x
```

### 2.2 Khởi tạo dự án

```powershell
cd C:\Projects
uv init filmsite --python 3.12
cd filmsite

# uv tự tạo:
#   pyproject.toml    ← file cấu hình chính (thay requirements.txt)
#   .python-version   ← pin Python version
#   .venv/            ← virtual env (tự động)
```

### 2.3 pyproject.toml — Hoàn Chỉnh

```toml
[project]
name = "filmsite"
version = "2.0.0"
description = "FilmSite — Movie streaming platform"
requires-python = ">=3.12"
dependencies = [
    # ── Core Framework ──────────────────────────
    "django>=5.1,<6",
    "djangorestframework>=3.15",
    "django-cors-headers>=4.4",
    "django-filter>=24.3",

    # ── Auth & Security ──────────────────────────
    "djangorestframework-simplejwt>=5.3",
    "django-allauth>=65.0",          # OAuth Google/GitHub
    "django-ratelimit>=4.1",
    "django-axes>=7.0",              # Brute-force protection
    "argon2-cffi>=23.1",             # Password hasher

    # ── Database ─────────────────────────────────
    "psycopg[binary]>=3.2",          # PostgreSQL driver (psycopg3)
    "django-extensions>=3.2",

    # ── Cache & Queue ────────────────────────────
    "redis>=5.1",
    "django-redis>=5.4",
    "celery>=5.4",
    "django-celery-beat>=2.7",
    "django-celery-results>=2.5",
    "flower>=2.0",                   # Celery monitoring UI

    # ── Storage & Media ──────────────────────────
    "boto3>=1.35",                   # S3-compatible CDN
    "django-storages>=1.14",
    "Pillow>=10.4",                  # Image processing

    # ── API Utilities ────────────────────────────
    "drf-spectacular>=0.27",         # OpenAPI / Swagger docs
    "django-silk>=5.3",              # API profiling (dev)

    # ── WSGI Server ──────────────────────────────
    "gunicorn>=23.0",

    # ── Monitoring ───────────────────────────────
    "django-prometheus>=2.3",
    "sentry-sdk>=2.14",

    # ── Utilities ────────────────────────────────
    "python-decouple>=3.8",          # .env reader
    "requests>=2.32",
    "httpx>=0.27",                   # Async HTTP client
    "python-slugify>=8.0",
    "rich>=13.8",                    # Beautiful CLI output
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "pytest-cov>=5.0",
    "factory-boy>=3.3",
    "faker>=30.0",
    "locust>=2.31",                  # Load testing
    "django-debug-toolbar>=4.4",
    "ipython>=8.27",
    "pre-commit>=3.8",
    "ruff>=0.6",                     # Linter + formatter
    "mypy>=1.11",
    "django-stubs>=5.1",
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.3",
    "pytest-django>=4.9",
    "pytest-cov>=5.0",
    "factory-boy>=3.3",
    "faker>=30.0",
    "locust>=2.31",
    "django-debug-toolbar>=4.4",
    "ipython>=8.27",
    "pre-commit>=3.8",
    "ruff>=0.6",
    "mypy>=1.11",
    "django-stubs>=5.1",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "config.settings.test"
python_files = ["test_*.py", "*_test.py"]
addopts = "--cov=. --cov-report=html -v"

[tool.mypy]
plugins = ["mypy_django_plugin.main"]
ignore_missing_imports = true

[tool.django-stubs]
django_settings_module = "config.settings.base"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

### 2.4 Workflow hàng ngày với uv

```powershell
# Cài toàn bộ dependencies (lần đầu hoặc sau khi clone)
uv sync

# Cài thêm package mới
uv add django-silk

# Cài dev dependency
uv add --dev locust

# Xóa package
uv remove django-silk

# Chạy lệnh trong venv (không cần activate)
uv run python manage.py migrate
uv run python manage.py runserver
uv run celery -A config worker -l info
uv run pytest

# Xuất requirements.txt (nếu cần tương thích với hệ thống khác)
uv export --format requirements-txt > requirements.txt
```

---

## 3. Cấu Trúc Dự Án

```
C:\Projects\filmsite\
│
├── pyproject.toml              ← Config chính (deps, tools, pytest)
├── .python-version             ← 3.12
├── .env                        ← Secrets (KHÔNG commit)
├── .env.example                ← Template env
├── .gitignore
├── .pre-commit-config.yaml
│
├── config/                     ← Django project settings
│   ├── __init__.py
│   ├── urls.py                 ← Root URL router
│   ├── wsgi.py
│   ├── asgi.py
│   └── settings/
│       ├── base.py             ← Common settings
│       ├── development.py      ← Dev overrides
│       ├── production.py       ← Prod overrides
│       └── test.py             ← Test overrides
│
├── apps/
│   ├── films/                  ← Core: Movie, Episode, Genre...
│   │   ├── models.py
│   │   ├── views.py            ← Template views
│   │   ├── api/
│   │   │   ├── views.py        ← DRF ViewSets
│   │   │   ├── serializers.py
│   │   │   ├── filters.py
│   │   │   └── urls.py
│   │   ├── admin.py
│   │   ├── tasks.py            ← Celery tasks
│   │   ├── cache.py            ← Cache helpers
│   │   └── templates/films/
│   │       ├── home.html
│   │       ├── detail.html
│   │       ├── search.html
│   │       └── person.html
│   │
│   ├── users/                  ← Auth, Profile, Watchlist
│   │   ├── models.py           ← CustomUser, UserProfile
│   │   ├── api/
│   │   │   ├── views.py        ← Register, Login, Refresh, Me
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   ├── admin.py
│   │   └── templates/users/
│   │       ├── login.html
│   │       ├── register.html
│   │       └── profile.html
│   │
│   ├── comments/               ← Nested comments
│   │   ├── models.py
│   │   ├── api/
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tasks.py            ← Notify on reply
│   │
│   ├── ratings/                ← Star ratings
│   │   ├── models.py
│   │   ├── api/
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── signals.py          ← Cập nhật avg_rating tự động
│   │
│   ├── history/                ← Watch history + resume
│   │   ├── models.py
│   │   ├── api/
│   │   │   ├── views.py
│   │   │   ├── serializers.py
│   │   │   └── urls.py
│   │   └── tasks.py            ← Cleanup old history
│   │
│   └── watchlist/              ← Bookmark / Favorites
│       ├── models.py
│       └── api/
│           ├── views.py
│           ├── serializers.py
│           └── urls.py
│
├── video_processor/
│   ├── processor.py            ← FFmpeg HLS encode
│   ├── metadata_fetcher.py     ← TMDB/Jikan API
│   ├── thumbnail_extractor.py  ← Auto thumbnail
│   └── raw_videos/             ← Drop .mp4 vào đây
│
├── media/                      ← MEDIA_ROOT (local dev)
│   ├── hls_streams/
│   ├── posters/
│   ├── backdrops/
│   ├── thumbnails/
│   └── subs/
│
├── static/                     ← STATIC_ROOT
│   ├── css/
│   ├── js/
│   └── fonts/
│
├── logs/
│   ├── django.log
│   ├── celery.log
│   └── access.log
│
├── tests/
│   ├── conftest.py
│   ├── factories.py
│   ├── test_api_films.py
│   ├── test_api_auth.py
│   ├── test_api_comments.py
│   └── test_api_ratings.py
│
├── monitoring/
│   ├── prometheus.yml
│   └── grafana/
│       └── dashboards/
│
└── scripts/
    ├── start_gunicorn.bat
    ├── start_celery.bat
    ├── start_celery_beat.bat
    ├── backup_db.bat
    └── load_test.sh
```

---

## 4. Database Schema — 22 Bảng

### 4.1 Entity Relationship Diagram

```
users ──────────────────────────────────────────────────┐
  │                                                      │
  ├──< watch_history >── episodes                        │
  ├──< ratings      >── movies ──< episodes              │
  ├──< comments (self-ref, nested) >── movies            │
  ├──< watchlist_items >── movies                        │
  └──< comment_likes >── comments                        │
                                                         │
movies ──< episodes ──< subtitles                        │
  │                                                      │
  ├──< trailers                                          │
  ├──< movie_genres    >── genres                        │
  ├──< movie_tags      >── tags                          │
  ├──< movie_countries >── countries                     │
  ├──< movie_cast_crew >── people                        │
  ├──< movie_studios   >── studios                       │
  └──  parent_movie (self-ref OVA/Special)               │
                                                         │
user_profiles ─── users ───────────────────────────────-┘
```

### 4.2 Bảng Mới So Với v1

| Bảng | Mục đích | Ghi chú |
|------|----------|---------|
| `users` (CustomUser) | Thay AbstractUser | email login, avatar |
| `user_profiles` | Bio, preferences | 1-1 với User |
| `ratings` | 1-10 sao per user/movie | Unique per user+movie |
| `comments` | Nested comments | Self-FK cho reply |
| `comment_likes` | Like/Dislike comment | — |
| `watch_history` | Lịch sử xem | Theo episode |
| `watchlist_items` | Bookmark | Theo movie |

---

## 5. User Authentication & Authorization

### 5.1 CustomUser Model

```python
# apps/users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """
    Dùng email làm username. Mở rộng dễ dàng sau này.
    """
    username    = None  # Tắt username mặc định
    email       = models.EmailField(_('email address'), unique=True)
    display_name= models.CharField(max_length=100, blank=True)
    avatar      = models.ImageField(upload_to='avatars/', null=True, blank=True)
    is_verified = models.BooleanField(default=False)  # Email verification
    created_at  = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD  = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'
        verbose_name = 'User'

    def __str__(self):
        return self.email


class UserProfile(models.Model):
    user        = models.OneToOneField(CustomUser, on_delete=models.CASCADE,
                                       related_name='profile')
    bio         = models.TextField(blank=True, max_length=500)
    birth_date  = models.DateField(null=True, blank=True)
    country     = models.CharField(max_length=3, blank=True)  # ISO 3166
    preferred_language = models.CharField(max_length=10, default='vi')
    # Preferences lưu dưới dạng JSON
    notifications_email  = models.BooleanField(default=True)
    notifications_reply  = models.BooleanField(default=True)
    # Stats (denormalized, update qua Celery)
    total_watch_time   = models.IntegerField(default=0)  # phút
    total_movies_watched = models.IntegerField(default=0)

    class Meta:
        db_table = 'user_profiles'

    def __str__(self):
        return f'Profile: {self.user.email}'
```

### 5.2 JWT Authentication — Settings

```python
# config/settings/base.py (phần Auth)
from datetime import timedelta

AUTH_USER_MODEL = 'users.CustomUser'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # Argon2 — mạnh nhất
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # Fallback
]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': env('JWT_SECRET_KEY'),
    'AUTH_HEADER_TYPES': ('Bearer',),
    'UPDATE_LAST_LOGIN': True,
}

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # Django Admin
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '300/min',
        'auth': '10/min',     # Login/Register
        'comment': '20/min',  # Post comment
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}
```

### 5.3 Auth API Endpoints

```python
# apps/users/api/urls.py
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from . import views

urlpatterns = [
    path('register/',      views.RegisterView.as_view(),     name='auth-register'),
    path('login/',         views.LoginView.as_view(),        name='auth-login'),
    path('logout/',        TokenBlacklistView.as_view(),     name='auth-logout'),
    path('token/refresh/', TokenRefreshView.as_view(),       name='token-refresh'),
    path('verify-email/<str:token>/', views.VerifyEmailView.as_view(), name='verify-email'),
    path('forgot-password/',          views.ForgotPasswordView.as_view()),
    path('reset-password/',           views.ResetPasswordView.as_view()),
    path('me/',            views.MeView.as_view(),           name='user-me'),
    path('me/avatar/',     views.UploadAvatarView.as_view(), name='user-avatar'),
    path('me/profile/',    views.UpdateProfileView.as_view()),
]
```

```python
# apps/users/api/views.py
from django.contrib.auth import authenticate
from django.core.cache import cache
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema
from .serializers import (
    RegisterSerializer, LoginSerializer,
    UserDetailSerializer, UpdateProfileSerializer,
)
from apps.users.tasks import send_verification_email


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class   = RegisterSerializer
    throttle_scope     = 'auth'

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Gửi email xác nhận qua Celery
        send_verification_email.delay(user.id)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user':    UserDetailSerializer(user).data,
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'message': 'Đăng ký thành công. Vui lòng kiểm tra email để xác nhận tài khoản.',
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class   = LoginSerializer
    throttle_scope     = 'auth'

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']
        user = authenticate(request, email=email, password=password)
        if not user:
            return Response({'detail': 'Email hoặc mật khẩu không đúng.'},
                            status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({'detail': 'Tài khoản đã bị vô hiệu hóa.'},
                            status=status.HTTP_403_FORBIDDEN)
        refresh = RefreshToken.for_user(user)
        return Response({
            'user':    UserDetailSerializer(user).data,
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
        })


class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class   = UserDetailSerializer

    def get_object(self):
        return self.request.user
```

### 5.4 Permissions Tùy Chỉnh

```python
# apps/films/api/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    """Admin có toàn quyền. Người dùng thường chỉ đọc."""
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return request.user and request.user.is_staff


class IsOwnerOrReadOnly(BasePermission):
    """Chỉ chủ sở hữu mới được sửa/xóa."""
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.user == request.user


class IsVerifiedUser(BasePermission):
    """Yêu cầu email đã xác nhận mới được comment/rating."""
    def has_permission(self, request, view):
        return (request.user and request.user.is_authenticated
                and request.user.is_verified)
```

---

## 6. REST API — Django REST Framework

### 6.1 URL Structure

```
/api/v1/
  ├── auth/
  │   ├── register/
  │   ├── login/
  │   ├── logout/
  │   ├── token/refresh/
  │   ├── me/
  │   └── me/profile/
  │
  ├── films/
  │   ├── movies/                    GET (list, search, filter)
  │   ├── movies/<slug>/             GET (detail)
  │   ├── movies/<slug>/episodes/    GET
  │   ├── movies/<slug>/comments/    GET, POST
  │   ├── movies/<slug>/rating/      GET, POST, PUT
  │   ├── genres/                    GET
  │   ├── people/<slug>/             GET (diễn viên)
  │   └── search/                    GET ?q=...
  │
  ├── comments/
  │   ├── <id>/                      GET, PUT, DELETE
  │   ├── <id>/like/                 POST
  │   └── <id>/replies/              GET, POST
  │
  ├── history/
  │   ├── /                          GET, DELETE (all)
  │   └── <episode_id>/              POST (upsert), DELETE
  │
  ├── watchlist/
  │   ├── /                          GET, POST
  │   └── <movie_slug>/              DELETE
  │
  └── schema/                        Swagger / OpenAPI docs
      ├── swagger-ui/
      └── redoc/
```

### 6.2 Movie API — ViewSet

```python
# apps/films/api/views.py
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.core.cache import cache
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.films.models import Movie, Episode
from apps.films.cache import get_movie_detail_cache_key
from .serializers import MovieListSerializer, MovieDetailSerializer, EpisodeSerializer
from .filters import MovieFilter
from .permissions import IsAdminOrReadOnly


class MovieViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Movie.objects
        .filter(is_hidden=False)
        .select_related('parent_movie')
        .prefetch_related('genres', 'countries', 'tags', 'studios')
    )
    lookup_field = 'slug'
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = MovieFilter
    search_fields    = ['title', 'original_title', 'cast_crew__full_name']
    ordering_fields  = ['release_year', 'imdb_rating', 'view_count', 'created_at']
    ordering         = ['-created_at']

    def get_serializer_class(self):
        if self.action == 'retrieve':
            return MovieDetailSerializer
        return MovieListSerializer

    def retrieve(self, request, *args, **kwargs):
        slug = kwargs['slug']
        cache_key = get_movie_detail_cache_key(slug)
        cached = cache.get(cache_key)
        if cached:
            return Response(cached)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        cache.set(cache_key, data, timeout=60 * 10)  # 10 phút
        return Response(data)

    @action(detail=True, methods=['get'])
    def episodes(self, request, slug=None):
        movie = self.get_object()
        qs = movie.episodes.all().prefetch_related('subtitles')
        return Response(EpisodeSerializer(qs, many=True).data)

    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Phim nổi bật — cache 5 phút."""
        cached = cache.get('featured_movies')
        if not cached:
            qs = self.get_queryset().filter(is_featured=True)[:12]
            cached = MovieListSerializer(qs, many=True).data
            cache.set('featured_movies', cached, 300)
        return Response(cached)

    @action(detail=False, methods=['get'])
    def trending(self, request):
        """Phim xem nhiều trong 7 ngày — Redis Sorted Set."""
        from apps.films.cache import get_trending_movies
        return Response(get_trending_movies())
```

### 6.3 Movie Serializers

```python
# apps/films/api/serializers.py
from rest_framework import serializers
from apps.films.models import Movie, Episode, Genre, Subtitle


class GenreSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Genre
        fields = ['id', 'name', 'slug']


class EpisodeSerializer(serializers.ModelSerializer):
    subtitles = serializers.SerializerMethodField()

    class Meta:
        model  = Episode
        fields = [
            'id', 'season_number', 'episode_number', 'episode_name',
            'm3u8_path', 'duration', 'air_date', 'view_count',
            'is_free', 'subtitles',
        ]

    def get_subtitles(self, obj):
        return obj.subtitles.values('language_code', 'language_label',
                                     'sub_path', 'is_default')


class MovieListSerializer(serializers.ModelSerializer):
    genres = GenreSerializer(many=True, read_only=True)

    class Meta:
        model  = Movie
        fields = [
            'id', 'title', 'slug', 'medium_type', 'status',
            'release_year', 'poster_path', 'thumbnail_path',
            'imdb_rating', 'avg_rating', 'view_count',
            'genres', 'is_featured',
        ]


class MovieDetailSerializer(serializers.ModelSerializer):
    genres    = GenreSerializer(many=True, read_only=True)
    episodes  = EpisodeSerializer(many=True, read_only=True, source='episodes.all')
    cast_crew = serializers.SerializerMethodField()
    user_rating    = serializers.SerializerMethodField()
    user_in_watchlist = serializers.SerializerMethodField()

    class Meta:
        model  = Movie
        fields = '__all__'

    def get_cast_crew(self, obj):
        from apps.films.models import MovieCastCrew
        qs = MovieCastCrew.objects.filter(movie=obj).select_related('person')
        return [
            {
                'id':             cc.person.id,
                'name':           cc.person.full_name,
                'slug':           cc.person.slug,
                'role':           cc.role,
                'character_name': cc.character_name,
                'avatar':         cc.person.avatar_path,
                'sort_order':     cc.sort_order,
            }
            for cc in qs.order_by('sort_order')
        ]

    def get_user_rating(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.ratings.models import Rating
            r = Rating.objects.filter(user=request.user, movie=obj).first()
            return r.score if r else None
        return None

    def get_user_in_watchlist(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            from apps.watchlist.models import WatchlistItem
            return WatchlistItem.objects.filter(user=request.user, movie=obj).exists()
        return False
```

### 6.4 Movie Filter

```python
# apps/films/api/filters.py
import django_filters
from apps.films.models import Movie, Genre, Country


class MovieFilter(django_filters.FilterSet):
    genre   = django_filters.CharFilter(field_name='genres__slug',   lookup_expr='exact')
    country = django_filters.CharFilter(field_name='countries__code', lookup_expr='exact')
    year    = django_filters.NumberFilter(field_name='release_year')
    year_gte = django_filters.NumberFilter(field_name='release_year', lookup_expr='gte')
    year_lte = django_filters.NumberFilter(field_name='release_year', lookup_expr='lte')
    rating_gte = django_filters.NumberFilter(field_name='imdb_rating', lookup_expr='gte')
    type    = django_filters.CharFilter(field_name='medium_type')
    status  = django_filters.CharFilter(field_name='status')

    class Meta:
        model  = Movie
        fields = ['genre', 'country', 'year', 'type', 'status']
```

### 6.5 OpenAPI / Swagger

```python
# config/settings/base.py
SPECTACULAR_SETTINGS = {
    'TITLE': 'FilmSite API',
    'DESCRIPTION': 'REST API cho hệ thống streaming phim.',
    'VERSION': '2.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SECURITY': [{'BearerAuth': []}],
}
```

Truy cập sau khi chạy server:
- Swagger UI: `http://localhost:8000/api/v1/schema/swagger-ui/`
- ReDoc: `http://localhost:8000/api/v1/schema/redoc/`

---

## 7. Comments System

### 7.1 Comment Model

```python
# apps/comments/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Comment(models.Model):
    movie      = models.ForeignKey('films.Movie', on_delete=models.CASCADE,
                                   related_name='comments')
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='comments')
    parent     = models.ForeignKey('self', null=True, blank=True,
                                   on_delete=models.CASCADE, related_name='replies')
    body       = models.TextField(max_length=2000)
    is_spoiler = models.BooleanField(default=False)
    is_hidden  = models.BooleanField(default=False)  # Admin ẩn vi phạm
    like_count = models.IntegerField(default=0)      # Denormalized
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'comments'
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['movie', '-created_at']),
            models.Index(fields=['parent']),
        ]

    @property
    def is_reply(self):
        return self.parent_id is not None

    def __str__(self):
        return f'{self.user.email} → {self.movie.title}: {self.body[:50]}'


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE,
                                related_name='likes')
    user    = models.ForeignKey(User, on_delete=models.CASCADE)
    value   = models.SmallIntegerField(default=1)  # 1=like, -1=dislike

    class Meta:
        db_table = 'comment_likes'
        unique_together = ('comment', 'user')
```

### 7.2 Comment API

```python
# apps/comments/api/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404
from apps.comments.models import Comment, CommentLike
from apps.films.models import Movie
from .serializers import CommentSerializer, CommentCreateSerializer
from apps.comments.tasks import notify_comment_reply


class MovieCommentListCreateView(generics.ListCreateAPIView):
    throttle_scope = 'comment'

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CommentCreateSerializer
        return CommentSerializer

    def get_queryset(self):
        movie = get_object_or_404(Movie, slug=self.kwargs['slug'])
        return (
            Comment.objects
            .filter(movie=movie, parent=None, is_hidden=False)
            .select_related('user')
            .prefetch_related('replies__user')
        )

    def perform_create(self, serializer):
        movie   = get_object_or_404(Movie, slug=self.kwargs['slug'])
        comment = serializer.save(user=self.request.user, movie=movie)
        # Thông báo reply qua Celery
        if comment.parent_id:
            notify_comment_reply.delay(comment.id)


class CommentLikeView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        comment = get_object_or_404(Comment, pk=pk)
        value   = request.data.get('value', 1)
        if value not in [1, -1]:
            return Response({'detail': 'value phải là 1 hoặc -1'},
                            status=status.HTTP_400_BAD_REQUEST)

        obj, created = CommentLike.objects.update_or_create(
            comment=comment, user=request.user,
            defaults={'value': value}
        )
        # Cập nhật denormalized like_count
        comment.like_count = CommentLike.objects.filter(
            comment=comment, value=1).count()
        comment.save(update_fields=['like_count'])
        return Response({'like_count': comment.like_count,
                         'user_value': value})
```

### 7.3 Comment Serializer (Nested)

```python
# apps/comments/api/serializers.py
from rest_framework import serializers
from apps.comments.models import Comment


class CommentUserSerializer(serializers.Serializer):
    id           = serializers.IntegerField()
    display_name = serializers.CharField()
    avatar       = serializers.ImageField()


class CommentSerializer(serializers.ModelSerializer):
    user    = CommentUserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()

    class Meta:
        model  = Comment
        fields = ['id', 'user', 'body', 'is_spoiler', 'like_count',
                  'created_at', 'updated_at', 'replies']

    def get_replies(self, obj):
        # Chỉ 1 cấp replies để tránh N+1
        qs = obj.replies.filter(is_hidden=False).select_related('user')
        return CommentSerializer(qs, many=True).data


class CommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Comment
        fields = ['body', 'parent', 'is_spoiler']

    def validate_body(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError('Comment quá ngắn.')
        return value
```

---

## 8. Ratings System

### 8.1 Rating Model

```python
# apps/ratings/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


class Rating(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='ratings')
    movie      = models.ForeignKey('films.Movie', on_delete=models.CASCADE,
                                   related_name='user_ratings')
    score      = models.SmallIntegerField(
                     validators=[MinValueValidator(1), MaxValueValidator(10)],
                     help_text='1-10 sao')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'ratings'
        unique_together = ('user', 'movie')  # 1 user 1 vote per movie
        indexes = [models.Index(fields=['movie'])]

    def __str__(self):
        return f'{self.user.email} → {self.movie.title}: {self.score}/10'
```

### 8.2 Rating Signal — Tự Động Cập Nhật avg_rating

```python
# apps/ratings/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import Rating
from apps.films.models import Movie


def _update_movie_avg_rating(movie_id):
    avg = Rating.objects.filter(movie_id=movie_id).aggregate(
              avg=Avg('score'))['avg']
    Movie.objects.filter(pk=movie_id).update(
        avg_rating=round(avg, 2) if avg else None,
        rating_count=Rating.objects.filter(movie_id=movie_id).count(),
    )


@receiver(post_save, sender=Rating)
def on_rating_save(sender, instance, **kwargs):
    _update_movie_avg_rating(instance.movie_id)


@receiver(post_delete, sender=Rating)
def on_rating_delete(sender, instance, **kwargs):
    _update_movie_avg_rating(instance.movie_id)
```

### 8.3 Rating API

```python
# apps/ratings/api/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.ratings.models import Rating
from apps.films.models import Movie
from .serializers import RatingSerializer


class MovieRatingView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = RatingSerializer

    def get(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug)
        rating = Rating.objects.filter(user=request.user, movie=movie).first()
        return Response({
            'movie_slug':  slug,
            'avg_rating':  movie.avg_rating,
            'rating_count': movie.rating_count,
            'user_score':  rating.score if rating else None,
        })

    def post(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rating, created = Rating.objects.update_or_create(
            user=request.user, movie=movie,
            defaults={'score': serializer.validated_data['score']}
        )
        return Response(
            {'score': rating.score, 'created': created},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def delete(self, request, slug):
        movie = get_object_or_404(Movie, slug=slug)
        Rating.objects.filter(user=request.user, movie=movie).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## 9. Watch History & Continue Watching

### 9.1 Watch History Model

```python
# apps/history/models.py
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class WatchHistory(models.Model):
    user        = models.ForeignKey(User, on_delete=models.CASCADE,
                                    related_name='watch_history')
    episode     = models.ForeignKey('films.Episode', on_delete=models.CASCADE,
                                    related_name='watch_history')
    # Resume playback
    progress_seconds = models.IntegerField(default=0)   # Đã xem đến giây thứ N
    duration_seconds = models.IntegerField(default=0)   # Tổng thời lượng
    completed        = models.BooleanField(default=False)  # Xem > 90%
    watched_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table     = 'watch_history'
        unique_together = ('user', 'episode')  # Upsert theo cặp này
        ordering = ['-watched_at']
        indexes  = [models.Index(fields=['user', '-watched_at'])]

    @property
    def progress_percent(self):
        if not self.duration_seconds:
            return 0
        return round(self.progress_seconds / self.duration_seconds * 100, 1)

    def __str__(self):
        return f'{self.user.email} → {self.episode} @ {self.progress_seconds}s'


class WatchlistItem(models.Model):
    user     = models.ForeignKey(User, on_delete=models.CASCADE,
                                 related_name='watchlist')
    movie    = models.ForeignKey('films.Movie', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'watchlist_items'
        unique_together = ('user', 'movie')
        ordering = ['-added_at']
```

### 9.2 Watch History API

```python
# apps/history/api/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.history.models import WatchHistory
from apps.films.models import Episode
from .serializers import WatchHistorySerializer


class WatchHistoryListView(generics.ListAPIView):
    """Lấy lịch sử xem — phân trang 20 items."""
    permission_classes = [permissions.IsAuthenticated]
    serializer_class   = WatchHistorySerializer

    def get_queryset(self):
        return (
            WatchHistory.objects
            .filter(user=self.request.user)
            .select_related('episode__movie')
            .order_by('-watched_at')
        )


class WatchProgressUpdateView(generics.GenericAPIView):
    """
    POST /api/v1/history/<episode_id>/
    Gọi mỗi 15-30 giây khi đang xem — upsert progress.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, episode_id):
        episode = get_object_or_404(Episode, pk=episode_id)
        progress  = int(request.data.get('progress_seconds', 0))
        duration  = int(request.data.get('duration_seconds', 0))
        completed = (duration > 0 and progress / duration >= 0.9)

        history, _ = WatchHistory.objects.update_or_create(
            user=request.user, episode=episode,
            defaults={
                'progress_seconds': progress,
                'duration_seconds': duration,
                'completed':        completed,
            }
        )
        # Tăng view_count (dùng F() tránh race condition)
        if completed and not history.completed:
            from django.db.models import F
            episode.movie.view_count = F('view_count') + 1
            episode.movie.save(update_fields=['view_count'])
            # Cập nhật Redis trending
            from apps.films.cache import increment_trending
            increment_trending(episode.movie_id)

        return Response({'progress_percent': history.progress_percent})
```

---

## 10. Redis Cache Strategy

### 10.1 Cài đặt Redis

```bash
# Windows — dùng WSL2 hoặc Docker
docker run -d --name filmsite-redis -p 6379:6379 redis:7-alpine

# Hoặc WSL2
sudo apt install redis-server
sudo service redis-server start
```

### 10.2 Django Cache Config

```python
# config/settings/base.py
CACHES = {
    'default': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS':   'django_redis.client.DefaultClient',
            'COMPRESSOR':     'django_redis.compressors.zlib.ZlibCompressor',
            'SERIALIZER':     'django_redis.serializers.json.JSONSerializer',
            'SOCKET_TIMEOUT': 3,
            'SOCKET_CONNECT_TIMEOUT': 3,
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
            'IGNORE_EXCEPTIONS': True,  # Nếu Redis down, fallback về DB
        },
        'KEY_PREFIX': 'fs',     # Prefix tránh xung đột
        'TIMEOUT':    300,      # Default 5 phút
    },
    'sessions': {
        'BACKEND':  'django_redis.cache.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'OPTIONS':  {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    },
}

SESSION_ENGINE   = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'sessions'

# Celery Broker
CELERY_BROKER_URL        = env('REDIS_URL', default='redis://127.0.0.1:6379/2')
CELERY_RESULT_BACKEND    = env('REDIS_URL', default='redis://127.0.0.1:6379/2')
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TIMEZONE          = 'Asia/Ho_Chi_Minh'
```

### 10.3 Cache Helpers

```python
# apps/films/cache.py
from django.core.cache import cache
import redis

_redis = redis.Redis.from_url('redis://127.0.0.1:6379/0')
TRENDING_KEY = 'fs:trending'


def get_movie_detail_cache_key(slug: str) -> str:
    return f'movie:detail:{slug}'


def invalidate_movie_cache(slug: str):
    """Gọi sau khi admin update phim."""
    keys = [
        get_movie_detail_cache_key(slug),
        'featured_movies',
        'fs:trending',
    ]
    cache.delete_many(keys)


def increment_trending(movie_id: int):
    """
    Dùng Redis Sorted Set để track trending.
    Key: fs:trending — Score = số lượt xem trong cửa sổ
    """
    _redis.zincrby(TRENDING_KEY, 1, str(movie_id))
    _redis.expire(TRENDING_KEY, 60 * 60 * 24 * 7)  # TTL 7 ngày


def get_trending_movies(limit: int = 10) -> list:
    """Lấy top N movie IDs từ Sorted Set."""
    from apps.films.models import Movie
    from apps.films.api.serializers import MovieListSerializer

    ids = [int(x) for x in _redis.zrevrange(TRENDING_KEY, 0, limit - 1)]
    if not ids:
        # Fallback nếu Redis trống
        return MovieListSerializer(
            Movie.objects.filter(is_hidden=False).order_by('-view_count')[:limit],
            many=True
        ).data

    movies = {m.id: m for m in Movie.objects.filter(id__in=ids, is_hidden=False)}
    return MovieListSerializer([movies[i] for i in ids if i in movies], many=True).data
```

### 10.4 Cache Strategy Tổng Quan

| Cache Key | Nội dung | TTL | Khi Invalidate |
|-----------|----------|-----|----------------|
| `movie:detail:<slug>` | MovieDetailSerializer | 10 phút | Admin edit movie |
| `featured_movies` | Danh sách phim nổi bật | 5 phút | Thay đổi is_featured |
| `fs:trending` | Redis Sorted Set view counts | 7 ngày | Rolling, không invalidate |
| `genre:list` | Tất cả genres | 1 giờ | Thêm/xóa genre |
| `search:<hash>` | Kết quả tìm kiếm | 2 phút | Không cần invalidate |
| `user:me:<id>` | UserDetail | 5 phút | User update profile |

---

## 11. Celery — Background Tasks

### 11.1 Celery Config

```python
# config/celery.py
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

app = Celery('filmsite')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# ── Scheduled Tasks (Celery Beat) ─────────────────────────────
app.conf.beat_schedule = {
    # Làm mới trending cache mỗi 30 phút
    'refresh-trending': {
        'task': 'apps.films.tasks.refresh_trending_cache',
        'schedule': crontab(minute='*/30'),
    },
    # Xóa watch history cũ hơn 1 năm
    'cleanup-old-history': {
        'task': 'apps.history.tasks.cleanup_old_watch_history',
        'schedule': crontab(hour=3, minute=0),  # Mỗi ngày 3:00 AM
    },
    # Backup DB hàng ngày
    'daily-db-backup': {
        'task': 'apps.films.tasks.backup_database',
        'schedule': crontab(hour=2, minute=0),
    },
    # Sync IMDB rating từ TMDB mỗi tuần
    'sync-imdb-ratings': {
        'task': 'apps.films.tasks.sync_imdb_ratings',
        'schedule': crontab(hour=1, minute=0, day_of_week=1),
    },
}
```

### 11.2 Celery Tasks

```python
# apps/films/tasks.py
from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.cache import cache

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_video_file(self, raw_path: str, movie_id: int, episode_id: int):
    """
    Encode MP4 → HLS sau khi admin upload.
    Chạy nền — không block request.
    """
    try:
        from video_processor.processor import encode_to_hls
        from apps.films.models import Episode
        result = encode_to_hls(raw_path, episode_id)
        Episode.objects.filter(pk=episode_id).update(
            m3u8_path=result['m3u8_path'],
            duration=result['duration_minutes'],
        )
        # Invalidate cache
        from apps.films.models import Movie
        movie = Movie.objects.get(pk=movie_id)
        from apps.films.cache import invalidate_movie_cache
        invalidate_movie_cache(movie.slug)
        logger.info(f'Video processed: episode_id={episode_id}')
    except Exception as exc:
        logger.error(f'Video processing failed: {exc}')
        raise self.retry(exc=exc)


@shared_task
def fetch_movie_metadata(movie_id: int, source: str = 'tmdb'):
    """Crawl metadata từ TMDB/Jikan API."""
    from video_processor.metadata_fetcher import fetch_and_update
    fetch_and_update(movie_id, source)


@shared_task
def refresh_trending_cache():
    """Rebuild trending list từ Redis Sorted Set."""
    from apps.films.cache import get_trending_movies
    data = get_trending_movies(limit=20)
    cache.set('trending_movies', data, timeout=1800)
    logger.info('Trending cache refreshed.')


@shared_task
def backup_database():
    """pg_dump vào backup folder."""
    import subprocess, datetime, os
    date_str  = datetime.date.today().isoformat()
    backup_dir = os.environ.get('BACKUP_DIR', 'C:\\Backups\\filmsite')
    os.makedirs(backup_dir, exist_ok=True)
    output = f'{backup_dir}\\filmsite_{date_str}.backup'
    result = subprocess.run([
        'pg_dump', '-U', os.environ['DB_USER'],
        '-d', os.environ['DB_NAME'],
        '-F', 'c', '-f', output
    ], capture_output=True, env={**os.environ, 'PGPASSWORD': os.environ['DB_PASSWORD']})
    if result.returncode == 0:
        logger.info(f'DB backup OK: {output}')
    else:
        logger.error(f'DB backup FAILED: {result.stderr.decode()}')


# apps/users/tasks.py
@shared_task
def send_verification_email(user_id: int):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.conf import settings
    import secrets

    User = get_user_model()
    user  = User.objects.get(pk=user_id)
    token = secrets.token_urlsafe(32)
    cache.set(f'email_verify:{token}', user_id, timeout=3600)
    verify_url = f'{settings.SITE_URL}/api/v1/auth/verify-email/{token}/'
    send_mail(
        subject='Xác nhận email — FilmSite',
        message=f'Click để xác nhận: {verify_url}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )


# apps/comments/tasks.py
@shared_task
def notify_comment_reply(comment_id: int):
    from apps.comments.models import Comment
    from django.core.mail import send_mail
    comment = Comment.objects.select_related('parent__user', 'user', 'movie').get(pk=comment_id)
    if not comment.parent:
        return
    parent_user = comment.parent.user
    if not parent_user.profile.notifications_reply:
        return
    send_mail(
        subject=f'Có người reply comment của bạn — {comment.movie.title}',
        message=f'{comment.user.display_name or comment.user.email} đã reply: "{comment.body[:100]}"',
        from_email='noreply@filmsite.local',
        recipient_list=[parent_user.email],
    )


# apps/history/tasks.py
@shared_task
def cleanup_old_watch_history():
    from apps.history.models import WatchHistory
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(days=365)
    deleted, _ = WatchHistory.objects.filter(watched_at__lt=cutoff).delete()
    logger.info(f'Cleaned up {deleted} old watch history records.')
```

### 11.3 Khởi Chạy Celery

```powershell
# Terminal 3: Celery Worker
uv run celery -A config worker --loglevel=info --concurrency=4 -P gevent

# Terminal 4: Celery Beat (Scheduler)
uv run celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Terminal 5: Flower (Monitoring UI)
uv run celery -A config flower --port=5555
# Truy cập: http://localhost:5555
```

---

## 12. Video Processing Pipeline

### 12.1 Luồng Xử Lý

```
Admin upload .mp4
  → Django Admin trigger Celery task: process_video_file.delay()
    → Celery Worker nhận task
      → FFmpeg encode HLS (multi-quality)
        → .m3u8 + .ts segments lưu vào media/hls_streams/<ep_id>/
          → Update DB: m3u8_path, duration
            → Invalidate Redis cache cho movie
              → CDN sync (nếu dùng S3)
```

### 12.2 FFmpeg Encoder

```python
# video_processor/processor.py
import subprocess
import os
from pathlib import Path
from rich.console import Console

console = Console()


def encode_to_hls(input_path: str, episode_id: int) -> dict:
    """
    Encode MP4 → HLS (480p, 720p, 1080p) + master playlist.
    """
    output_dir = Path(f'media/hls_streams/{episode_id}')
    output_dir.mkdir(parents=True, exist_ok=True)

    qualities = [
        # (height, bitrate, bandwidth)
        ('480',  '1000k',  '1200000'),
        ('720',  '2500k',  '3000000'),
        ('1080', '5000k',  '6000000'),
    ]

    # ── Encode từng quality ──────────────────────────────────
    for height, bitrate, _ in qualities:
        output = output_dir / f'{height}p.m3u8'
        cmd = [
            'ffmpeg', '-i', input_path,
            '-vf',    f'scale=-2:{height}',
            '-c:v',   'libx264', '-crf', '23', '-preset', 'fast',
            '-b:v',   bitrate,   '-maxrate', bitrate, '-bufsize', f'{int(bitrate[:-1])*2}k',
            '-c:a',   'aac', '-b:a', '128k', '-ac', '2',
            '-hls_time', '6',
            '-hls_playlist_type', 'vod',
            '-hls_segment_filename', str(output_dir / f'{height}p_%04d.ts'),
            str(output),
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f'FFmpeg failed: {result.stderr.decode()}')
        console.print(f'[green]✓ Encoded {height}p[/green]')

    # ── Tạo Master Playlist ──────────────────────────────────
    master = output_dir / 'master.m3u8'
    with open(master, 'w') as f:
        f.write('#EXTM3U\n#EXT-X-VERSION:3\n')
        for height, _, bandwidth in qualities:
            f.write(f'#EXT-X-STREAM-INF:BANDWIDTH={bandwidth},'
                    f'RESOLUTION={"1920x1080" if height=="1080" else "1280x720" if height=="720" else "854x480"},'
                    f'CODECS="avc1.42e01e,mp4a.40.2"\n')
            f.write(f'{height}p.m3u8\n')

    # ── Lấy duration ────────────────────────────────────────
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_format', input_path
    ], capture_output=True)
    import json
    info     = json.loads(probe.stdout)
    duration = float(info['format'].get('duration', 0))

    return {
        'm3u8_path':        f'hls_streams/{episode_id}/master.m3u8',
        'duration_minutes': int(duration / 60),
    }
```

---

## 13. CDN Integration

### 13.1 Cấu Hình S3-Compatible Storage

```python
# config/settings/production.py (CDN section)
# Tương thích: AWS S3, Cloudflare R2, MinIO, DigitalOcean Spaces

DEFAULT_FILE_STORAGE  = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE   = 'storages.backends.s3boto3.S3StaticStorage'

AWS_ACCESS_KEY_ID      = env('CDN_ACCESS_KEY')
AWS_SECRET_ACCESS_KEY  = env('CDN_SECRET_KEY')
AWS_STORAGE_BUCKET_NAME = env('CDN_BUCKET_NAME')
AWS_S3_ENDPOINT_URL    = env('CDN_ENDPOINT_URL')       # Cloudflare R2: https://<id>.r2.cloudflarestorage.com
AWS_S3_CUSTOM_DOMAIN   = env('CDN_CUSTOM_DOMAIN')      # cdn.filmsite.com
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=604800',   # 7 ngày cho media
}
AWS_DEFAULT_ACL = 'public-read'
AWS_QUERYSTRING_AUTH = False

MEDIA_URL  = f'https://{AWS_S3_CUSTOM_DOMAIN}/media/'
STATIC_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/static/'
```

### 13.2 Upload HLS lên CDN

```python
# video_processor/processor.py — thêm bước upload
import boto3

def upload_hls_to_cdn(episode_id: int):
    """Upload toàn bộ HLS files lên S3-compatible CDN."""
    from django.conf import settings
    local_dir = Path(f'media/hls_streams/{episode_id}')
    s3 = boto3.client(
        's3',
        endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    for file in local_dir.rglob('*'):
        if file.is_file():
            key = f'media/hls_streams/{episode_id}/{file.name}'
            content_type = 'application/x-mpegURL' if file.suffix == '.m3u8' else 'video/MP2T'
            s3.upload_file(
                str(file), settings.AWS_STORAGE_BUCKET_NAME, key,
                ExtraArgs={'ContentType': content_type, 'ACL': 'public-read'}
            )
    console.print(f'[green]✓ HLS uploaded to CDN: episode_id={episode_id}[/green]')
```

### 13.3 Development (Local) vs Production (CDN)

| Môi trường | Media storage | Static storage | m3u8 URL |
|------------|---------------|----------------|----------|
| Development | `media/` local | `static/` local | `/media/hls_streams/<id>/master.m3u8` |
| Production | S3/R2 bucket | S3/R2 bucket | `https://cdn.filmsite.com/media/hls_streams/<id>/master.m3u8` |

---

## 14. Django Models — Code Đầy Đủ

### 14.1 Films Models

```python
# apps/films/models.py
from django.db import models
from django.utils.text import slugify


class MediumType(models.TextChoices):
    MOVIE       = 'Movie',       'Phim lẻ'
    SERIES      = 'Series',      'Phim bộ'
    ANIME       = 'Anime',       'Anime'
    ANIME_MOVIE = 'Anime Movie', 'Anime Movie'
    OVA         = 'OVA',         'OVA'
    SPECIAL     = 'Special',     'Special'
    DOCUMENTARY = 'Documentary', 'Phim tài liệu'
    SHORT_FILM  = 'Short Film',  'Phim ngắn'
    MINI_SERIES = 'Mini-Series', 'Mini-Series'
    TV_MOVIE    = 'TV Movie',    'TV Movie'


class ContentStatus(models.TextChoices):
    ONGOING   = 'Ongoing',   'Đang chiếu'
    COMPLETED = 'Completed', 'Hoàn thành'
    UPCOMING  = 'Upcoming',  'Sắp chiếu'
    HIATUS    = 'Hiatus',    'Tạm dừng'
    CANCELLED = 'Cancelled', 'Đã hủy'
    UNKNOWN   = 'Unknown',   'Không rõ'


class Genre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    class Meta: db_table = 'genres'; ordering = ['name']
    def __str__(self): return self.name


class Tag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    class Meta: db_table = 'tags'
    def __str__(self): return self.name


class Country(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=3, unique=True)  # ISO 3166
    flag = models.CharField(max_length=10, blank=True)  # Emoji flag
    class Meta: db_table = 'countries'; ordering = ['name']
    def __str__(self): return self.name


class Studio(models.Model):
    name       = models.CharField(max_length=255, unique=True)
    slug       = models.SlugField(unique=True)
    logo_path  = models.CharField(max_length=500, blank=True)
    founded_year = models.IntegerField(null=True, blank=True)
    class Meta: db_table = 'studios'
    def __str__(self): return self.name


class Person(models.Model):
    full_name     = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    slug          = models.SlugField(unique=True)
    avatar_path   = models.CharField(max_length=500, blank=True)
    bio           = models.TextField(blank=True)
    birth_date    = models.DateField(null=True, blank=True)
    nationality   = models.CharField(max_length=100, blank=True)
    tmdb_id       = models.IntegerField(null=True, blank=True, unique=True)
    class Meta: db_table = 'people'
    def __str__(self): return self.full_name


class Movie(models.Model):
    # ── Core ──────────────────────────────────────────────────
    title          = models.CharField(max_length=500)
    original_title = models.CharField(max_length=500, blank=True)
    slug           = models.SlugField(max_length=600, unique=True)
    synopsis       = models.TextField(blank=True)
    medium_type    = models.CharField(max_length=20, choices=MediumType.choices,
                                      default=MediumType.MOVIE)
    status         = models.CharField(max_length=20, choices=ContentStatus.choices,
                                      default=ContentStatus.UNKNOWN)
    release_year   = models.IntegerField(null=True, blank=True)
    content_rating = models.CharField(max_length=10, blank=True)

    # ── External IDs ──────────────────────────────────────────
    tmdb_id     = models.IntegerField(null=True, blank=True, unique=True)
    imdb_id     = models.CharField(max_length=20, blank=True)
    mal_id      = models.IntegerField(null=True, blank=True)
    imdb_rating = models.DecimalField(max_digits=3, decimal_places=1,
                                      null=True, blank=True)

    # ── User Ratings (denormalized) ───────────────────────────
    avg_rating   = models.DecimalField(max_digits=4, decimal_places=2,
                                       null=True, blank=True)
    rating_count = models.IntegerField(default=0)

    # ── Media paths ───────────────────────────────────────────
    poster_path   = models.CharField(max_length=500, blank=True)
    backdrop_path = models.CharField(max_length=500, blank=True)
    thumbnail_path= models.CharField(max_length=500, blank=True)

    # ── Flags ────────────────────────────────────────────────
    is_featured = models.BooleanField(default=False)
    is_hidden   = models.BooleanField(default=False)
    view_count  = models.BigIntegerField(default=0)

    # ── Self-ref (OVA, Special) ───────────────────────────────
    parent_movie = models.ForeignKey('self', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='children')

    # ── M2M ──────────────────────────────────────────────────
    genres    = models.ManyToManyField(Genre,   through='MovieGenre',    blank=True)
    tags      = models.ManyToManyField(Tag,     through='MovieTag',      blank=True)
    countries = models.ManyToManyField(Country, through='MovieCountry',  blank=True)
    cast_crew = models.ManyToManyField(Person,  through='MovieCastCrew', blank=True)
    studios   = models.ManyToManyField(Studio,  through='MovieStudio',   blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'movies'
        ordering = ['-created_at']
        indexes  = [
            models.Index(fields=['slug'],                    name='idx_movie_slug'),
            models.Index(fields=['medium_type', 'status'],  name='idx_movie_type'),
            models.Index(fields=['release_year'],            name='idx_movie_year'),
            models.Index(fields=['imdb_rating'],             name='idx_movie_imdb'),
            models.Index(fields=['avg_rating'],              name='idx_movie_avgrating'),
            models.Index(fields=['is_hidden', 'is_featured'],name='idx_movie_flags'),
            models.Index(fields=['view_count'],              name='idx_movie_views'),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f'{self.title}-{self.release_year}' if self.release_year else self.title
            self.slug = slugify(base)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.title} ({self.release_year})'


# ── M2M Through Tables ─────────────────────────────────────────
class MovieGenre(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genre, on_delete=models.CASCADE)
    class Meta: db_table = 'movie_genres'; unique_together = ('movie', 'genre')

class MovieTag(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE)
    tag   = models.ForeignKey(Tag,   on_delete=models.CASCADE)
    class Meta: db_table = 'movie_tags'; unique_together = ('movie', 'tag')

class MovieCountry(models.Model):
    movie   = models.ForeignKey(Movie,   on_delete=models.CASCADE)
    country = models.ForeignKey(Country, on_delete=models.CASCADE)
    class Meta: db_table = 'movie_countries'; unique_together = ('movie', 'country')

class MovieCastCrew(models.Model):
    ROLES = [
        ('Director',    'Đạo diễn'),
        ('Cast',        'Diễn viên'),
        ('Screenwriter','Biên kịch'),
        ('Producer',    'Nhà sản xuất'),
        ('Composer',    'Nhạc sĩ'),
        ('Editor',      'Dựng phim'),
        ('Voice Actor', 'Lồng tiếng'),
        ('Cinematographer', 'Quay phim'),
        ('Visual Effects Supervisor', 'VFX'),
    ]
    movie          = models.ForeignKey(Movie,  on_delete=models.CASCADE)
    person         = models.ForeignKey(Person, on_delete=models.CASCADE)
    role           = models.CharField(max_length=40, choices=ROLES)
    character_name = models.CharField(max_length=255, blank=True)
    sort_order     = models.IntegerField(default=0)
    class Meta: db_table = 'movie_cast_crew'; ordering = ['sort_order']

class MovieStudio(models.Model):
    movie  = models.ForeignKey(Movie,  on_delete=models.CASCADE)
    studio = models.ForeignKey(Studio, on_delete=models.CASCADE)
    role   = models.CharField(max_length=20, default='Production')
    class Meta: db_table = 'movie_studios'; unique_together = ('movie', 'studio')


class Episode(models.Model):
    movie          = models.ForeignKey(Movie, on_delete=models.CASCADE,
                                       related_name='episodes')
    season_number  = models.IntegerField(default=1)
    episode_number = models.IntegerField()
    episode_name   = models.CharField(max_length=255, blank=True)
    description    = models.TextField(blank=True)
    m3u8_path      = models.CharField(max_length=500, blank=True)
    movie_file_path= models.CharField(max_length=500, blank=True)
    thumbnail_path = models.CharField(max_length=500, blank=True)
    duration       = models.IntegerField(null=True, blank=True)  # phút
    air_date       = models.DateField(null=True, blank=True)
    view_count     = models.BigIntegerField(default=0)
    is_free        = models.BooleanField(default=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table     = 'episodes'
        ordering     = ['season_number', 'episode_number']
        unique_together = ('movie', 'season_number', 'episode_number')

    def __str__(self):
        return f'{self.movie.title} S{self.season_number:02d}E{self.episode_number:02d}'


class Subtitle(models.Model):
    episode        = models.ForeignKey(Episode, on_delete=models.CASCADE,
                                       related_name='subtitles')
    language_code  = models.CharField(max_length=10)
    language_label = models.CharField(max_length=50, blank=True)
    sub_path       = models.CharField(max_length=500)
    format         = models.CharField(max_length=5,
                                      choices=[('vtt','VTT'),('srt','SRT'),('ass','ASS')],
                                      default='vtt')
    is_default     = models.BooleanField(default=False)
    class Meta: db_table = 'subtitles'

    def __str__(self):
        return f'{self.episode} — {self.language_label}'


class Trailer(models.Model):
    movie      = models.ForeignKey(Movie, on_delete=models.CASCADE,
                                   related_name='trailers')
    trailer_path = models.CharField(max_length=500)
    label      = models.CharField(max_length=30, default='Official Trailer')
    language   = models.CharField(max_length=10, default='vi')
    sort_order = models.IntegerField(default=0)
    class Meta: db_table = 'trailers'; ordering = ['sort_order']
```

---

## 15. Settings & Configuration

### 15.1 .env File

```dotenv
# .env — KHÔNG commit lên git

# Django
SECRET_KEY=your-very-long-django-secret-key-here
JWT_SECRET_KEY=your-jwt-signing-key-different-from-django-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,192.168.1.100
SITE_URL=http://localhost:8000

# Database
DATABASE_URL=postgres://film_user:password@localhost:5432/filmsite_db
DB_USER=film_user
DB_PASSWORD=password
DB_NAME=filmsite_db

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# Email (SMTP)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=app-password
DEFAULT_FROM_EMAIL=noreply@filmsite.local

# CDN (Production)
CDN_ACCESS_KEY=
CDN_SECRET_KEY=
CDN_BUCKET_NAME=filmsite-media
CDN_ENDPOINT_URL=
CDN_CUSTOM_DOMAIN=

# Sentry (Production)
SENTRY_DSN=

# Backup
BACKUP_DIR=C:\Backups\filmsite
```

### 15.2 Base Settings

```python
# config/settings/base.py
from decouple import config as env, Csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY       = env('SECRET_KEY')
DEBUG            = env('DEBUG', cast=bool, default=False)
ALLOWED_HOSTS    = env('ALLOWED_HOSTS', cast=Csv())

INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',
    'django_celery_beat',
    'django_celery_results',
    'django_prometheus',
    'axes',
    # Local apps
    'apps.films',
    'apps.users',
    'apps.comments',
    'apps.ratings',
    'apps.history',
    'apps.watchlist',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'axes.middleware.AxesMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF    = 'config.urls'
AUTH_USER_MODEL = 'users.CustomUser'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME':   env('DB_NAME'),
        'USER':   env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST':   env('DB_HOST', default='localhost'),
        'PORT':   env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,  # Persistent connections
        'OPTIONS': {
            'connect_timeout': 10,
        },
    }
}

LANGUAGE_CODE  = 'vi'
TIME_ZONE      = 'Asia/Ho_Chi_Minh'
USE_I18N       = True
USE_TZ         = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/django.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {'handlers': ['file'], 'level': 'WARNING', 'propagate': False},
        'celery': {'handlers': ['file'], 'level': 'INFO',    'propagate': False},
    },
}
```

---

## 16. Caddy Reverse Proxy

### 16.1 Caddyfile Hoàn Chỉnh

```caddyfile
# C:\Caddy\Caddyfile
localhost:80, 192.168.1.x:80 {

    # ── Security Headers ────────────────────────────────────
    header {
        X-Content-Type-Options     "nosniff"
        X-Frame-Options            "SAMEORIGIN"
        X-XSS-Protection           "1; mode=block"
        Referrer-Policy            "strict-origin-when-cross-origin"
        Permissions-Policy         "geolocation=(), camera=(), microphone=()"
        Content-Security-Policy    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; media-src 'self' https:;"
        -Server
        -X-Powered-By
    }

    # ── Rate Limiting (Caddy built-in) ──────────────────────
    # Giới hạn 60 req/min per IP cho /api/v1/auth/
    @auth_endpoints path /api/v1/auth/*
    handle @auth_endpoints {
        # Forward, Django tự throttle qua DRF
        reverse_proxy localhost:8000
    }

    # ── Static Files (CSS, JS, Fonts) ───────────────────────
    route /static/* {
        header Cache-Control "public, max-age=86400, stale-while-revalidate=3600"
        file_server { root C:\Projects\filmsite }
    }

    # ── Media Files (HLS, Posters) ──────────────────────────
    route /media/* {
        @m3u8 path *.m3u8
        header @m3u8 Cache-Control "no-cache, no-store, must-revalidate"

        @ts path *.ts
        header @ts Cache-Control "public, max-age=604800, immutable"

        @vtt path *.vtt
        header @vtt Cache-Control "public, max-age=86400"

        @img path *.webp *.jpg *.png
        header @img Cache-Control "public, max-age=604800, immutable"

        file_server { root C:\Projects\filmsite }
    }

    # ── Metrics (nội bộ) ─────────────────────────────────────
    @metrics path /metrics
    handle @metrics {
        reverse_proxy localhost:8000
    }

    # ── Django App ──────────────────────────────────────────
    reverse_proxy localhost:8000 {
        header_up X-Forwarded-For   {remote_host}
        header_up X-Forwarded-Proto {scheme}
        header_up X-Real-IP         {remote_host}
        transport http {
            read_timeout  30s
            write_timeout 30s
        }
    }

    # ── Gzip Compression ────────────────────────────────────
    encode gzip

    # ── Logging ─────────────────────────────────────────────
    log {
        output file C:\Caddy\access.log {
            roll_size 10mb
            roll_keep 5
        }
        format json
    }
}
```

---

## 17. Security Hardening

### 17.1 Django Security Settings

```python
# config/settings/production.py
from .base import *

DEBUG = False

# ── HTTPS ────────────────────────────────────────────────────
SECURE_SSL_REDIRECT          = True
SECURE_HSTS_SECONDS          = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD          = True
SECURE_PROXY_SSL_HEADER      = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_CONTENT_TYPE_NOSNIFF  = True
SECURE_BROWSER_XSS_FILTER    = True

# ── Cookies ──────────────────────────────────────────────────
SESSION_COOKIE_SECURE        = True
SESSION_COOKIE_HTTPONLY      = True
SESSION_COOKIE_SAMESITE      = 'Lax'
CSRF_COOKIE_SECURE           = True
CSRF_COOKIE_HTTPONLY         = True
CSRF_COOKIE_SAMESITE         = 'Lax'
SESSION_COOKIE_AGE           = 3600 * 24 * 7   # 7 ngày

# ── CORS ─────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'https://filmsite.com',
]
CORS_ALLOW_CREDENTIALS = True

# ── Brute-Force Protection (django-axes) ──────────────────────
AXES_FAILURE_LIMIT      = 5      # Khóa sau 5 lần sai
AXES_COOLOFF_TIME       = 1      # Mở khóa sau 1 giờ
AXES_LOCK_OUT_BY_COMBINATION_USER_AND_IP = True
AXES_RESET_ON_SUCCESS   = True
AUTHENTICATION_BACKENDS = [
    'axes.backends.AxesStandaloneBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# ── File Upload ───────────────────────────────────────────────
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024    # 5MB form fields
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# ── Content Validation ────────────────────────────────────────
ALLOWED_UPLOAD_EXTENSIONS = ['.mp4', '.mkv', '.avi', '.mov']
ALLOWED_IMAGE_EXTENSIONS  = ['.jpg', '.jpeg', '.png', '.webp']
```

### 17.2 Input Validation

```python
# apps/films/admin.py — Validate file upload
import os
from django.core.exceptions import ValidationError


def validate_video_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.mp4', '.mkv', '.avi', '.mov']:
        raise ValidationError(f'Định dạng không hỗ trợ: {ext}')


def validate_image_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.jpg', '.jpeg', '.png', '.webp']:
        raise ValidationError(f'Phải là ảnh JPG/PNG/WebP.')
```

### 17.3 Rate Limiting Chi Tiết

```python
# apps/users/api/throttles.py
from rest_framework.throttling import ScopedRateThrottle


class AuthThrottle(ScopedRateThrottle):
    scope = 'auth'       # 10/min — Login, Register, Forgot Password

class CommentThrottle(ScopedRateThrottle):
    scope = 'comment'    # 20/min — Post Comment

class SearchThrottle(ScopedRateThrottle):
    scope = 'search'     # 30/min — Search API
```

### 17.4 SQL Injection Prevention

```python
# Luôn dùng ORM, KHÔNG dùng raw SQL tùy tiện
# Nếu cần raw SQL:
from django.db import connection

# ĐÚNG — parameterized query
with connection.cursor() as cursor:
    cursor.execute("SELECT * FROM movies WHERE slug = %s", [slug])

# SAI — dễ bị SQL injection
# cursor.execute(f"SELECT * FROM movies WHERE slug = '{slug}'")
```

### 17.5 Dependency Audit

```bash
# Kiểm tra vulnerabilities hàng tuần
uv run pip-audit

# Hoặc dùng safety
uv add --dev safety
uv run safety check
```

---

## 18. Load Testing — Locust

### 18.1 Locustfile

```python
# tests/locustfile.py
from locust import HttpUser, task, between
import random


MOVIE_SLUGS = ['avengers-endgame-2019', 'spirited-away-2001', 'parasite-2019']


class AnonymousUser(HttpUser):
    """Simulate khách chưa đăng nhập."""
    wait_time = between(1, 3)

    @task(5)
    def browse_home(self):
        self.client.get('/api/v1/films/movies/')

    @task(3)
    def view_movie_detail(self):
        slug = random.choice(MOVIE_SLUGS)
        self.client.get(f'/api/v1/films/movies/{slug}/')

    @task(2)
    def search_movie(self):
        self.client.get('/api/v1/films/movies/?search=anime')

    @task(1)
    def get_trending(self):
        self.client.get('/api/v1/films/movies/trending/')


class AuthenticatedUser(HttpUser):
    """Simulate user đã đăng nhập."""
    wait_time = between(2, 5)
    token     = None

    def on_start(self):
        """Login và lưu JWT token."""
        resp = self.client.post('/api/v1/auth/login/', json={
            'email':    'test@filmsite.com',
            'password': 'testpass123',
        })
        if resp.status_code == 200:
            self.token = resp.json()['access']

    def get_headers(self):
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    @task(3)
    def view_movie(self):
        slug = random.choice(MOVIE_SLUGS)
        self.client.get(f'/api/v1/films/movies/{slug}/', headers=self.get_headers())

    @task(2)
    def update_watch_progress(self):
        self.client.post('/api/v1/history/1/', json={
            'progress_seconds': random.randint(0, 3600),
            'duration_seconds': 7200,
        }, headers=self.get_headers())

    @task(1)
    def post_comment(self):
        self.client.post(f'/api/v1/films/movies/{MOVIE_SLUGS[0]}/comments/', json={
            'body': 'Phim hay quá! Recommend mọi người xem thử.',
        }, headers=self.get_headers())

    @task(1)
    def rate_movie(self):
        slug = random.choice(MOVIE_SLUGS)
        self.client.post(f'/api/v1/films/movies/{slug}/rating/', json={
            'score': random.randint(6, 10),
        }, headers=self.get_headers())
```

### 18.2 Chạy Load Test

```bash
# Chạy Locust Web UI
uv run locust -f tests/locustfile.py --host http://localhost:8000

# Truy cập: http://localhost:8089
# Cấu hình: 50 users, spawn rate 5/s, chạy 5 phút

# Chạy headless (CI/CD)
uv run locust -f tests/locustfile.py \
  --host http://localhost:8000 \
  --users 50 --spawn-rate 5 \
  --run-time 5m --headless \
  --csv reports/load_test
```

### 18.3 Targets

| Metric | Target | Action nếu fail |
|--------|--------|-----------------|
| Avg response time | < 200ms | Thêm cache |
| 95th percentile | < 500ms | Optimize query |
| Error rate | < 1% | Check logs |
| Requests/sec | > 100 | Scale workers |

---

## 19. Monitoring — Prometheus + Grafana

### 19.1 Setup

```powershell
# Dùng Docker Compose (dev) hoặc cài thủ công
# monitoring/docker-compose.yml
```

```yaml
# monitoring/docker-compose.yml
version: '3.8'
services:
  prometheus:
    image: prom/prometheus:latest
    ports: ["9090:9090"]
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports: ["3000:3000"]
    environment:
      GF_SECURITY_ADMIN_PASSWORD: admin123
    volumes:
      - grafana_data:/var/lib/grafana
      - ./grafana/dashboards:/etc/grafana/provisioning/dashboards

volumes:
  grafana_data:
```

### 19.2 Prometheus Config

```yaml
# monitoring/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'filmsite-django'
    static_configs:
      - targets: ['host.docker.internal:8000']
    metrics_path: '/metrics'

  - job_name: 'celery'
    static_configs:
      - targets: ['host.docker.internal:5555']
    metrics_path: '/metrics'

  - job_name: 'redis'
    static_configs:
      - targets: ['host.docker.internal:9121']  # redis_exporter
```

### 19.3 Django Metrics Endpoint

```python
# config/urls.py
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('metrics', include('django_prometheus.urls')),  # /metrics
    path('api/v1/', include('config.api_urls')),
    # ...
]
```

### 19.4 Sentry Error Tracking

```python
# config/settings/production.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.redis  import RedisIntegration

sentry_sdk.init(
    dsn=env('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(transaction_style='url'),
        CeleryIntegration(),
        RedisIntegration(),
    ],
    traces_sample_rate=0.1,    # 10% transactions
    profiles_sample_rate=0.05, # 5% profiling
    send_default_pii=False,
)
```

### 19.5 Metrics Quan Trọng Cần Theo Dõi

| Metric | Grafana Panel | Alert khi |
|--------|---------------|-----------|
| `django_http_requests_total` | Request rate | > 1000/min |
| `django_http_requests_latency_seconds` | P95 latency | > 500ms |
| `django_db_errors_total` | DB errors | > 0 |
| `celery_tasks_total` | Task throughput | — |
| `celery_task_failed_total` | Failed tasks | > 5 |
| `redis_connected_clients` | Redis clients | > 100 |
| `process_resident_memory_bytes` | Memory | > 512MB |

---

## 20. Deployment & Automation

### 20.1 Gunicorn (thay Waitress)

```python
# gunicorn.conf.py
import multiprocessing

bind            = '127.0.0.1:8000'
workers         = multiprocessing.cpu_count() * 2 + 1
worker_class    = 'sync'
worker_connections = 1000
timeout         = 30
keepalive       = 5
max_requests    = 1000       # Restart worker sau 1000 requests (chống memory leak)
max_requests_jitter = 100
preload_app     = True
accesslog       = 'logs/access.log'
errorlog        = 'logs/gunicorn.log'
loglevel        = 'info'
```

```powershell
# scripts/start_gunicorn.bat
@echo off
cd C:\Projects\filmsite
call .venv\Scripts\activate.bat
uv run gunicorn config.wsgi:application -c gunicorn.conf.py
```

### 20.2 Task Scheduler — Windows

```powershell
# scripts/setup_tasks.ps1 (chạy với quyền Admin)
$base = "C:\Projects\filmsite"

# Django (Gunicorn)
$a1 = New-ScheduledTaskAction -Execute "$base\scripts\start_gunicorn.bat"
Register-ScheduledTask -TaskName "FilmSite-Gunicorn" `
    -Action $a1 `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings (New-ScheduledTaskSettingsSet -RestartCount 5 -RestartInterval (New-TimeSpan -Minutes 2)) `
    -RunLevel Highest

# Caddy
$a2 = New-ScheduledTaskAction -Execute "C:\Caddy\caddy.exe" -Argument "run" -WorkingDirectory "C:\Caddy"
Register-ScheduledTask -TaskName "FilmSite-Caddy" `
    -Action $a2 `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings (New-ScheduledTaskSettingsSet -RestartCount 5) `
    -RunLevel Highest

# Celery Worker
$a3 = New-ScheduledTaskAction -Execute "$base\scripts\start_celery.bat"
Register-ScheduledTask -TaskName "FilmSite-Celery" `
    -Action $a3 `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings (New-ScheduledTaskSettingsSet -RestartCount 5) `
    -RunLevel Highest

# Celery Beat
$a4 = New-ScheduledTaskAction -Execute "$base\scripts\start_celery_beat.bat"
Register-ScheduledTask -TaskName "FilmSite-Beat" `
    -Action $a4 `
    -Trigger (New-ScheduledTaskTrigger -AtStartup) `
    -Settings (New-ScheduledTaskSettingsSet -RestartCount 3) `
    -RunLevel Highest

Write-Host "All tasks registered successfully!" -ForegroundColor Green
```

### 20.3 .bat Scripts

```batch
:: scripts/start_celery.bat
@echo off
cd C:\Projects\filmsite
call .venv\Scripts\activate.bat
uv run celery -A config worker --loglevel=info --concurrency=4 -P gevent

:: scripts/start_celery_beat.bat
@echo off
cd C:\Projects\filmsite
call .venv\Scripts\activate.bat
uv run celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### 20.4 Setup Commands (First Time)

```powershell
# 1. Clone và cài dependencies
git clone <repo> C:\Projects\filmsite
cd C:\Projects\filmsite
uv sync

# 2. Tạo DB
psql -U postgres -c "CREATE DATABASE filmsite_db;"
psql -U postgres -c "CREATE USER film_user WITH PASSWORD 'yourpassword';"
psql -U postgres -c "GRANT ALL ON DATABASE filmsite_db TO film_user;"

# 3. Migrate
uv run python manage.py migrate
uv run python manage.py createsuperuser

# 4. Collect static
uv run python manage.py collectstatic --no-input

# 5. Load initial data (genres, countries)
uv run python manage.py loaddata apps/films/fixtures/initial_data.json

# 6. Test
uv run pytest --cov=. -v
```

---

## 21. Backup & Maintenance

### 21.1 Backup Script

```batch
:: scripts/backup_db.bat — Chạy hàng ngày qua Task Scheduler
@echo off
SET PGPASSWORD=%DB_PASSWORD%
SET BACKUP_DIR=C:\Backups\filmsite
SET DATE_STR=%date:~10,4%-%date:~4,2%-%date:~7,2%

IF NOT EXIST "%BACKUP_DIR%" MKDIR "%BACKUP_DIR%"

"C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" ^
    -U film_user -d filmsite_db ^
    -F c ^
    -f "%BACKUP_DIR%\filmsite_%DATE_STR%.backup"

:: Xóa backup cũ hơn 30 ngày
forfiles /P "%BACKUP_DIR%" /S /M *.backup /D -30 /C "cmd /c del @path" 2>nul

echo Backup done: filmsite_%DATE_STR%.backup
```

### 21.2 Database Maintenance

```sql
-- Chạy hàng tuần để optimize
VACUUM ANALYZE movies;
VACUUM ANALYZE episodes;
VACUUM ANALYZE watch_history;
VACUUM ANALYZE ratings;
VACUUM ANALYZE comments;

-- Reindex nếu cần
REINDEX TABLE movies;
```

### 21.3 Redis Maintenance

```bash
# Xem memory usage
redis-cli info memory

# Xóa cache cũ nếu đầy
redis-cli FLUSHDB  # CẢNH BÁO: Xóa toàn bộ DB

# Monitor real-time
redis-cli monitor
```

---

## 22. Checklist Hoàn Chỉnh

### Phase 0 — Môi Trường
- [ ] Cài uv: `irm https://astral.sh/uv/install.ps1 | iex`
- [ ] `uv init filmsite --python 3.12`
- [ ] Tạo `pyproject.toml` theo mẫu
- [ ] `uv sync` — cài toàn bộ dependencies
- [ ] Tạo file `.env` từ `.env.example`
- [ ] Cài PostgreSQL 16, tạo DB và user
- [ ] Cài Redis (Docker hoặc WSL2)
- [ ] Cài FFmpeg, thêm vào PATH

### Phase 1 — Database
- [ ] Tạo đủ 22 models
- [ ] `uv run python manage.py makemigrations`
- [ ] `uv run python manage.py migrate`
- [ ] Verify: `\dt` trong psql thấy đủ bảng
- [ ] Load fixtures: genres, countries, studios

### Phase 2 — Auth
- [ ] CustomUser model với email login
- [ ] JWT endpoints: register, login, logout, refresh
- [ ] Email verification flow (Celery task)
- [ ] Brute-force protection (django-axes)
- [ ] Test: đăng ký, login, token refresh

### Phase 3 — REST API
- [ ] MovieViewSet với filter, search, ordering
- [ ] Cache cho movie detail (10 phút)
- [ ] Redis Sorted Set cho trending
- [ ] OpenAPI/Swagger docs hoạt động
- [ ] Test API bằng Postman hoặc curl

### Phase 4 — Comments & Ratings
- [ ] Comment model + nested replies
- [ ] CommentLike (like/dislike)
- [ ] Rating model + signal tự update avg_rating
- [ ] Rate limiting: 20 comments/min, 10 ratings/min
- [ ] Test: tạo comment, reply, like, rate

### Phase 5 — Watch History
- [ ] WatchHistory model với progress_seconds
- [ ] WatchlistItem model
- [ ] API: update progress mỗi 30 giây
- [ ] "Continue watching" endpoint
- [ ] Increment view_count khi xem > 90%

### Phase 6 — Redis & Celery
- [ ] Redis connect thành công (`redis-cli ping`)
- [ ] django-redis config
- [ ] Celery worker chạy: `uv run celery -A config worker`
- [ ] Celery Beat chạy, tasks chạy đúng schedule
- [ ] Flower UI tại localhost:5555

### Phase 7 — Video Processing
- [ ] FFmpeg encode HLS thành công (test với file nhỏ)
- [ ] process_video_file Celery task hoạt động
- [ ] Multi-quality: 480p, 720p, 1080p
- [ ] Master playlist đúng format
- [ ] Player phát được HLS

### Phase 8 — Caddy
- [ ] Caddy cài đặt, Caddyfile viết đúng
- [ ] `caddy validate` không lỗi
- [ ] Static files phục vụ qua Caddy
- [ ] HLS streams phục vụ với đúng Cache-Control
- [ ] Security headers xuất hiện trong response

### Phase 9 — Security
- [ ] Argon2 password hasher
- [ ] JWT secret key khác Django secret key
- [ ] CORS config đúng origins
- [ ] django-axes bảo vệ login
- [ ] File upload validate extension
- [ ] `uv run pip-audit` — không có critical vulnerabilities

### Phase 10 — Testing
- [ ] `uv run pytest` — tất cả tests pass
- [ ] Coverage > 70%
- [ ] `uv run locust` — load test với 50 users
- [ ] P95 response time < 500ms
- [ ] Error rate < 1%

### Phase 11 — Monitoring
- [ ] `django-prometheus` metrics tại `/metrics`
- [ ] Prometheus scrape thành công
- [ ] Grafana dashboard hiển thị request rate, latency
- [ ] Sentry DSN cấu hình (production)

### Phase 12 — Deployment
- [ ] Task Scheduler tất cả tasks đăng ký
- [ ] Auto-start khi Windows restart
- [ ] Backup DB task chạy hàng ngày
- [ ] Logs rotate đúng (`logs/django.log`)
- [ ] Từ điện thoại cùng WiFi mở site OK

---

## Phụ Lục — Biến Môi Trường Tổng Hợp

| Biến | Bắt buộc | Mô tả |
|------|----------|-------|
| `SECRET_KEY` | ✅ | Django secret key (50+ chars) |
| `JWT_SECRET_KEY` | ✅ | JWT signing key (khác SECRET_KEY) |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `REDIS_URL` | ✅ | Redis connection string |
| `DEBUG` | ✅ | True/False |
| `ALLOWED_HOSTS` | ✅ | Comma-separated |
| `SITE_URL` | ✅ | http(s)://domain |
| `EMAIL_HOST` | ⚠️ | SMTP server |
| `EMAIL_HOST_USER` | ⚠️ | SMTP email |
| `EMAIL_HOST_PASSWORD` | ⚠️ | SMTP password/app key |
| `CDN_ACCESS_KEY` | Production | S3 access key |
| `CDN_SECRET_KEY` | Production | S3 secret key |
| `CDN_BUCKET_NAME` | Production | S3 bucket name |
| `CDN_ENDPOINT_URL` | Production | S3 endpoint |
| `SENTRY_DSN` | Production | Sentry error tracking |
| `BACKUP_DIR` | ⚠️ | Path lưu backup DB |

---

*FilmSite Architecture Plan v2.0 — Cập nhật bởi Claude Sonnet 4*