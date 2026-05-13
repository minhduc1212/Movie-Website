# FilmSite — Kế Hoạch Kiến Trúc & Xây Dựng Hoàn Chỉnh (v2.1)

> **Stack:** Django 5 · PostgreSQL 16 · Redis 7 · Celery 5 · DRF · uv · pyproject.toml · Caddy · FFmpeg · HLS  
> **Phiên bản:** 2.1 — Đã review và fix 20+ bugs: Cache serialization, missing imports, incomplete views, DDL inconsistency, signals setup, LOGGING config, Markdown errors

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
23. [UI Frontend — Modern, Responsive, Beautiful](#23-ui-frontend--modern-responsive-beautiful)

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
│  CDN / Media │    │   Django (Waitress)  │
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
    → Còn lại → forward tới Waitress:8000
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
    "waitress>=3.0",             # Windows-compatible WSGI server
    "gevent>=24.2",              # Cho Celery pool (async workers)
    "greenlet>=3.0",             # Phụ thuộc của gevent trên Python 3.12+

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

# NOTE: [project.optional-dependencies].dev đã bị loại bỏ vì trùng lặp.
# Dùng uv add --dev <pkg> để thêm dev dependency — uv quản lý qua [tool.uv].dev-dependencies.

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
    ├── start_waitress.bat
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

### 4.3 Thiết Kế Chi Tiết — Tất Cả 22 Bảng

#### Nhóm 1: User & Auth

**Bảng `users`** — CustomUser (thay thế auth_user mặc định)

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `email` | `VARCHAR(254)` | NO | — | UNIQUE, dùng làm username |
| `password` | `VARCHAR(128)` | NO | — | Argon2 hash |
| `display_name` | `VARCHAR(100)` | YES | `''` | Tên hiển thị |
| `avatar` | `VARCHAR(100)` | YES | NULL | Đường dẫn file avatar |
| `is_verified` | `BOOLEAN` | NO | `FALSE` | Email đã xác nhận |
| `is_active` | `BOOLEAN` | NO | `TRUE` | Soft-delete tài khoản |
| `is_staff` | `BOOLEAN` | NO | `FALSE` | Truy cập Django Admin |
| `is_superuser` | `BOOLEAN` | NO | `FALSE` | Toàn quyền |
| `last_login` | `TIMESTAMPTZ` | YES | NULL | Cập nhật tự động khi login |
| `date_joined` | `TIMESTAMPTZ` | NO | `NOW()` | — |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |

Indexes: `UNIQUE(email)`, `INDEX(is_active, created_at)`

---

**Bảng `user_profiles`** — Thông tin mở rộng của user (1-1)

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `user_id` | `BIGINT` | NO | — | FK → users(id) CASCADE |
| `bio` | `TEXT` | YES | `''` | Giới thiệu bản thân, max 500 ký tự |
| `birth_date` | `DATE` | YES | NULL | — |
| `country` | `CHAR(3)` | YES | `''` | ISO 3166 alpha-3 |
| `preferred_language` | `VARCHAR(10)` | NO | `'vi'` | — |
| `notifications_email` | `BOOLEAN` | NO | `TRUE` | Nhận email thông báo |
| `notifications_reply` | `BOOLEAN` | NO | `TRUE` | Nhận email khi có reply |
| `total_watch_time` | `INT` | NO | `0` | Tổng số phút đã xem (denormalized) |
| `total_movies_watched` | `INT` | NO | `0` | Tổng số phim đã xem (denormalized) |

Indexes: `UNIQUE(user_id)`

---

#### Nhóm 2: Phim & Metadata

**Bảng `genres`** — Thể loại phim

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `SERIAL` | NO | auto | PK |
| `name` | `VARCHAR(100)` | NO | — | UNIQUE, VD: "Hành Động" |
| `slug` | `VARCHAR(100)` | NO | — | UNIQUE, VD: "hanh-dong" |

---

**Bảng `tags`** — Tag tùy chỉnh

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `SERIAL` | NO | auto | PK |
| `name` | `VARCHAR(100)` | NO | — | UNIQUE |
| `slug` | `VARCHAR(100)` | NO | — | UNIQUE |

---

**Bảng `countries`** — Quốc gia sản xuất

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `SERIAL` | NO | auto | PK |
| `name` | `VARCHAR(100)` | NO | — | VD: "Nhật Bản" |
| `code` | `CHAR(3)` | NO | — | UNIQUE, ISO 3166 alpha-3 |
| `flag` | `VARCHAR(10)` | YES | `''` | Emoji quốc kỳ: 🇯🇵 |

---

**Bảng `studios`** — Hãng sản xuất

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `SERIAL` | NO | auto | PK |
| `name` | `VARCHAR(255)` | NO | — | UNIQUE |
| `slug` | `VARCHAR(255)` | NO | — | UNIQUE |
| `logo_path` | `VARCHAR(500)` | YES | `''` | Đường dẫn ảnh logo |
| `founded_year` | `SMALLINT` | YES | NULL | Năm thành lập |

---

**Bảng `people`** — Diễn viên, đạo diễn, v.v.

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `full_name` | `VARCHAR(255)` | NO | — | Tên tiếng Việt |
| `original_name` | `VARCHAR(255)` | YES | `''` | Tên gốc (Nhật, Hàn, ...) |
| `slug` | `VARCHAR(300)` | NO | — | UNIQUE |
| `avatar_path` | `VARCHAR(500)` | YES | `''` | — |
| `bio` | `TEXT` | YES | `''` | — |
| `birth_date` | `DATE` | YES | NULL | — |
| `nationality` | `VARCHAR(100)` | YES | `''` | — |
| `tmdb_id` | `INT` | YES | NULL | UNIQUE, ID trên TMDB |

Indexes: `UNIQUE(slug)`, `UNIQUE(tmdb_id)`, `INDEX(full_name)`

---

**Bảng `movies`** — Bảng trung tâm của hệ thống

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `title` | `VARCHAR(500)` | NO | — | Tên tiếng Việt |
| `original_title` | `VARCHAR(500)` | YES | `''` | Tên gốc |
| `slug` | `VARCHAR(600)` | NO | — | UNIQUE, URL-friendly |
| `synopsis` | `TEXT` | YES | `''` | Tóm tắt nội dung |
| `medium_type` | `VARCHAR(20)` | NO | `'Movie'` | ENUM: Movie/Series/Anime/OVA/... |
| `status` | `VARCHAR(20)` | NO | `'Unknown'` | ENUM: Ongoing/Completed/Upcoming/... |
| `release_year` | `SMALLINT` | YES | NULL | Năm phát hành |
| `content_rating` | `VARCHAR(10)` | YES | `''` | VD: "PG-13", "R", "C18" |
| `tmdb_id` | `INT` | YES | NULL | UNIQUE |
| `imdb_id` | `VARCHAR(20)` | YES | `''` | VD: "tt1234567" |
| `mal_id` | `INT` | YES | NULL | MyAnimeList ID |
| `imdb_rating` | `NUMERIC(3,1)` | YES | NULL | VD: 8.5 |
| `avg_rating` | `NUMERIC(4,2)` | YES | NULL | Denormalized từ `ratings` |
| `rating_count` | `INT` | NO | `0` | Denormalized từ `ratings` |
| `poster_path` | `VARCHAR(500)` | YES | `''` | — |
| `backdrop_path` | `VARCHAR(500)` | YES | `''` | — |
| `thumbnail_path` | `VARCHAR(500)` | YES | `''` | — |
| `is_featured` | `BOOLEAN` | NO | `FALSE` | Hiển thị trang chủ |
| `is_hidden` | `BOOLEAN` | NO | `FALSE` | Ẩn khỏi người dùng |
| `view_count` | `BIGINT` | NO | `0` | Tổng lượt xem |
| `parent_movie_id` | `BIGINT` | YES | NULL | FK → movies(id) SET NULL (OVA/Special) |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | auto_now |

Indexes:
```
UNIQUE(slug)
UNIQUE(tmdb_id)
INDEX(medium_type, status)     -- idx_movie_type
INDEX(release_year)            -- idx_movie_year
INDEX(imdb_rating DESC)        -- idx_movie_imdb
INDEX(avg_rating DESC)         -- idx_movie_avgrating
INDEX(is_hidden, is_featured)  -- idx_movie_flags
INDEX(view_count DESC)         -- idx_movie_views
INDEX(created_at DESC)         -- default ordering
```

---

#### Nhóm 3: Bảng M2M (Many-to-Many)

**Bảng `movie_genres`**

| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGSERIAL` | PK |
| `movie_id` | `BIGINT` | FK → movies CASCADE |
| `genre_id` | `INT` | FK → genres CASCADE |

Constraint: `UNIQUE(movie_id, genre_id)`

---

**Bảng `movie_tags`**

| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGSERIAL` | PK |
| `movie_id` | `BIGINT` | FK → movies CASCADE |
| `tag_id` | `INT` | FK → tags CASCADE |

Constraint: `UNIQUE(movie_id, tag_id)`

---

**Bảng `movie_countries`**

| Cột | Kiểu | Ghi chú |
|-----|------|---------|
| `id` | `BIGSERIAL` | PK |
| `movie_id` | `BIGINT` | FK → movies CASCADE |
| `country_id` | `INT` | FK → countries CASCADE |

Constraint: `UNIQUE(movie_id, country_id)`

---

**Bảng `movie_cast_crew`**

| Cột | Kiểu | Nullable | Ghi chú |
|-----|------|----------|---------|
| `id` | `BIGSERIAL` | NO | PK |
| `movie_id` | `BIGINT` | NO | FK → movies CASCADE |
| `person_id` | `BIGINT` | NO | FK → people CASCADE |
| `role` | `VARCHAR(40)` | NO | ENUM: Director/Cast/Screenwriter/... |
| `character_name` | `VARCHAR(255)` | YES | Tên nhân vật (diễn viên) |
| `sort_order` | `SMALLINT` | NO | 0 |

Index: `INDEX(movie_id, role)`, `INDEX(person_id)`

---

**Bảng `movie_studios`**

| Cột | Kiểu | Nullable | Ghi chú |
|-----|------|----------|---------|
| `id` | `BIGSERIAL` | NO | PK |
| `movie_id` | `BIGINT` | NO | FK → movies CASCADE |
| `studio_id` | `INT` | NO | FK → studios CASCADE |
| `role` | `VARCHAR(20)` | NO | `'Production'` |

Constraint: `UNIQUE(movie_id, studio_id)`

---

#### Nhóm 4: Video & Media

**Bảng `episodes`** — Tập phim (cả phim lẻ lẫn phim bộ dùng chung)

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `movie_id` | `BIGINT` | NO | — | FK → movies CASCADE |
| `season_number` | `SMALLINT` | NO | `1` | Phim lẻ luôn = 1 |
| `episode_number` | `SMALLINT` | NO | — | Phim lẻ = 1 |
| `episode_name` | `VARCHAR(255)` | YES | `''` | — |
| `description` | `TEXT` | YES | `''` | — |
| `m3u8_path` | `VARCHAR(500)` | YES | `''` | Đường dẫn HLS master playlist |
| `movie_file_path` | `VARCHAR(500)` | YES | `''` | File gốc (raw .mp4) |
| `thumbnail_path` | `VARCHAR(500)` | YES | `''` | Ảnh thumbnail tập |
| `duration` | `SMALLINT` | YES | NULL | Thời lượng (phút) |
| `air_date` | `DATE` | YES | NULL | Ngày phát sóng |
| `view_count` | `BIGINT` | NO | `0` | — |
| `is_free` | `BOOLEAN` | NO | `TRUE` | Xem miễn phí hay cần VIP |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |

Constraints:
```
UNIQUE(movie_id, season_number, episode_number)
INDEX(movie_id, season_number, episode_number)
```

---

**Bảng `subtitles`** — Phụ đề per episode

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `episode_id` | `BIGINT` | NO | — | FK → episodes CASCADE |
| `language_code` | `VARCHAR(10)` | NO | — | VD: "vi", "en", "ja" |
| `language_label` | `VARCHAR(50)` | YES | `''` | VD: "Tiếng Việt" |
| `sub_path` | `VARCHAR(500)` | NO | — | Đường dẫn file .vtt/.srt |
| `format` | `VARCHAR(5)` | NO | `'vtt'` | ENUM: vtt/srt/ass |
| `is_default` | `BOOLEAN` | NO | `FALSE` | Auto-on khi load player |

Index: `INDEX(episode_id)`

---

**Bảng `trailers`** — Trailer phim

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `movie_id` | `BIGINT` | NO | — | FK → movies CASCADE |
| `trailer_path` | `VARCHAR(500)` | NO | — | URL hoặc local path |
| `label` | `VARCHAR(30)` | NO | `'Official Trailer'` | — |
| `language` | `VARCHAR(10)` | NO | `'vi'` | — |
| `sort_order` | `SMALLINT` | NO | `0` | — |

Index: `INDEX(movie_id, sort_order)`

---

#### Nhóm 5: User Activity

**Bảng `comments`** — Bình luận có nested reply

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `movie_id` | `BIGINT` | NO | — | FK → movies CASCADE |
| `user_id` | `BIGINT` | NO | — | FK → users CASCADE |
| `parent_id` | `BIGINT` | YES | NULL | FK → comments CASCADE (self-ref) |
| `body` | `TEXT` | NO | — | Nội dung bình luận |
| `is_spoiler` | `BOOLEAN` | NO | `FALSE` | Đánh dấu spoiler |
| `is_hidden` | `BOOLEAN` | NO | `FALSE` | Admin ẩn comment vi phạm |
| `like_count` | `INT` | NO | `0` | Denormalized từ comment_likes |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |

Indexes:
```
INDEX(movie_id, parent_id, created_at DESC)   -- Lấy top-level comments
INDEX(parent_id)                               -- Lấy replies
INDEX(user_id)                                 -- Comments của 1 user
```

---

**Bảng `comment_likes`** — Like/Dislike comment

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `comment_id` | `BIGINT` | NO | — | FK → comments CASCADE |
| `user_id` | `BIGINT` | NO | — | FK → users CASCADE |
| `value` | `SMALLINT` | NO | `1` | `1` = like, `-1` = dislike |

Constraint: `UNIQUE(comment_id, user_id)`

---

**Bảng `ratings`** — Đánh giá 1-10 sao

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `user_id` | `BIGINT` | NO | — | FK → users CASCADE |
| `movie_id` | `BIGINT` | NO | — | FK → movies CASCADE |
| `score` | `SMALLINT` | NO | — | CHECK(score BETWEEN 1 AND 10) |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |

Constraints: `UNIQUE(user_id, movie_id)`, `INDEX(movie_id)`

---

**Bảng `watch_history`** — Lịch sử xem & tiến độ resume

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `user_id` | `BIGINT` | NO | — | FK → users CASCADE |
| `episode_id` | `BIGINT` | NO | — | FK → episodes CASCADE |
| `progress_seconds` | `INT` | NO | `0` | Đã xem đến giây thứ N |
| `duration_seconds` | `INT` | NO | `0` | Tổng thời lượng (giây) |
| `completed` | `BOOLEAN` | NO | `FALSE` | Đã xem > 90% |
| `watched_at` | `TIMESTAMPTZ` | NO | `NOW()` | auto_now — cập nhật mỗi lần xem |

Constraints:
```
UNIQUE(user_id, episode_id)
INDEX(user_id, watched_at DESC)    -- Continue watching query
INDEX(episode_id)
```

---

**Bảng `watchlist_items`** — Danh sách xem sau (bookmark)

| Cột | Kiểu | Nullable | Default | Ghi chú |
|-----|------|----------|---------|---------|
| `id` | `BIGSERIAL` | NO | auto | PK |
| `user_id` | `BIGINT` | NO | — | FK → users CASCADE |
| `movie_id` | `BIGINT` | NO | — | FK → movies CASCADE |
| `added_at` | `TIMESTAMPTZ` | NO | `NOW()` | — |

Constraints: `UNIQUE(user_id, movie_id)`, `INDEX(user_id, added_at DESC)`

---

### 4.4 PostgreSQL DDL — Toàn Bộ SQL

```sql
-- ============================================================
-- FilmSite Database Schema v2.0
-- PostgreSQL 16+
-- Thực thi: psql -U film_user -d filmsite_db -f schema.sql
-- ============================================================

-- Extension
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- Full-text trigram search
CREATE EXTENSION IF NOT EXISTS "unaccent";  -- Tìm kiếm không dấu

-- ─────────────────────────────────────────
-- 1. USERS & AUTH
-- ─────────────────────────────────────────

CREATE TABLE users (
    id              BIGSERIAL       PRIMARY KEY,
    email           VARCHAR(254)    NOT NULL,
    password        VARCHAR(128)    NOT NULL,
    display_name    VARCHAR(100)    NOT NULL DEFAULT '',
    avatar          VARCHAR(100),
    is_verified     BOOLEAN         NOT NULL DEFAULT FALSE,
    is_active       BOOLEAN         NOT NULL DEFAULT TRUE,
    is_staff        BOOLEAN         NOT NULL DEFAULT FALSE,
    is_superuser    BOOLEAN         NOT NULL DEFAULT FALSE,
    last_login      TIMESTAMPTZ,
    date_joined     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT users_email_unique UNIQUE (email)
);

CREATE INDEX idx_users_active_created ON users (is_active, created_at DESC);
CREATE INDEX idx_users_email_trgm ON users USING GIN (email gin_trgm_ops);

COMMENT ON TABLE users IS 'CustomUser — dùng email thay username, Argon2 password hash';


CREATE TABLE user_profiles (
    id                      BIGSERIAL   PRIMARY KEY,
    user_id                 BIGINT      NOT NULL,
    bio                     TEXT        NOT NULL DEFAULT '',
    birth_date              DATE,
    country                 CHAR(3)     NOT NULL DEFAULT '',
    preferred_language      VARCHAR(10) NOT NULL DEFAULT 'vi',
    notifications_email     BOOLEAN     NOT NULL DEFAULT TRUE,
    notifications_reply     BOOLEAN     NOT NULL DEFAULT TRUE,
    total_watch_time        INT         NOT NULL DEFAULT 0,   -- phút
    total_movies_watched    INT         NOT NULL DEFAULT 0,

    CONSTRAINT fk_profile_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT user_profiles_user_unique UNIQUE (user_id)
);

COMMENT ON TABLE user_profiles IS '1-1 với users. Tạo tự động qua Django signal khi user đăng ký.';


-- ─────────────────────────────────────────
-- 2. LOOKUP / TAXONOMY TABLES
-- ─────────────────────────────────────────

CREATE TABLE genres (
    id      SERIAL          PRIMARY KEY,
    name    VARCHAR(100)    NOT NULL,
    slug    VARCHAR(100)    NOT NULL,

    CONSTRAINT genres_name_unique UNIQUE (name),
    CONSTRAINT genres_slug_unique UNIQUE (slug)
);

INSERT INTO genres (name, slug) VALUES
    ('Hành Động',   'hanh-dong'),
    ('Tình Cảm',    'tinh-cam'),
    ('Kinh Dị',     'kinh-di'),
    ('Hài Hước',    'hai-huoc'),
    ('Khoa Học Viễn Tưởng', 'khoa-hoc-vien-tuong'),
    ('Hoạt Hình',   'hoat-hinh'),
    ('Anime',       'anime'),
    ('Tâm Lý',      'tam-ly'),
    ('Phiêu Lưu',   'phieu-luu'),
    ('Tài Liệu',    'tai-lieu'),
    ('Thể Thao',    'the-thao'),
    ('Âm Nhạc',     'am-nhac'),
    ('Gia Đình',    'gia-dinh'),
    ('Lịch Sử',     'lich-su'),
    ('Chiến Tranh', 'chien-tranh');


CREATE TABLE tags (
    id      SERIAL          PRIMARY KEY,
    name    VARCHAR(100)    NOT NULL,
    slug    VARCHAR(100)    NOT NULL,

    CONSTRAINT tags_name_unique UNIQUE (name),
    CONSTRAINT tags_slug_unique UNIQUE (slug)
);


CREATE TABLE countries (
    id      SERIAL          PRIMARY KEY,
    name    VARCHAR(100)    NOT NULL,
    code    CHAR(3)         NOT NULL,
    flag    VARCHAR(10)     NOT NULL DEFAULT '',

    CONSTRAINT countries_code_unique UNIQUE (code)
);

INSERT INTO countries (name, code, flag) VALUES
    ('Nhật Bản',        'JPN', '🇯🇵'),
    ('Hàn Quốc',        'KOR', '🇰🇷'),
    ('Hoa Kỳ',          'USA', '🇺🇸'),
    ('Việt Nam',        'VNM', '🇻🇳'),
    ('Trung Quốc',      'CHN', '🇨🇳'),
    ('Anh',             'GBR', '🇬🇧'),
    ('Pháp',            'FRA', '🇫🇷'),
    ('Thái Lan',        'THA', '🇹🇭'),
    ('Ấn Độ',           'IND', '🇮🇳'),
    ('Đức',             'DEU', '🇩🇪');


CREATE TABLE studios (
    id              SERIAL          PRIMARY KEY,
    name            VARCHAR(255)    NOT NULL,
    slug            VARCHAR(255)    NOT NULL,
    logo_path       VARCHAR(500)    NOT NULL DEFAULT '',
    founded_year    SMALLINT,

    CONSTRAINT studios_name_unique UNIQUE (name),
    CONSTRAINT studios_slug_unique UNIQUE (slug)
);


CREATE TABLE people (
    id              BIGSERIAL       PRIMARY KEY,
    full_name       VARCHAR(255)    NOT NULL,
    original_name   VARCHAR(255)    NOT NULL DEFAULT '',
    slug            VARCHAR(300)    NOT NULL,
    avatar_path     VARCHAR(500)    NOT NULL DEFAULT '',
    bio             TEXT            NOT NULL DEFAULT '',
    birth_date      DATE,
    nationality     VARCHAR(100)    NOT NULL DEFAULT '',
    tmdb_id         INT,

    CONSTRAINT people_slug_unique   UNIQUE (slug),
    CONSTRAINT people_tmdb_unique   UNIQUE (tmdb_id)
);

CREATE INDEX idx_people_name ON people (full_name);
CREATE INDEX idx_people_name_trgm ON people USING GIN (full_name gin_trgm_ops);


-- ─────────────────────────────────────────
-- 3. MOVIES (bảng trung tâm)
-- ─────────────────────────────────────────

CREATE TYPE medium_type_enum AS ENUM (
    'Movie', 'Series', 'Anime', 'Anime Movie',
    'OVA', 'Special', 'Documentary', 'Short Film',
    'Mini-Series', 'TV Movie'
);

CREATE TYPE content_status_enum AS ENUM (
    'Ongoing', 'Completed', 'Upcoming',
    'Hiatus', 'Cancelled', 'Unknown'
);

CREATE TABLE movies (
    id              BIGSERIAL           PRIMARY KEY,
    title           VARCHAR(500)        NOT NULL,
    original_title  VARCHAR(500)        NOT NULL DEFAULT '',
    slug            VARCHAR(600)        NOT NULL,
    synopsis        TEXT                NOT NULL DEFAULT '',
    medium_type     medium_type_enum    NOT NULL DEFAULT 'Movie',
    status          content_status_enum NOT NULL DEFAULT 'Unknown',
    release_year    SMALLINT,
    content_rating  VARCHAR(10)         NOT NULL DEFAULT '',

    -- External IDs
    tmdb_id         INT,
    imdb_id         VARCHAR(20)         NOT NULL DEFAULT '',
    mal_id          INT,
    imdb_rating     NUMERIC(3,1),

    -- Denormalized ratings (cập nhật qua signal)
    avg_rating      NUMERIC(4,2),
    rating_count    INT                 NOT NULL DEFAULT 0,

    -- Media
    poster_path     VARCHAR(500)        NOT NULL DEFAULT '',
    backdrop_path   VARCHAR(500)        NOT NULL DEFAULT '',
    thumbnail_path  VARCHAR(500)        NOT NULL DEFAULT '',

    -- Flags
    is_featured     BOOLEAN             NOT NULL DEFAULT FALSE,
    is_hidden       BOOLEAN             NOT NULL DEFAULT FALSE,
    view_count      BIGINT              NOT NULL DEFAULT 0,

    -- Self-reference (OVA/Special liên quan đến series gốc)
    parent_movie_id BIGINT,

    created_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT movies_slug_unique   UNIQUE (slug),
    CONSTRAINT movies_tmdb_unique   UNIQUE (tmdb_id),
    CONSTRAINT movies_rating_check  CHECK (imdb_rating BETWEEN 0.0 AND 10.0),
    CONSTRAINT movies_year_check    CHECK (release_year BETWEEN 1888 AND 2100),

    CONSTRAINT fk_movies_parent FOREIGN KEY (parent_movie_id)
        REFERENCES movies(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX idx_movie_slug         ON movies (slug);
CREATE INDEX idx_movie_type         ON movies (medium_type, status);
CREATE INDEX idx_movie_year         ON movies (release_year);
CREATE INDEX idx_movie_imdb         ON movies (imdb_rating DESC NULLS LAST);
CREATE INDEX idx_movie_avgrating    ON movies (avg_rating DESC NULLS LAST);
CREATE INDEX idx_movie_flags        ON movies (is_hidden, is_featured);
CREATE INDEX idx_movie_views        ON movies (view_count DESC);
CREATE INDEX idx_movie_created      ON movies (created_at DESC);
CREATE INDEX idx_movie_title_trgm   ON movies USING GIN (title gin_trgm_ops);
CREATE INDEX idx_movie_orig_trgm    ON movies USING GIN (original_title gin_trgm_ops);

-- Trigger: tự động cập nhật updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_movies_updated_at
    BEFORE UPDATE ON movies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMENT ON TABLE movies IS 'Bảng trung tâm. Cả phim lẻ lẫn phim bộ đều dùng chung, phân biệt qua medium_type.';


-- ─────────────────────────────────────────
-- 4. M2M THROUGH TABLES
-- ─────────────────────────────────────────

CREATE TABLE movie_genres (
    id          BIGSERIAL   PRIMARY KEY,
    movie_id    BIGINT      NOT NULL,
    genre_id    INT         NOT NULL,

    CONSTRAINT fk_mg_movie  FOREIGN KEY (movie_id) REFERENCES movies(id)  ON DELETE CASCADE,
    CONSTRAINT fk_mg_genre  FOREIGN KEY (genre_id) REFERENCES genres(id)  ON DELETE CASCADE,
    CONSTRAINT uq_mg        UNIQUE (movie_id, genre_id)
);

CREATE TABLE movie_tags (
    id          BIGSERIAL   PRIMARY KEY,
    movie_id    BIGINT      NOT NULL,
    tag_id      INT         NOT NULL,

    CONSTRAINT fk_mt_movie  FOREIGN KEY (movie_id) REFERENCES movies(id)  ON DELETE CASCADE,
    CONSTRAINT fk_mt_tag    FOREIGN KEY (tag_id)   REFERENCES tags(id)    ON DELETE CASCADE,
    CONSTRAINT uq_mt        UNIQUE (movie_id, tag_id)
);

CREATE TABLE movie_countries (
    id              BIGSERIAL   PRIMARY KEY,
    movie_id        BIGINT      NOT NULL,
    country_id      INT         NOT NULL,

    CONSTRAINT fk_mc_movie      FOREIGN KEY (movie_id)   REFERENCES movies(id)    ON DELETE CASCADE,
    CONSTRAINT fk_mc_country    FOREIGN KEY (country_id) REFERENCES countries(id) ON DELETE CASCADE,
    CONSTRAINT uq_mc            UNIQUE (movie_id, country_id)
);

CREATE TABLE movie_cast_crew (
    id              BIGSERIAL       PRIMARY KEY,
    movie_id        BIGINT          NOT NULL,
    person_id       BIGINT          NOT NULL,
    role            VARCHAR(40)     NOT NULL,
    character_name  VARCHAR(255)    NOT NULL DEFAULT '',
    sort_order      SMALLINT        NOT NULL DEFAULT 0,

    CONSTRAINT fk_mcc_movie     FOREIGN KEY (movie_id)  REFERENCES movies(id)  ON DELETE CASCADE,
    CONSTRAINT fk_mcc_person    FOREIGN KEY (person_id) REFERENCES people(id)  ON DELETE CASCADE,
    CONSTRAINT chk_mcc_role     CHECK (role IN (
        'Director', 'Cast', 'Screenwriter', 'Producer',
        'Composer', 'Editor', 'Voice Actor',
        'Cinematographer', 'Visual Effects Supervisor'
    ))
);

CREATE INDEX idx_mcc_movie_role ON movie_cast_crew (movie_id, role);
CREATE INDEX idx_mcc_person     ON movie_cast_crew (person_id);


CREATE TABLE movie_studios (
    id          BIGSERIAL   PRIMARY KEY,
    movie_id    BIGINT      NOT NULL,
    studio_id   INT         NOT NULL,
    role        VARCHAR(20) NOT NULL DEFAULT 'Production',

    CONSTRAINT fk_ms_movie  FOREIGN KEY (movie_id)  REFERENCES movies(id)  ON DELETE CASCADE,
    CONSTRAINT fk_ms_studio FOREIGN KEY (studio_id) REFERENCES studios(id) ON DELETE CASCADE,
    CONSTRAINT uq_ms        UNIQUE (movie_id, studio_id)
);


-- ─────────────────────────────────────────
-- 5. VIDEO & MEDIA
-- ─────────────────────────────────────────

CREATE TABLE episodes (
    id              BIGSERIAL       PRIMARY KEY,
    movie_id        BIGINT          NOT NULL,
    season_number   SMALLINT        NOT NULL DEFAULT 1,
    episode_number  SMALLINT        NOT NULL,
    episode_name    VARCHAR(255)    NOT NULL DEFAULT '',
    description     TEXT            NOT NULL DEFAULT '',
    m3u8_path       VARCHAR(500)    NOT NULL DEFAULT '',
    movie_file_path VARCHAR(500)    NOT NULL DEFAULT '',
    thumbnail_path  VARCHAR(500)    NOT NULL DEFAULT '',
    duration        SMALLINT,                               -- phút
    air_date        DATE,
    view_count      BIGINT          NOT NULL DEFAULT 0,
    is_free         BOOLEAN         NOT NULL DEFAULT TRUE,
    -- BUG FIX: Thêm các cột này — có trong Django model nhưng bị thiếu trong DDL
    processing_status VARCHAR(20)   NOT NULL DEFAULT 'Pending'
                      CHECK (processing_status IN ('Pending', 'Processing', 'Completed', 'Failed')),
    error_message   TEXT            NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_ep_movie  FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    CONSTRAINT uq_ep        UNIQUE (movie_id, season_number, episode_number),
    CONSTRAINT chk_ep_season    CHECK (season_number >= 1),
    CONSTRAINT chk_ep_number    CHECK (episode_number >= 0)
);

CREATE INDEX idx_ep_movie ON episodes (movie_id, season_number, episode_number);

COMMENT ON COLUMN episodes.episode_number IS 'Phim lẻ dùng episode_number = 1, season_number = 1';


CREATE TABLE subtitles (
    id              BIGSERIAL   PRIMARY KEY,
    episode_id      BIGINT      NOT NULL,
    language_code   VARCHAR(10) NOT NULL,
    language_label  VARCHAR(50) NOT NULL DEFAULT '',
    sub_path        VARCHAR(500) NOT NULL,
    format          VARCHAR(5)  NOT NULL DEFAULT 'vtt',
    is_default      BOOLEAN     NOT NULL DEFAULT FALSE,

    CONSTRAINT fk_sub_episode   FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    CONSTRAINT chk_sub_format   CHECK (format IN ('vtt', 'srt', 'ass'))
);

CREATE INDEX idx_sub_episode ON subtitles (episode_id);


CREATE TABLE trailers (
    id              BIGSERIAL       PRIMARY KEY,
    movie_id        BIGINT          NOT NULL,
    trailer_path    VARCHAR(500)    NOT NULL,
    label           VARCHAR(30)     NOT NULL DEFAULT 'Official Trailer',
    language        VARCHAR(10)     NOT NULL DEFAULT 'vi',
    sort_order      SMALLINT        NOT NULL DEFAULT 0,

    CONSTRAINT fk_trailer_movie FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

CREATE INDEX idx_trailer_movie ON trailers (movie_id, sort_order);


-- ─────────────────────────────────────────
-- 6. USER ACTIVITY
-- ─────────────────────────────────────────

CREATE TABLE comments (
    id          BIGSERIAL   PRIMARY KEY,
    movie_id    BIGINT      NOT NULL,
    user_id     BIGINT      NOT NULL,
    parent_id   BIGINT,                         -- NULL = top-level comment
    body        TEXT        NOT NULL,
    is_spoiler  BOOLEAN     NOT NULL DEFAULT FALSE,
    is_hidden   BOOLEAN     NOT NULL DEFAULT FALSE,
    like_count  INT         NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_comment_movie     FOREIGN KEY (movie_id)  REFERENCES movies(id)   ON DELETE CASCADE,
    CONSTRAINT fk_comment_user      FOREIGN KEY (user_id)   REFERENCES users(id)    ON DELETE CASCADE,
    CONSTRAINT fk_comment_parent    FOREIGN KEY (parent_id) REFERENCES comments(id) ON DELETE CASCADE,
    CONSTRAINT chk_comment_body     CHECK (char_length(body) >= 3),
    CONSTRAINT chk_comment_depth    CHECK (parent_id IS NULL OR parent_id != id)
);

CREATE INDEX idx_comment_movie_top  ON comments (movie_id, parent_id, created_at DESC);
CREATE INDEX idx_comment_parent     ON comments (parent_id);
CREATE INDEX idx_comment_user       ON comments (user_id);

CREATE TRIGGER trg_comments_updated_at
    BEFORE UPDATE ON comments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();


CREATE TABLE comment_likes (
    id          BIGSERIAL   PRIMARY KEY,
    comment_id  BIGINT      NOT NULL,
    user_id     BIGINT      NOT NULL,
    value       SMALLINT    NOT NULL DEFAULT 1,

    CONSTRAINT fk_cl_comment    FOREIGN KEY (comment_id) REFERENCES comments(id) ON DELETE CASCADE,
    CONSTRAINT fk_cl_user       FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    CONSTRAINT uq_cl            UNIQUE (comment_id, user_id),
    CONSTRAINT chk_cl_value     CHECK (value IN (1, -1))
);


CREATE TABLE ratings (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     BIGINT      NOT NULL,
    movie_id    BIGINT      NOT NULL,
    score       SMALLINT    NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_rating_user   FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
    CONSTRAINT fk_rating_movie  FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    CONSTRAINT uq_rating        UNIQUE (user_id, movie_id),
    CONSTRAINT chk_rating_score CHECK (score BETWEEN 1 AND 10)
);

CREATE INDEX idx_rating_movie ON ratings (movie_id);

CREATE TRIGGER trg_ratings_updated_at
    BEFORE UPDATE ON ratings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Section 4: SQL Schema - Đã loại bỏ trigger trg_rating_update_avg để tránh race condition
-- Logic đã được chuyển sang Celery async task (Xem Section 8.2)



CREATE TABLE watch_history (
    id                  BIGSERIAL   PRIMARY KEY,
    user_id             BIGINT      NOT NULL,
    episode_id          BIGINT      NOT NULL,
    progress_seconds    INT         NOT NULL DEFAULT 0,
    duration_seconds    INT         NOT NULL DEFAULT 0,
    completed           BOOLEAN     NOT NULL DEFAULT FALSE,
    watched_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),   -- auto_now

    CONSTRAINT fk_wh_user       FOREIGN KEY (user_id)    REFERENCES users(id)    ON DELETE CASCADE,
    CONSTRAINT fk_wh_episode    FOREIGN KEY (episode_id) REFERENCES episodes(id) ON DELETE CASCADE,
    CONSTRAINT uq_wh            UNIQUE (user_id, episode_id),
    CONSTRAINT chk_wh_progress  CHECK (progress_seconds >= 0),
    CONSTRAINT chk_wh_duration  CHECK (duration_seconds >= 0)
);

CREATE INDEX idx_wh_user_time   ON watch_history (user_id, watched_at DESC);
CREATE INDEX idx_wh_episode     ON watch_history (episode_id);

COMMENT ON TABLE watch_history IS 'Upsert mỗi 15-30s khi đang xem. Dùng ON CONFLICT DO UPDATE.';


CREATE TABLE watchlist_items (
    id          BIGSERIAL   PRIMARY KEY,
    user_id     BIGINT      NOT NULL,
    movie_id    BIGINT      NOT NULL,
    added_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_wl_user   FOREIGN KEY (user_id)  REFERENCES users(id)  ON DELETE CASCADE,
    CONSTRAINT fk_wl_movie  FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
    CONSTRAINT uq_wl        UNIQUE (user_id, movie_id)
);

CREATE INDEX idx_wl_user ON watchlist_items (user_id, added_at DESC);
```

---

### 4.5 Script Khởi Tạo Database

```sql
-- Tạo user và database (chạy với quyền postgres superuser)
-- psql -U postgres

CREATE USER film_user WITH
    PASSWORD 'your_strong_password'
    CREATEDB
    LOGIN;

CREATE DATABASE filmsite_db
    OWNER film_user
    ENCODING 'UTF8'
    LC_COLLATE 'vi_VN.UTF-8'
    LC_CTYPE   'vi_VN.UTF-8'
    TEMPLATE   template0;

-- Cấp quyền
GRANT ALL PRIVILEGES ON DATABASE filmsite_db TO film_user;
GRANT ALL ON SCHEMA public TO film_user;

-- Kết nối và chạy schema
\c filmsite_db film_user
\i schema.sql
```

```powershell
# PowerShell — chạy schema sau khi có PostgreSQL
$env:PGPASSWORD = "your_strong_password"
psql -U film_user -d filmsite_db -f schema.sql

# Hoặc dùng Django migrations (khuyến nghị trong dev)
uv run python manage.py migrate
```

---

### 4.6 Query Mẫu — Các Truy Vấn Quan Trọng

```sql
-- ── 1. Trang chủ: top trending (dùng Redis thực tế, SQL fallback) ──
SELECT m.id, m.title, m.slug, m.poster_path, m.avg_rating, m.view_count
FROM movies m
WHERE m.is_hidden = FALSE
ORDER BY m.view_count DESC
LIMIT 12;

-- ── 2. Tìm kiếm full-text có dấu ──
SELECT id, title, slug, poster_path, release_year
FROM movies
WHERE to_tsvector('simple', unaccent(title || ' ' || original_title))
      @@ plainto_tsquery('simple', unaccent('avengers'))
  AND is_hidden = FALSE
LIMIT 20;

-- ── 3. Lọc phim theo nhiều tiêu chí ──
SELECT DISTINCT m.id, m.title, m.slug, m.imdb_rating
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.id
JOIN genres g ON g.id = mg.genre_id
JOIN movie_countries mc ON mc.movie_id = m.id
WHERE g.slug         = 'hanh-dong'
  AND mc.country_id  = (SELECT id FROM countries WHERE code = 'JPN')
  AND m.release_year BETWEEN 2010 AND 2024
  AND m.is_hidden    = FALSE
ORDER BY m.imdb_rating DESC NULLS LAST
LIMIT 24;

-- ── 4. Continue watching (upsert-based) ──
SELECT
    wh.progress_seconds,
    wh.duration_seconds,
    wh.watched_at,
    e.episode_number,
    e.season_number,
    m.title,
    m.slug,
    m.poster_path
FROM watch_history wh
JOIN episodes e ON e.id = wh.episode_id
JOIN movies m   ON m.id = e.movie_id
WHERE wh.user_id  = $1
  AND wh.completed = FALSE
ORDER BY wh.watched_at DESC
LIMIT 8;

-- ── 5. Upsert watch progress ──
INSERT INTO watch_history (user_id, episode_id, progress_seconds, duration_seconds, completed, watched_at)
VALUES ($1, $2, $3, $4, ($3::FLOAT / NULLIF($4, 0) >= 0.9), NOW())
ON CONFLICT (user_id, episode_id)
DO UPDATE SET
    progress_seconds = EXCLUDED.progress_seconds,
    duration_seconds = EXCLUDED.duration_seconds,
    completed        = EXCLUDED.completed,
    watched_at       = NOW();

-- ── 6. Nested comments (1 cấp) ──
SELECT
    c.id, c.body, c.is_spoiler, c.like_count, c.created_at,
    u.display_name, u.avatar,
    r.id AS reply_id, r.body AS reply_body,
    ru.display_name AS reply_user
FROM comments c
JOIN users u ON u.id = c.user_id
LEFT JOIN comments r  ON r.parent_id = c.id AND r.is_hidden = FALSE
LEFT JOIN users ru ON ru.id = r.user_id
WHERE c.movie_id  = $1
  AND c.parent_id IS NULL
  AND c.is_hidden = FALSE
ORDER BY c.created_at DESC
LIMIT 20;

-- ── 7. Top rated phim (weighted rating — Bayesian average) ──
-- C = avg rating toàn site, m = min votes cần thiết (vd: 10)
SELECT
    title, slug, avg_rating, rating_count, imdb_rating,
    -- Bayesian: (v * R + m * C) / (v + m)
    ROUND(
        (rating_count * avg_rating + 10 * (SELECT AVG(avg_rating) FROM movies WHERE avg_rating IS NOT NULL))
        / NULLIF(rating_count + 10, 0)
    , 2) AS weighted_rating
FROM movies
WHERE is_hidden = FALSE AND rating_count >= 5
ORDER BY weighted_rating DESC NULLS LAST
LIMIT 20;

-- ── 8. Cast của một phim ──
SELECT
    p.full_name, p.slug, p.avatar_path,
    mcc.role, mcc.character_name
FROM movie_cast_crew mcc
JOIN people p ON p.id = mcc.person_id
WHERE mcc.movie_id = $1
ORDER BY
    CASE mcc.role WHEN 'Director' THEN 0 WHEN 'Cast' THEN 1 ELSE 2 END,
    mcc.sort_order;

-- ── 9. Watchlist của user ──
SELECT m.id, m.title, m.slug, m.poster_path, m.avg_rating, wi.added_at
FROM watchlist_items wi
JOIN movies m ON m.id = wi.movie_id
WHERE wi.user_id = $1
ORDER BY wi.added_at DESC
LIMIT 20;

-- ── 10. Thống kê user (dashboard) ──
SELECT
    COUNT(*) FILTER (WHERE completed = TRUE) AS movies_completed,
    COUNT(*) FILTER (WHERE completed = FALSE) AS movies_in_progress,
    COALESCE(SUM(progress_seconds) / 3600, 0) AS total_watch_hours
FROM watch_history
WHERE user_id = $1;
```

---

### 4.7 Database Indexes — Chiến Lược

| Index | Bảng | Cột | Loại | Mục đích |
|-------|------|-----|------|---------|
| `idx_movie_title_trgm` | `movies` | `title` | GIN (trigram) | Full-text search nhanh |
| `idx_movie_orig_trgm` | `movies` | `original_title` | GIN (trigram) | Tìm theo tên gốc |
| `idx_movie_flags` | `movies` | `(is_hidden, is_featured)` | BTREE | Lọc trang chủ |
| `idx_movie_type` | `movies` | `(medium_type, status)` | BTREE | Lọc theo loại phim |
| `idx_movie_views` | `movies` | `view_count DESC` | BTREE | Trending fallback |
| `idx_ep_movie` | `episodes` | `(movie_id, season, ep)` | BTREE | Lấy danh sách tập |
| `idx_wh_user_time` | `watch_history` | `(user_id, watched_at DESC)` | BTREE | Continue watching |
| `idx_comment_movie_top` | `comments` | `(movie_id, parent_id, created_at)` | BTREE | Load top-level comments |
| `idx_rating_movie` | `ratings` | `movie_id` | BTREE | Tính avg khi trigger |
| `idx_people_name_trgm` | `people` | `full_name` | GIN (trigram) | Tìm kiếm diễn viên |

> **Lưu ý:** Trigram index (`pg_trgm`) hỗ trợ `LIKE '%keyword%'` nhanh hơn sequential scan rất nhiều. Bật extension trước khi migrate.

---

### 4.8 Database Migration — Quy Trình

```powershell
# Bước 1: Tạo migrations từ models
uv run python manage.py makemigrations films users comments ratings history watchlist

# Bước 2: Xem SQL trước khi apply (kiểm tra)
uv run python manage.py sqlmigrate films 0001_initial

# Bước 3: Apply migrations
uv run python manage.py migrate

# Bước 4: Tạo superuser
uv run python manage.py createsuperuser

# Bước 5: Load seed data (genres, countries)
uv run python manage.py loaddata genres countries
```

```python
# management/commands/seed_db.py — Seed dữ liệu mẫu
from django.core.management.base import BaseCommand
from apps.films.models import Genre, Country

class Command(BaseCommand):
    help = 'Seed database với dữ liệu cơ bản'

    def handle(self, *args, **kwargs):
        genres = [
            ('Hành Động', 'hanh-dong'), ('Tình Cảm', 'tinh-cam'),
            ('Kinh Dị', 'kinh-di'),     ('Hài Hước', 'hai-huoc'),
            ('Anime', 'anime'),          ('Tâm Lý', 'tam-ly'),
            ('Phiêu Lưu', 'phieu-luu'), ('Tài Liệu', 'tai-lieu'),
            ('Khoa Học Viễn Tưởng', 'khoa-hoc-vien-tuong'),
            ('Hoạt Hình', 'hoat-hinh'), ('Gia Đình', 'gia-dinh'),
            ('Lịch Sử', 'lich-su'),     ('Chiến Tranh', 'chien-tranh'),
        ]
        for name, slug in genres:
            Genre.objects.get_or_create(slug=slug, defaults={'name': name})
        self.stdout.write(self.style.SUCCESS(f'✓ Seeded {len(genres)} genres'))

        countries = [
            ('Nhật Bản', 'JPN', '🇯🇵'), ('Hàn Quốc', 'KOR', '🇰🇷'),
            ('Hoa Kỳ',   'USA', '🇺🇸'), ('Việt Nam', 'VNM', '🇻🇳'),
            ('Trung Quốc','CHN','🇨🇳'), ('Anh',      'GBR', '🇬🇧'),
            ('Pháp',     'FRA', '🇫🇷'), ('Thái Lan', 'THA', '🇹🇭'),
            ('Ấn Độ',    'IND', '🇮🇳'), ('Đức',      'DEU', '🇩🇪'),
        ]
        for name, code, flag in countries:
            Country.objects.get_or_create(code=code, defaults={'name': name, 'flag': flag})
        self.stdout.write(self.style.SUCCESS(f'✓ Seeded {len(countries)} countries'))
```

---

### 4.9 Backup & Restore

```powershell
# Backup toàn bộ database
$date = Get-Date -Format "yyyy-MM-dd"
pg_dump -U film_user -d filmsite_db -F c -f "C:\Backups\filmsite_$date.backup"

# Backup chỉ schema (không có data — dùng để clone cấu trúc)
pg_dump -U film_user -d filmsite_db --schema-only -f "schema_only.sql"

# Restore từ backup
pg_restore -U film_user -d filmsite_db_new -F c "C:\Backups\filmsite_2025-01-01.backup"

# Xem danh sách bảng và kích thước
psql -U film_user -d filmsite_db -c "
SELECT
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    n_live_tup AS row_count
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC;
"
```

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
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/min',
        'user': '300/min',
        'auth': '10/min',        # Login/Register
        'comment': '20/min',     # Post comment
        'search': '30/min',      # Search API (FIX-19)
        'watch_progress': '120/min', # Heartbeat (FIX-19)
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

    # FIX-14: Tích hợp django-axes để block brute-force
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email    = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        user = authenticate(request, email=email, password=password)
        
        if not user:
            # Axes tự động bắt tín hiệu authenticate thất bại để tăng counter
            return Response({'detail': 'Email hoặc mật khẩu không đúng.'},
                            status=status.HTTP_401_UNAUTHORIZED)

        if not user.is_active:
            return Response({'detail': 'Tài khoản đã bị vô hiệu hoá.'},
                            status=status.HTTP_403_FORBIDDEN)

        # BUG FIX: Phần này bị thiếu trong bản gốc — tạo JWT tokens cho user đăng nhập thành công
        refresh = RefreshToken.for_user(user)
        return Response({
            'user':    UserDetailSerializer(user).data,
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_200_OK)


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
        
        # Sửa lỗi Thundering Herd bằng get_or_set_safe
        from apps.films.cache import get_or_set_safe
        
        def fetch_data():
            instance = self.get_object()
            return self.get_serializer(instance).data
            
        data = get_or_set_safe(cache_key, fetch_data, timeout=60 * 10) # 10 phút
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
    episodes  = EpisodeSerializer(many=True, read_only=True)
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
        from django.db.models import Prefetch
        movie = get_object_or_404(Movie, slug=self.kwargs['slug'])
        # FIX-18: Dùng Prefetch để lấy replies trong 1 query duy nhất
        return (
            Comment.objects
            .filter(movie=movie, parent=None, is_hidden=False)
            .select_related('user')
            .prefetch_related(
                Prefetch('replies', queryset=Comment.objects.filter(is_hidden=False).select_related('user'))
            )
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

### 8.0 AppConfig — Kết Nối Signals

> **Vấn đề quan trọng:** `ratings/signals.py` chỉ chạy nếu được import trong `AppConfig.ready()`. Nếu bỏ qua bước này, signal cập nhật `avg_rating` sẽ **không bao giờ hoạt động** dù code signal đúng hoàn toàn.

```python
# apps/ratings/apps.py  ← BUG FIX: file này bị thiếu hoàn toàn trong plan gốc
from django.apps import AppConfig


class RatingsConfig(AppConfig):
    name = 'apps.ratings'
    verbose_name = 'Ratings'

    def ready(self):
        import apps.ratings.signals  # noqa: F401 — import để kích hoạt signal handlers
```

```python
# apps/ratings/__init__.py
default_app_config = 'apps.ratings.apps.RatingsConfig'
```

> **Áp dụng tương tự cho các app có signals:**
> - `apps/comments/apps.py` → import `apps.comments.signals` trong `ready()`
> - `apps/users/apps.py` → import `apps.users.signals` trong `ready()` (signal tạo UserProfile sau khi register)

```python
# apps/users/apps.py — Ví dụ: signal tạo UserProfile tự động
from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'
    verbose_name = 'Users'

    def ready(self):
        import apps.users.signals  # noqa: F401
```

```python
# apps/users/signals.py — Tạo UserProfile tự động khi User được tạo
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        from apps.users.models import UserProfile
        UserProfile.objects.get_or_create(user=instance)
```

---

### 8.1 Ratings Model

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

### 8.2 Rating Signal — Tự Động Cập Nhật avg_rating (Async via Celery)

```python
# apps/ratings/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Rating

@receiver(post_save, sender=Rating)
def on_rating_save(sender, instance, **kwargs):
    from apps.ratings.tasks import update_movie_avg_rating
    update_movie_avg_rating.delay(instance.movie_id)

@receiver(post_delete, sender=Rating)
def on_rating_delete(sender, instance, **kwargs):
    from apps.ratings.tasks import update_movie_avg_rating
    update_movie_avg_rating.delay(instance.movie_id)

# apps/ratings/tasks.py
from celery import shared_task
from django.db.models import Avg

@shared_task
def update_movie_avg_rating(movie_id: int):
    from apps.ratings.models import Rating
    from apps.films.models import Movie
    result = Rating.objects.filter(movie_id=movie_id).aggregate(avg=Avg('score'))
    count = Rating.objects.filter(movie_id=movie_id).count()
    Movie.objects.filter(pk=movie_id).update(
        avg_rating=round(result['avg'], 2) if result['avg'] else None,
        rating_count=count,
    )
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

    from django.db import transaction

    @transaction.atomic
    def post(self, request, episode_id):
        episode = get_object_or_404(Episode, pk=episode_id)
        progress  = int(request.data.get('progress_seconds', 0))
        duration  = int(request.data.get('duration_seconds', 0))
        completed = (duration > 0 and progress / duration >= 0.9)

        # Tránh IntegrityError bằng lock row
        history, created = WatchHistory.objects.select_for_update().get_or_create(
            user=request.user, episode=episode
        )
        
        was_completed = history.completed
        history.progress_seconds = progress
        history.duration_seconds = duration
        history.completed = completed
        history.save()

        # Tăng view_count (dùng Redis increment - FIX-15)
        if completed and not was_completed:
            from apps.films.cache import increment_view_count_redis, increment_trending
            increment_view_count_redis(episode.movie_id)
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
CELERY_BROKER_URL        = env('CELERY_BROKER_URL', default='redis://127.0.0.1:6379/2')
CELERY_RESULT_BACKEND    = env('CELERY_RESULT_BACKEND', default='redis://127.0.0.1:6379/3')  # BUG FIX: khác DB với broker
CELERY_TASK_SERIALIZER   = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT    = ['json']
CELERY_TIMEZONE          = 'Asia/Ho_Chi_Minh'
```

### 10.3 Cache Helpers

```python
# apps/films/cache.py
from django.core.cache import cache
from django.conf import settings
import redis

# BUG FIX: Không hardcode URL — đọc từ settings để đồng bộ với toàn bộ config
_redis = redis.Redis.from_url(
    getattr(settings, 'REDIS_URL', 'redis://127.0.0.1:6379/0')
)
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


def get_or_set_safe(key: str, default_fn: callable, timeout: int = 300):
    """
    Sửa lỗi Thundering Herd bằng Redis Lock.
    Chỉ 1 request được gọi DB khi cache expire, các request khác chờ.
    """
    data = cache.get(key)
    if data is not None:
        return data

    lock_key = f"{key}:lock"
    # Lock trong 10s để tránh deadlock
    with _redis.lock(lock_key, timeout=10):
        # Kiểm tra lại cache sau khi lấy được lock
        data = cache.get(key)
        if data is not None:
            return data
        
        # Thực thi hàm lấy dữ liệu từ DB
        data = default_fn()
        cache.set(key, data, timeout=timeout)
        return data


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
# config/__init__.py
# BUG FIX: File này BẮT BUỘC phải có để Django import Celery app khi startup.
# Nếu thiếu, Celery sẽ không autodiscover tasks và beat schedule sẽ không hoạt động.
from .celery import app as celery_app

__all__ = ('celery_app',)
```

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
    # Dọn dẹp JWT blacklist (Tránh phình DB)
    'flush-expired-tokens': {
        'task': 'rest_framework_simplejwt.token_blacklist.tasks.flush_expired_tokens',
        'schedule': crontab(hour=4, minute=0),
    },
}
```

### 11.2 Celery Tasks

```python
# apps/films/tasks.py
from celery import shared_task, chord, group
from celery.utils.log import get_task_logger
from django.core.cache import cache  # BUG FIX: thiếu import này, dùng trong refresh_trending_cache
from django.db.models import F
from .models import Episode, Movie

logger = get_task_logger(__name__)

@shared_task(bind=True)
def process_video_file(self, raw_path: str, episode_id: int):
    """FIX-16: Entry point cho pipeline encoding song song."""
    Episode.objects.filter(pk=episode_id).update(processing_status='Processing')
    
    qualities = [480, 720, 1080]
    # Chạy song song các task encode resolution
    header = group(encode_quality_task.s(raw_path, episode_id, q) for q in qualities)
    # Sau khi xong hết thì chạy task finalize
    callback = finalize_encoding_task.s(episode_id)
    
    return chord(header)(callback)

@shared_task
def encode_quality_task(raw_path: str, episode_id: int, quality: int):
    """Task encode 1 resolution cụ thể."""
    from video_processor.processor import encode_single_quality
    return encode_single_quality(raw_path, episode_id, quality)

@shared_task
def finalize_encoding_task(results, episode_id: int):
    """Tổng hợp kết quả, tạo master playlist và cập nhật DB."""
    from video_processor.processor import create_master_playlist
    episode = Episode.objects.get(pk=episode_id)
    
    m3u8_path, duration = create_master_playlist(episode_id, results)
    
    episode.m3u8_path = m3u8_path
    episode.duration = duration
    episode.processing_status = 'Completed'
    episode.save()
    
    # Invalidate cache
    from apps.films.cache import invalidate_movie_cache
    invalidate_movie_cache(episode.movie.slug)
    return f"Episode {episode_id} processed successfully."


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
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email(self, user_id: int):
    from django.contrib.auth import get_user_model
    from django.core.mail import send_mail
    from django.core.cache import cache  # BUG FIX: thiếu import này
    from django.conf import settings
    import secrets

    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return  # BUG FIX: xử lý trường hợp user bị xóa trước khi task chạy
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
# FIX-13: Thêm basic auth cho Flower
uv run celery -A config flower --port=5555 --basic_auth=admin:your_secure_password
# Truy cập: http://localhost:5555

### 11.3.1 Celery Signals — Fix DB Connection Drops (FIX-12)

```python
# config/celery.py (Bổ sung)
from celery.signals import worker_process_init, task_prerun
from django.db import connections

@worker_process_init.connect
def close_old_connections(**kwargs):
    for conn in connections.all():
        conn.close()

@task_prerun.connect
def on_task_prerun(task_id, task, *args, **kwargs):
    for conn in connections.all():
        conn.close()
```
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
    
    # FIX-16: Trạng thái xử lý video
    processing_status = models.CharField(
        max_length=20,
        choices=[('Pending', 'Chờ xử lý'), ('Processing', 'Đang xử lý'), 
                 ('Completed', 'Hoàn thành'), ('Failed', 'Lỗi')],
        default='Pending'
    )
    error_message = models.TextField(blank=True)
    
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
# BUG FIX: Broker và result backend dùng DB riêng — không dùng chung REDIS_URL
CELERY_BROKER_URL=redis://127.0.0.1:6379/2
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/3

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
SITE_URL         = env('SITE_URL', default='http://localhost:8000')

# BUG FIX: Khai báo REDIS_URL ở settings để cache.py đọc qua settings thay vì hardcode
REDIS_URL        = env('REDIS_URL', default='redis://127.0.0.1:6379/0')

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
        'ATOMIC_REQUESTS': True,  # Đảm bảo toàn vẹn dữ liệu per request
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

# Logging — cấu hình đầy đủ
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {process:d} {thread:d} — {message}',
            'style': '{',
        },
        'simple': {
            'format': '[{asctime}] {levelname} — {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'},
        'require_debug_true':  {'()': 'django.utils.log.RequireDebugTrue'},
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
            'filters': ['require_debug_true'],
        },
        'django_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
        'celery_file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'celery.log',
            'maxBytes': 10 * 1024 * 1024,
            'backupCount': 3,
            'formatter': 'verbose',
        },
        'mail_admins': {
            'class': 'django.utils.log.AdminEmailHandler',
            'filters': ['require_debug_false'],
            'level': 'ERROR',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'django_file'],
            'level': 'INFO',
        },
        'django.request': {
            'handlers': ['mail_admins', 'django_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',  # Đặt DEBUG để xem SQL queries khi cần
            'propagate': False,
        },
        'celery': {
            'handlers': ['celery_file', 'console'],
            'level': 'INFO',
        },
        'apps': {
            'handlers': ['console', 'django_file'],
            'level': 'DEBUG',
        },
    },
}

### 15.3 Health Check (FIX-20)

```python
# config/views.py
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache

def health_check(request):
    health = {'status': 'healthy', 'checks': {}}
    try:
        connections['default'].cursor()
        health['checks']['database'] = 'ok'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['checks']['database'] = str(e)
    try:
        cache.set('health_check', 'ok', 10)
        health['checks']['cache'] = 'ok' if cache.get('health_check') == 'ok' else 'fail'
    except Exception as e:
        health['status'] = 'unhealthy'
        health['checks']['cache'] = str(e)
    return JsonResponse(health, status=200 if health['status'] == 'healthy' else 503)

# config/urls.py (Bổ sung)
path('health/', health_check, name='health-check'),
```

### 15.5 Development Settings (FIX-24)

```python
# config/settings/development.py
from .base import *

DEBUG = True

INSTALLED_APPS += [
    'debug_toolbar',
    'silk',
]

MIDDLEWARE += [
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'silk.middleware.SilkyMiddleware',
]

# Silk config
SILKY_PYTHON_PROFILER = True
SILKY_INTERCEPT_PERCENT = 100

# Debug Toolbar
INTERNAL_IPS = ['127.0.0.1']
```

```python
# config/settings/test.py
from .base import *

DEBUG = False
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher', # Fast for tests
]

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
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
CSRF_COOKIE_HTTPONLY         = False  # Phải là False để HTMX/JS đọc được CSRF token
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

### 20.1 Waitress — WSGI Server (Windows)

> **Lý do dùng Waitress thay Gunicorn:** Gunicorn dùng `os.fork()` — không hỗ trợ trên Windows. Waitress là WSGI server thuần Python, chạy native trên Windows, hiệu năng tốt cho local/LAN deployment.

```powershell
# scripts/start_waitress.bat
@echo off
cd C:\Projects\filmsite
uv run waitress-serve ^
    --host=127.0.0.1 ^
    --port=8000 ^
    --threads=8 ^
    --connection-limit=1000 ^
    --channel-timeout=30 ^
    --log-socket-errors=true ^
    config.wsgi:application
```

> **Giải thích tham số:**
> - `--threads=8` — số thread xử lý song song (≈ CPU cores × 2)
> - `--connection-limit=1000` — tối đa 1000 kết nối đồng thời
> - `--channel-timeout=30` — timeout 30 giây per request
> - Không cần file config riêng như gunicorn.conf.py

### 20.2 Task Scheduler — Windows

```powershell
# scripts/setup_tasks.ps1 (chạy với quyền Admin)
$base = "C:\Projects\filmsite"

# Django (Waitress)
$a1 = New-ScheduledTaskAction -Execute "$base\scripts\start_waitress.bat"
Register-ScheduledTask -TaskName "FilmSite-Waitress" `
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
:: FIX-25: KHÔNG dùng SET PGPASSWORD. 
:: Hãy tạo file %APPDATA%\postgresql\pgpass.conf với nội dung: 
:: localhost:5432:filmsite_db:film_user:your_password

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
---

## 23. UI Frontend — Modern, Responsive, Beautiful

> **Stack:** Tailwind CSS v3 · HTMX · Alpine.js · hls.js · Django Templates  
> **Triết lý:** Zero build step, Django-native, progressive enhancement. Không cần Node.js, không cần SPA framework. Đẹp ngay từ HTML.

---

### 23.1 Tại Sao Không Dùng React/Vue?

| Tiêu chí | React/Vue SPA | Django Templates + HTMX |
|---|---|---|
| Build complexity | Cao (Webpack, Vite) | Không có |
| Django integration | API-only, tách rời | Tích hợp sâu (forms, CSRF, auth) |
| SEO | Cần SSR | Native (server-rendered) |
| Time to ship | Chậm hơn | Nhanh hơn |
| Bundle size | 200–500KB+ | ~60KB (Tailwind CDN + HTMX + Alpine) |
| Phù hợp dự án này | Overkill | **Perfect fit** |

> **HTMX** cho phép làm search live, load more, rating, comment mà không cần viết JavaScript — chỉ cần HTML attributes.

---

### 23.2 Design System — Tokens & Colors

```css
/* static/css/tokens.css */
:root {
  /* ── Brand ─────────────────────────────────── */
  --color-primary:     #6272f0;   /* indigo accent */
  --color-primary-dim: rgba(98,114,240,.12);
  --color-danger:      #f0516e;
  --color-success:     #22c55e;
  --color-warn:        #f59e0b;
  --color-star:        #fbbf24;   /* rating stars */

  /* ── Background ─────────────────────────────── */
  --bg:       #090b10;
  --surface:  #0f1218;
  --surface2: #161b24;
  --surface3: #1d2330;
  --border:   #222736;
  --border2:  #2d3447;

  /* ── Text ───────────────────────────────────── */
  --text:   #dde1f0;
  --text2:  #a8afc8;
  --muted:  #636b88;

  /* ── Shadows ─────────────────────────────────── */
  --shadow-card: 0 4px 24px rgba(0,0,0,.4);
  --shadow-glow: 0 0 30px rgba(98,114,240,.2);

  /* ── Spacing (8px grid) ─────────────────────── */
  --space-1: 4px;   --space-2: 8px;  --space-3: 12px;
  --space-4: 16px;  --space-6: 24px; --space-8: 32px;
  --space-12: 48px; --space-16: 64px;

  /* ── Typography ─────────────────────────────── */
  --font-sans: 'Sora', system-ui, sans-serif;
  --font-mono: 'IBM Plex Mono', 'Fira Code', monospace;

  /* ── Radius ─────────────────────────────────── */
  --radius-sm: 6px;   --radius-md: 10px;
  --radius-lg: 14px;  --radius-xl: 20px;

  /* ── Transitions ────────────────────────────── */
  --transition: 150ms ease;
}
```

---

### 23.3 Base Template — `templates/base.html`

```html
{% load static %}  {# BUG FIX: phải load static ở đầu template, trước khi dùng {% static %} bất kỳ đâu #}
<!DOCTYPE html>
<html lang="vi" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}FilmSite{% endblock %} — Xem Phim Hay</title>
  <meta name="description" content="{% block meta_desc %}FilmSite — Streaming phim lẻ, phim bộ, anime chất lượng cao.{% endblock %}">
  <meta name="htmx-config" content='{"includeIndicatorStyles": false, "useTemplateFragments": true}'>

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Sora:wght@300;400;500;600;700;800&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">

  <!-- CSS: Tailwind -->
  {% if debug %}
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            primary: '#6272f0',
            surface: '#0f1218',
            surface2: '#161b24',
            border:  '#222736',
          },
          fontFamily: {
            sans: ['Sora', 'system-ui'],
            mono: ['IBM Plex Mono', 'monospace'],
          }
        }
      }
    }
  </script>
  {% else %}
  <link rel="stylesheet" href="{% static 'css/tailwind.min.css' %}">
  {% endif %}

  <!-- Custom CSS tokens + overrides -->
  <link rel="stylesheet" href="{% static 'css/tokens.css' %}">
  <link rel="stylesheet" href="{% static 'css/components.css' %}">

  {% block extra_head %}{% endblock %}
</head>
<body class="bg-[#090b10] text-[#dde1f0] font-sans antialiased min-h-screen">

  <!-- ── Navbar ───────────────────────────────────── -->
  {% include 'partials/navbar.html' %}

  <!-- ── Main Content ─────────────────────────────── -->
  <main id="main-content" class="min-h-[80vh]">
    {% block content %}{% endblock %}
  </main>

  <!-- ── Footer ───────────────────────────────────── -->
  {% include 'partials/footer.html' %}

  <!-- ── Notifications Toast ──────────────────────── -->
  <div id="toast-container" class="fixed bottom-6 right-6 z-50 flex flex-col gap-3"
       x-data="toastManager()" @show-toast.window="show($event.detail)">
    <template x-for="toast in toasts" :key="toast.id">
      <div x-show="toast.visible"
           x-transition:enter="transition ease-out duration-300"
           x-transition:enter-start="opacity-0 translate-y-4"
           x-transition:enter-end="opacity-100 translate-y-0"
           :class="toast.type === 'error' ? 'border-red-500' : 'border-primary'"
           class="bg-surface2 border rounded-lg px-4 py-3 shadow-xl text-sm flex items-center gap-3 min-w-64">
        <span x-text="toast.message" class="text-[#dde1f0]"></span>
      </div>
    </template>
  </div>

  <!-- ── JS Libraries ─────────────────────────────── -->
  <script src="https://unpkg.com/htmx.org@1.9.12"></script>
  {# BUG FIX: Pin phiên bản Alpine.js cụ thể — 3.x.x unpinned có thể nhận breaking changes #}
  <script src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
  <script src="https://cdn.jsdelivr.net/npm/hls.js@1.5.15/dist/hls.min.js"></script>

  <!-- ── App JS ─────────────────────────────────── -->
  <script src="{% static 'js/app.js' %}"></script>
  <script src="{% static 'js/player.js' %}"></script>

  {% block extra_scripts %}{% endblock %}
</body>
</html>
```

---

### 23.4 Navbar — `templates/partials/navbar.html`

```html
<nav class="sticky top-0 z-40 bg-[#090b10]/90 backdrop-blur-md border-b border-[#222736]"
     x-data="{ mobileOpen: false, searchOpen: false }">
  <div class="max-w-7xl mx-auto px-4 h-16 flex items-center gap-4">

    <!-- Logo -->
    <a href="/" class="flex items-center gap-2 font-bold text-xl tracking-tight flex-shrink-0">
      <span class="text-primary">🎬</span>
      <span>Film<span class="text-primary">Site</span></span>
    </a>

    <!-- Desktop nav links -->
    <div class="hidden md:flex items-center gap-1 ml-4">
      <a href="/" class="nav-link {% if request.resolver_match.url_name == 'home' %}active{% endif %}">Trang chủ</a>
      <a href="{% url 'films:movies' %}?type=Movie" class="nav-link">Phim lẻ</a>
      <a href="{% url 'films:movies' %}?type=Series" class="nav-link">Phim bộ</a>
      <a href="{% url 'films:movies' %}?type=Anime" class="nav-link">Anime</a>
    </div>

    <!-- Search bar (desktop) -->
    <div class="hidden md:flex flex-1 max-w-sm ml-auto relative">
      <input type="search" placeholder="Tìm phim, diễn viên..."
             name="q" value="{{ request.GET.q }}"
             hx-get="{% url 'films:search' %}"
             hx-trigger="input changed delay:400ms, search"
             hx-target="#search-results-dropdown"
             hx-include="[name='q']"
             class="w-full bg-[#161b24] border border-[#222736] rounded-lg px-4 py-2 text-sm
                    text-[#dde1f0] placeholder-[#636b88]
                    focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30
                    transition-all duration-150">
      <div id="search-results-dropdown"
           class="absolute top-full mt-2 w-full bg-[#0f1218] border border-[#222736]
                  rounded-xl shadow-2xl z-50 overflow-hidden">
      </div>
    </div>

    <!-- Auth section -->
    {% if user.is_authenticated %}
    <div class="relative ml-2" x-data="{ open: false }">
      <button @click="open = !open" class="flex items-center gap-2 hover:opacity-80 transition">
        <img src="{{ user.avatar.url|default:'/static/img/avatar-default.webp' }}"
             class="w-8 h-8 rounded-full object-cover ring-2 ring-primary/30">
        <span class="hidden md:block text-sm font-medium">{{ user.display_name|default:user.email|truncatechars:20 }}</span>
      </button>
      <div x-show="open" @click.away="open = false" x-cloak
           class="absolute right-0 top-full mt-2 w-48 bg-[#0f1218] border border-[#222736] rounded-xl shadow-2xl py-1 z-50">
        <a href="{% url 'users:profile' %}" class="dropdown-item">👤 Trang cá nhân</a>
        <a href="{% url 'users:watchlist' %}" class="dropdown-item">🔖 Danh sách xem</a>
        <a href="{% url 'history:index' %}" class="dropdown-item">🕐 Lịch sử xem</a>
        <hr class="border-[#222736] my-1">
        <form method="post" action="{% url 'users:logout' %}">{% csrf_token %}
          <button type="submit" class="dropdown-item text-red-400 w-full text-left">⬅ Đăng xuất</button>
        </form>
      </div>
    </div>
    {% else %}
    <div class="flex items-center gap-2 ml-2">
      <a href="{% url 'users:login' %}" class="text-sm text-[#a8afc8] hover:text-[#dde1f0] transition px-3 py-2">Đăng nhập</a>
      <a href="{% url 'users:register' %}" class="btn-primary text-sm">Đăng ký</a>
    </div>
    {% endif %}

    <!-- Mobile menu toggle -->
    <button @click="mobileOpen = !mobileOpen" class="md:hidden ml-1 p-2 text-[#636b88] hover:text-[#dde1f0]">
      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path x-show="!mobileOpen" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
        <path x-show="mobileOpen"  stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  </div>

  <!-- Mobile menu -->
  <div x-show="mobileOpen" x-cloak class="md:hidden border-t border-[#222736] bg-[#0f1218] px-4 py-3 space-y-1">
    <input type="search" placeholder="Tìm phim..." class="w-full input-field mb-3">
    <a href="/" class="mobile-nav-link">Trang chủ</a>
    <a href="{% url 'films:movies' %}?type=Movie" class="mobile-nav-link">Phim lẻ</a>
    <a href="{% url 'films:movies' %}?type=Series" class="mobile-nav-link">Phim bộ</a>
    <a href="{% url 'films:movies' %}?type=Anime" class="mobile-nav-link">Anime</a>
  </div>
</nav>
```

---

### 23.5 Trang Chủ — `apps/films/templates/films/home.html`

```html
{% extends 'base.html' %}
{% block title %}Trang Chủ{% endblock %}

{% block content %}

<!-- ══ HERO BANNER ══════════════════════════════════════════════ -->
{% if featured_movie %}
<section class="relative h-[75vh] min-h-[500px] overflow-hidden">

  <!-- Backdrop image -->
  <img src="{{ featured_movie.backdrop_path }}" alt="{{ featured_movie.title }}"
       class="absolute inset-0 w-full h-full object-cover">

  <!-- Gradient overlay -->
  <div class="absolute inset-0 bg-gradient-to-r from-[#090b10] via-[#090b10]/70 to-transparent"></div>
  <div class="absolute inset-0 bg-gradient-to-t from-[#090b10] via-transparent to-transparent"></div>

  <!-- Content -->
  <div class="relative z-10 h-full max-w-7xl mx-auto px-4 flex items-end pb-16">
    <div class="max-w-lg">
      <!-- Badges -->
      <div class="flex items-center gap-2 mb-3">
        <span class="badge badge-primary">{{ featured_movie.medium_type }}</span>
        {% if featured_movie.content_rating %}
        <span class="badge badge-outline">{{ featured_movie.content_rating }}</span>
        {% endif %}
        {% if featured_movie.imdb_rating %}
        <span class="flex items-center gap-1 text-yellow-400 text-sm font-semibold">
          ⭐ {{ featured_movie.imdb_rating }}
        </span>
        {% endif %}
      </div>

      <h1 class="text-4xl md:text-5xl font-extrabold leading-tight mb-3 tracking-tight">
        {{ featured_movie.title }}
      </h1>
      <p class="text-[#a8afc8] text-base leading-relaxed mb-6 line-clamp-3">
        {{ featured_movie.short_description }}
      </p>

      <!-- CTA buttons -->
      <div class="flex items-center gap-3 flex-wrap">
        <a href="{% url 'films:detail' featured_movie.slug %}"
           class="btn-primary flex items-center gap-2 text-base px-6 py-3">
          ▶ Xem ngay
        </a>
        <button class="btn-secondary flex items-center gap-2 text-base px-5 py-3"
                hx-post="{% url 'watchlist:toggle' featured_movie.slug %}"
                hx-swap="outerHTML"
                hx-target="this">
          + Danh sách xem
        </button>
      </div>
    </div>
  </div>
</section>
{% endif %}

<!-- ══ CONTINUE WATCHING ════════════════════════════════════════ -->
{% if user.is_authenticated and continue_watching %}
<section class="max-w-7xl mx-auto px-4 mt-10">
  <div class="section-header">
    <h2 class="section-title">🕐 Xem tiếp</h2>
  </div>
  <div class="movie-row">
    {% for item in continue_watching %}
    {% include 'partials/episode_card_resume.html' with history=item %}
    {% endfor %}
  </div>
</section>
{% endif %}

<!-- ══ TRENDING ═════════════════════════════════════════════════ -->
<section class="max-w-7xl mx-auto px-4 mt-12">
  <div class="section-header">
    <h2 class="section-title">🔥 Đang thịnh hành</h2>
    <a href="{% url 'films:movies' %}?sort=-view_count" class="text-primary text-sm hover:underline">Xem tất cả →</a>
  </div>
  <div class="movie-row">
    {% for movie in trending %}
    {% include 'partials/movie_card.html' %}
    {% endfor %}
  </div>
</section>

<!-- ══ BY GENRE ══════════════════════════════════════════════════ -->
{% for section in genre_sections %}
<section class="max-w-7xl mx-auto px-4 mt-12">
  <div class="section-header">
    <h2 class="section-title">{{ section.emoji }} {{ section.genre.genre_name }}</h2>
    <a href="{% url 'films:movies' %}?genre={{ section.genre.slug }}" class="text-primary text-sm hover:underline">Xem tất cả →</a>
  </div>
  <div class="movie-row">
    {% for movie in section.movies %}
    {% include 'partials/movie_card.html' %}
    {% endfor %}
  </div>
</section>
{% endfor %}

<!-- ══ NEW RELEASES ═════════════════════════════════════════════ -->
<section class="max-w-7xl mx-auto px-4 mt-12 mb-16">
  <div class="section-header">
    <h2 class="section-title">✨ Mới nhất</h2>
    <a href="{% url 'films:movies' %}?sort=-created_at" class="text-primary text-sm hover:underline">Xem tất cả →</a>
  </div>
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
    {% for movie in new_releases %}
    {% include 'partials/movie_card.html' %}
    {% endfor %}
  </div>
</section>

{% endblock %}
```

---

### 23.6 Movie Card — `templates/partials/movie_card.html`

```html
<!-- Reusable movie card — 2:3 poster ratio -->
<article class="movie-card group relative" x-data="{ inWatchlist: {{ movie.in_watchlist|yesno:'true,false' }} }">

  <!-- Poster -->
  <a href="{% url 'films:detail' movie.slug %}" class="block aspect-[2/3] relative overflow-hidden rounded-xl bg-[#161b24]">
    {% if movie.poster_path %}
    <img src="{{ movie.poster_path }}"
         alt="{{ movie.title }}"
         loading="lazy"
         class="w-full h-full object-cover transition duration-300 group-hover:scale-105">
    {% else %}
    <div class="w-full h-full flex items-center justify-center text-4xl">🎬</div>
    {% endif %}

    <!-- Hover overlay -->
    <div class="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition duration-300
                flex items-center justify-center">
      <span class="bg-primary text-white rounded-full w-12 h-12 flex items-center justify-center text-xl">▶</span>
    </div>

    <!-- Badges (top-left) -->
    <div class="absolute top-2 left-2 flex gap-1 flex-wrap">
      {% if movie.medium_type == 'Anime' %}
      <span class="badge-sm badge-purple">Anime</span>
      {% elif movie.medium_type == 'Series' %}
      <span class="badge-sm badge-blue">Series</span>
      {% endif %}
      {% if movie.status == 'Ongoing' %}
      <span class="badge-sm badge-green">● Đang chiếu</span>
      {% endif %}
    </div>

    <!-- IMDB rating (bottom-right) -->
    {% if movie.imdb_rating %}
    <div class="absolute bottom-2 right-2 bg-black/70 backdrop-blur rounded px-1.5 py-0.5
                text-yellow-400 text-xs font-bold flex items-center gap-1">
      ⭐ {{ movie.imdb_rating }}
    </div>
    {% endif %}
  </a>

  <!-- Watchlist button -->
  <button @click="inWatchlist = !inWatchlist"
          hx-post="{% url 'watchlist:toggle' movie.slug %}"
          hx-swap="none"
          class="absolute top-2 right-2 w-8 h-8 rounded-full bg-black/70 backdrop-blur
                 flex items-center justify-center opacity-0 group-hover:opacity-100
                 transition hover:bg-primary">
    <span x-text="inWatchlist ? '🔖' : '+'"></span>
  </button>

  <!-- Info -->
  <div class="mt-2.5 px-0.5">
    <h3 class="text-sm font-semibold leading-tight line-clamp-2 text-[#dde1f0] group-hover:text-primary transition">
      <a href="{% url 'films:detail' movie.slug %}">{{ movie.title }}</a>
    </h3>
    <p class="text-xs text-[#636b88] mt-1">
      {{ movie.release_year }}{% if movie.total_episodes > 1 %} · {{ movie.episodes.count }}/{{ movie.total_episodes|default:'?' }} tập{% endif %}
    </p>
  </div>
</article>
```

---

### 23.7 Movie Detail — `apps/films/templates/films/detail.html`

```html
{% extends 'base.html' %}
{% block title %}{{ movie.title }}{% endblock %}
{% block meta_desc %}{{ movie.short_description }}{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 py-8" x-data="movieDetailPage()">

  <!-- ══ HERO ROW ══════════════════════════════════════════ -->
  <div class="flex flex-col lg:flex-row gap-8 mb-10">

    <!-- Poster -->
    <div class="flex-shrink-0 w-full lg:w-60">
      <img src="{{ movie.poster_path }}" alt="{{ movie.title }}"
           class="w-full lg:w-60 aspect-[2/3] object-cover rounded-xl shadow-2xl">
    </div>

    <!-- Info -->
    <div class="flex-1 min-w-0">
      <div class="flex flex-wrap gap-2 mb-3">
        <span class="badge badge-primary">{{ movie.get_medium_type_display }}</span>
        <span class="badge badge-outline">{{ movie.get_status_display }}</span>
        {% if movie.content_rating %}<span class="badge badge-outline">{{ movie.content_rating }}</span>{% endif %}
      </div>

      <h1 class="text-3xl md:text-4xl font-extrabold leading-tight mb-1 tracking-tight">
        {{ movie.title }}
      </h1>
      {% if movie.original_title %}
      <p class="text-[#636b88] text-base mb-3">{{ movie.original_title }}</p>
      {% endif %}

      <!-- Meta row -->
      <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-[#a8afc8] mb-4">
        {% if movie.release_year %}<span>📅 {{ movie.release_year }}</span>{% endif %}
        {% if movie.imdb_rating %}<span class="text-yellow-400 font-semibold">⭐ {{ movie.imdb_rating }} IMDb</span>{% endif %}
        {% if movie.avg_rating %}<span class="text-primary font-semibold">★ {{ movie.avg_rating|floatformat:1 }} site</span>{% endif %}
        {% if movie.total_episodes and movie.total_episodes > 1 %}<span>📺 {{ movie.total_episodes }} tập</span>{% endif %}
        {% for country in movie.countries.all %}<span>🌏 {{ country.country_name }}</span>{% endfor %}
      </div>

      <!-- Genres -->
      <div class="flex flex-wrap gap-2 mb-4">
        {% for genre in movie.genres.all %}
        <a href="{% url 'films:movies' %}?genre={{ genre.slug }}"
           class="text-xs px-3 py-1 bg-[#161b24] border border-[#222736] rounded-full
                  text-[#a8afc8] hover:border-primary hover:text-primary transition">
          {{ genre.genre_name }}
        </a>
        {% endfor %}
      </div>

      <p class="text-[#a8afc8] leading-relaxed mb-6 text-sm max-w-2xl">
        {{ movie.description }}
      </p>

      <!-- Action buttons -->
      <div class="flex flex-wrap gap-3">
        {% if current_episode %}
        <a href="#player" onclick="scrollToPlayer()" class="btn-primary flex items-center gap-2">
          ▶ Xem ngay — Tập {{ current_episode.episode_number }}
        </a>
        {% endif %}

        <!-- Watchlist toggle -->
        <button id="watchlist-btn"
                hx-post="{% url 'watchlist:toggle' movie.slug %}"
                hx-target="#watchlist-btn"
                hx-swap="outerHTML"
                class="btn-secondary flex items-center gap-2">
          {% if in_watchlist %}🔖 Đã lưu{% else %}+ Thêm vào danh sách{% endif %}
        </button>

        <!-- Trailers -->
        {% if movie.trailers.exists %}
        <button @click="showTrailer = true" class="btn-secondary flex items-center gap-2">
          🎬 Trailer
        </button>
        {% endif %}
      </div>

      <!-- Star Rating -->
      {% if user.is_authenticated %}
      <div class="mt-6 flex items-center gap-3">
        <span class="text-sm text-[#636b88]">Đánh giá của bạn:</span>
        <div class="flex gap-1" id="star-rating">
          {% for i in "12345678910"|make_list %}
          <button hx-post="{% url 'ratings:rate' movie.slug %}"
                  hx-vals='{"score": {{ forloop.counter }}}'
                  hx-target="#star-rating"
                  hx-swap="outerHTML"
                  class="text-xl transition hover:scale-125 {% if user_rating >= forloop.counter %}text-yellow-400{% else %}text-[#2d3447] hover:text-yellow-400{% endif %}">★</button>
          {% endfor %}
          {% if user_rating %}<span class="text-sm text-[#636b88] ml-2">{{ user_rating }}/10</span>{% endif %}
        </div>
      </div>
      {% endif %}
    </div>
  </div>

  <!-- ══ VIDEO PLAYER ═══════════════════════════════════════ -->
  {% if current_episode %}
  <div id="player" class="mb-8">
    <div class="bg-black rounded-2xl overflow-hidden shadow-2xl relative aspect-video">
      <video id="hls-player"
             class="w-full h-full"
             controls
             playsinline
             poster="{{ current_episode.thumbnail_path }}">
        <!-- Subtitles -->
        {% for sub in current_episode.subtitles.all %}
        <track kind="subtitles"
               src="{{ sub.sub_path }}"
               srclang="{{ sub.language_code }}"
               label="{{ sub.language_label }}"
               {% if sub.is_default %}default{% endif %}>
        {% endfor %}
      </video>

      <!-- Player overlay controls (quality, speed) -->
      <div class="absolute top-3 right-3 flex gap-2" x-data="{ showControls: false }">
        <button @click="showControls = !showControls"
                class="bg-black/60 backdrop-blur text-white text-xs px-2 py-1 rounded">
          ⚙ Chất lượng
        </button>
        <div x-show="showControls" @click.away="showControls = false"
             class="absolute top-full right-0 mt-1 bg-[#0f1218] border border-[#222736] rounded-lg py-1 min-w-32 shadow-xl">
          {% for quality in current_episode.qualities %}
          <button class="block w-full text-left px-4 py-2 text-sm text-[#a8afc8] hover:bg-[#161b24] hover:text-[#dde1f0]">
            {{ quality }}
          </button>
          {% endfor %}
        </div>
      </div>
    </div>

    <!-- Player meta bar -->
    <div class="mt-3 flex flex-wrap items-center justify-between gap-2 text-sm text-[#636b88]">
      <div>
        <span class="text-[#dde1f0] font-semibold">{{ current_episode.episode_name|default:movie.title }}</span>
        {% if current_episode.duration %}· {{ current_episode.duration }} phút{% endif %}
      </div>
      <!-- Report issue -->
      <button class="hover:text-[#dde1f0] transition text-xs">⚑ Báo lỗi video</button>
    </div>

    <!-- Auto-next progress bar -->
    <div id="auto-next-bar" class="hidden mt-2 bg-[#161b24] rounded-full h-1 overflow-hidden">
      <div id="auto-next-fill" class="h-full bg-primary transition-all duration-1000 w-0"></div>
    </div>
  </div>
  {% endif %}

  <!-- ══ SEASON / EPISODE LIST ══════════════════════════════ -->
  {% if movie.total_seasons > 1 %}
  <div class="mb-4 flex gap-2 overflow-x-auto pb-1">
    {% for s_num in season_numbers %}
    <a href="?s={{ s_num }}&tap=1"
       class="px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition
              {% if s_num == current_season %}bg-primary text-white{% else %}bg-[#161b24] text-[#a8afc8] hover:bg-[#1d2330]{% endif %}">
      Mùa {{ s_num }}
    </a>
    {% endfor %}
  </div>
  {% endif %}

  <div class="mb-10">
    <h3 class="text-base font-semibold mb-3 text-[#a8afc8]">
      Danh sách tập — Mùa {{ current_season }}
    </h3>
    <div class="grid grid-cols-4 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2">
      {% for ep in season_episodes %}
      <a href="?s={{ ep.season_number }}&tap={{ ep.episode_number }}"
         class="aspect-square flex items-center justify-center rounded-lg text-sm font-medium transition
                {% if ep == current_episode %}
                  bg-primary text-white shadow-lg shadow-primary/30
                {% else %}
                  bg-[#161b24] text-[#a8afc8] hover:bg-[#1d2330] hover:text-[#dde1f0]
                {% endif %}
                {% if not ep.is_free %}ring-1 ring-yellow-500/40{% endif %}">
        {{ ep.episode_number }}
        {% if not ep.is_free %}<span class="text-yellow-400 text-xs">👑</span>{% endif %}
      </a>
      {% endfor %}
    </div>
  </div>

  <!-- ══ CAST & CREW ════════════════════════════════════════ -->
  {% if cast %}
  <div class="mb-10">
    <h3 class="section-title mb-4">Diễn viên</h3>
    <div class="flex gap-4 overflow-x-auto pb-2">
      {% for cc in cast %}
      <a href="{% url 'films:person' cc.person.slug %}"
         class="flex-shrink-0 text-center w-24 group">
        <img src="{{ cc.person.avatar_path|default:'/static/img/person-placeholder.webp' }}"
             alt="{{ cc.person.full_name }}"
             class="w-20 h-20 rounded-full object-cover mx-auto mb-2 ring-2 ring-[#222736] group-hover:ring-primary transition">
        <p class="text-xs font-medium text-[#dde1f0] leading-tight line-clamp-2 group-hover:text-primary transition">
          {{ cc.person.full_name }}
        </p>
        {% if cc.character_name %}
        <p class="text-xs text-[#636b88] mt-0.5 line-clamp-1">{{ cc.character_name }}</p>
        {% endif %}
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- ══ TRAILERS ═══════════════════════════════════════════ -->
  {% if trailers %}
  <div class="mb-10">
    <h3 class="section-title mb-4">Trailer</h3>
    <div class="flex gap-4 overflow-x-auto pb-2">
      {% for trailer in trailers %}
      <a href="{{ trailer.trailer_path }}" target="_blank" rel="noopener"
         class="flex-shrink-0 w-64 bg-[#161b24] border border-[#222736] rounded-xl overflow-hidden hover:border-primary transition group">
        <div class="aspect-video bg-[#1d2330] flex items-center justify-center text-3xl group-hover:bg-[#222736] transition">🎬</div>
        <div class="p-3">
          <p class="text-sm font-medium text-[#dde1f0]">{{ trailer.label }}</p>
          {% if trailer.language %}<p class="text-xs text-[#636b88]">{{ trailer.language }}</p>{% endif %}
        </div>
      </a>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <!-- ══ COMMENTS ═══════════════════════════════════════════ -->
  <div id="comments-section" class="mb-10">
    <div class="flex items-center justify-between mb-6">
      <h3 class="section-title">💬 Bình luận</h3>
      <span class="text-sm text-[#636b88]">{{ movie.comment_count }} bình luận</span>
    </div>

    <!-- Comment form -->
    {% if user.is_authenticated %}
    <form hx-post="{% url 'comments:create' movie.slug %}"
          hx-target="#comment-list"
          hx-swap="afterbegin"
          hx-on::after-request="this.reset()"
          class="mb-6 flex gap-3">
      {% csrf_token %}
      <img src="{{ user.avatar.url|default:'/static/img/avatar-default.webp' }}"
           class="w-9 h-9 rounded-full flex-shrink-0 object-cover">
      <div class="flex-1">
        <textarea name="body" rows="2" placeholder="Bình luận của bạn..."
                  class="input-field w-full resize-none"
                  required maxlength="1000"></textarea>
        <div class="flex justify-end mt-2">
          <button type="submit" class="btn-primary text-sm px-4 py-1.5">Gửi</button>
        </div>
      </div>
    </form>
    {% else %}
    <div class="bg-[#161b24] border border-[#222736] rounded-xl p-4 text-center text-[#636b88] text-sm mb-6">
      <a href="{% url 'users:login' %}" class="text-primary hover:underline">Đăng nhập</a> để bình luận
    </div>
    {% endif %}

    <!-- Comment list -->
    <div id="comment-list" class="space-y-4">
      {% for comment in comments %}
      {% include 'partials/comment.html' %}
      {% endfor %}
    </div>

    <!-- Load more -->
    {% if has_more_comments %}
    <div class="text-center mt-6">
      <button hx-get="{% url 'comments:list' movie.slug %}?page={{ next_comment_page }}"
              hx-target="#comment-list"
              hx-swap="beforeend"
              hx-indicator="#comments-loader"
              class="btn-secondary text-sm">
        Xem thêm bình luận
      </button>
      <span id="comments-loader" class="htmx-indicator ml-2 text-[#636b88] text-sm">Đang tải...</span>
    </div>
    {% endif %}
  </div>

  <!-- ══ RELATED MOVIES ════════════════════════════════════ -->
  {% if related_movies %}
  <div>
    <h3 class="section-title mb-4">Có thể bạn thích</h3>
    <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {% for movie in related_movies %}
      {% include 'partials/movie_card.html' %}
      {% endfor %}
    </div>
  </div>
  {% endif %}

</div>

<!-- ══ TRAILER MODAL ════════════════════════════════════════ -->
<div x-show="showTrailer" x-cloak @keydown.escape.window="showTrailer = false"
     class="fixed inset-0 z-50 flex items-center justify-center p-4">
  <div @click="showTrailer = false" class="absolute inset-0 bg-black/80 backdrop-blur-sm"></div>
  <div class="relative z-10 w-full max-w-4xl bg-[#0f1218] rounded-2xl overflow-hidden shadow-2xl">
    <div class="aspect-video bg-black">
      <iframe x-show="showTrailer"
              src="{{ movie.trailers.first.trailer_path }}?autoplay=1"
              class="w-full h-full" allowfullscreen></iframe>
    </div>
    <button @click="showTrailer = false"
            class="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black transition">✕</button>
  </div>
</div>

{% endblock %}

{% block extra_scripts %}
<script>
  // HLS.js player init
  const video = document.getElementById('hls-player');
  const m3u8  = "{{ current_episode.m3u8_path|escapejs }}";

  if (video && m3u8) {
    if (Hls.isSupported()) {
      const hls = new Hls({ maxBufferLength: 60, capLevelToPlayerSize: true });
      hls.loadSource(m3u8);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        // Resume from watch history
        const progress = {{ watch_progress|default:0 }};
        if (progress > 10) video.currentTime = progress;
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      video.src = m3u8;
    }

    // Save watch progress every 15s
    let saveInterval;
    video.addEventListener('play', () => {
      saveInterval = setInterval(() => {
        fetch("{% url 'history:update' current_episode.id %}", {
          method: 'POST',
          headers: { 'X-CSRFToken': getCsrfToken(), 'Content-Type': 'application/json' },
          body: JSON.stringify({ progress_seconds: Math.floor(video.currentTime) })
        });
      }, 15000);
    });
    video.addEventListener('pause',  () => clearInterval(saveInterval));
    video.addEventListener('ended',  () => { clearInterval(saveInterval); showAutoNext(); });
  }

  function movieDetailPage() {
    return { showTrailer: false };
  }
</script>
{% endblock %}
```

---

### 23.8 Search Results — `apps/films/templates/films/search.html`

```html
{% extends 'base.html' %}
{% block title %}Tìm kiếm: {{ query }}{% endblock %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 py-8">

  <!-- Search header -->
  <div class="mb-8">
    <h1 class="text-2xl font-bold mb-2">
      {% if query %}Kết quả cho "<span class="text-primary">{{ query }}</span>"
      {% else %}Tìm kiếm phim{% endif %}
    </h1>
    <p class="text-[#636b88] text-sm">{{ total_count }} kết quả</p>
  </div>

  <!-- Filter row -->
  <div class="flex flex-wrap gap-3 mb-8 p-4 bg-[#0f1218] border border-[#222736] rounded-xl"
       x-data="{ showFilters: false }">
    <form method="get" id="filter-form" class="contents">
      <input type="hidden" name="q" value="{{ query }}">

      <select name="type" onchange="document.getElementById('filter-form').submit()"
              class="input-field-sm">
        <option value="">Tất cả loại</option>
        <option value="Movie"       {% if request.GET.type == 'Movie' %}selected{% endif %}>Phim lẻ</option>
        <option value="Series"      {% if request.GET.type == 'Series' %}selected{% endif %}>Phim bộ</option>
        <option value="Anime"       {% if request.GET.type == 'Anime' %}selected{% endif %}>Anime</option>
        <option value="Documentary" {% if request.GET.type == 'Documentary' %}selected{% endif %}>Tài liệu</option>
      </select>

      <select name="genre" onchange="this.form.submit()" class="input-field-sm">
        <option value="">Tất cả thể loại</option>
        {% for genre in genres %}
        <option value="{{ genre.slug }}" {% if request.GET.genre == genre.slug %}selected{% endif %}>
          {{ genre.genre_name }}
        </option>
        {% endfor %}
      </select>

      <select name="year" onchange="this.form.submit()" class="input-field-sm">
        <option value="">Tất cả năm</option>
        {% for year in year_choices %}
        <option value="{{ year }}" {% if request.GET.year == year|stringformat:"s" %}selected{% endif %}>{{ year }}</option>
        {% endfor %}
      </select>

      <select name="sort" onchange="this.form.submit()" class="input-field-sm">
        <option value="-created_at"  {% if request.GET.sort == '-created_at' %}selected{% endif %}>Mới nhất</option>
        <option value="-imdb_rating" {% if request.GET.sort == '-imdb_rating' %}selected{% endif %}>Điểm IMDb</option>
        <option value="-view_count"  {% if request.GET.sort == '-view_count' %}selected{% endif %}>Xem nhiều nhất</option>
        <option value="-release_year"{% if request.GET.sort == '-release_year' %}selected{% endif %}>Năm phát hành</option>
      </select>
    </form>
  </div>

  <!-- Results grid -->
  {% if movies %}
  <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4 mb-10">
    {% for movie in movies %}
    {% include 'partials/movie_card.html' %}
    {% endfor %}
  </div>

  <!-- Pagination -->
  {% include 'partials/pagination.html' %}

  {% else %}
  <div class="text-center py-24">
    <div class="text-6xl mb-4">🎬</div>
    <h3 class="text-xl font-semibold mb-2">Không tìm thấy kết quả</h3>
    <p class="text-[#636b88] text-sm">Thử từ khóa khác hoặc bỏ bộ lọc</p>
  </div>
  {% endif %}
</div>
{% endblock %}
```

---

### 23.9 User Profile — `apps/users/templates/users/profile.html`

```html
{% extends 'base.html' %}
{% block title %}Trang cá nhân — {{ profile_user.display_name|default:profile_user.email }}{% endblock %}

{% block content %}
<div class="max-w-5xl mx-auto px-4 py-8">

  <!-- Profile header -->
  <div class="flex flex-col sm:flex-row items-start sm:items-end gap-6 mb-8
              p-6 bg-[#0f1218] border border-[#222736] rounded-2xl">
    <div class="relative">
      <img src="{{ profile_user.avatar.url|default:'/static/img/avatar-default.webp' }}"
           class="w-24 h-24 rounded-full object-cover ring-4 ring-[#222736]">
      {% if user == profile_user %}
      <label class="absolute bottom-0 right-0 w-7 h-7 bg-primary rounded-full
                    flex items-center justify-center cursor-pointer hover:bg-indigo-600 transition"
             for="avatar-upload">
        ✏
        <input id="avatar-upload" type="file" accept="image/*" class="hidden"
               hx-post="{% url 'users:update_avatar' %}" hx-encoding="multipart/form-data">
      </label>
      {% endif %}
    </div>

    <div class="flex-1 min-w-0">
      <h1 class="text-2xl font-bold">{{ profile_user.display_name|default:"Người dùng" }}</h1>
      <p class="text-[#636b88] text-sm mt-1">{{ profile_user.email }}</p>
      <div class="flex gap-4 mt-3 text-sm text-[#a8afc8]">
        <span>🎬 <strong class="text-[#dde1f0]">{{ profile.total_movies_watched }}</strong> phim đã xem</span>
        <span>⏱ <strong class="text-[#dde1f0]">{{ profile.total_watch_time }}</strong> phút</span>
      </div>
    </div>

    {% if user == profile_user %}
    <a href="{% url 'users:settings' %}" class="btn-secondary text-sm">⚙ Cài đặt</a>
    {% endif %}
  </div>

  <!-- Tabs -->
  <div class="flex gap-1 border-b border-[#222736] mb-8" x-data="{ tab: 'history' }">
    {% if user == profile_user %}
    <button @click="tab = 'history'" :class="tab === 'history' ? 'tab-active' : 'tab'" class="tab">🕐 Lịch sử</button>
    <button @click="tab = 'watchlist'" :class="tab === 'watchlist' ? 'tab-active' : 'tab'" class="tab">🔖 Danh sách</button>
    <button @click="tab = 'ratings'" :class="tab === 'ratings' ? 'tab-active' : 'tab'" class="tab">★ Đã đánh giá</button>
    {% endif %}
    <button @click="tab = 'comments'" :class="tab === 'comments' ? 'tab-active' : 'tab'" class="tab">💬 Bình luận</button>

    <!-- Tab contents (loaded via HTMX) -->
    <div x-show="tab === 'history'"
         hx-get="{% url 'history:user_history' profile_user.pk %}"
         hx-trigger="intersect once"
         hx-target="this">
      <div class="text-center py-8 text-[#636b88]">Đang tải...</div>
    </div>
    <div x-show="tab === 'watchlist'" hx-get="{% url 'watchlist:user' profile_user.pk %}"
         hx-trigger="intersect once" hx-target="this">
      <div class="text-center py-8 text-[#636b88]">Đang tải...</div>
    </div>
  </div>
</div>
{% endblock %}
```

---

### 23.10 Login & Register Pages

```html
<!-- apps/users/templates/users/login.html -->
{% extends 'base.html' %}
{% block title %}Đăng nhập{% endblock %}

{% block content %}
<div class="min-h-[80vh] flex items-center justify-center px-4 py-12">
  <div class="w-full max-w-md">

    <!-- Card -->
    <div class="bg-[#0f1218] border border-[#222736] rounded-2xl p-8 shadow-2xl">
      <div class="text-center mb-8">
        <div class="text-4xl mb-3">🎬</div>
        <h1 class="text-2xl font-bold">Chào mừng trở lại</h1>
        <p class="text-[#636b88] text-sm mt-1">Đăng nhập để tiếp tục xem</p>
      </div>

      <!-- Error messages -->
      {% if form.errors %}
      <div class="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 mb-6 text-red-400 text-sm">
        {{ form.non_field_errors }}
      </div>
      {% endif %}

      <form method="post" class="space-y-4">
        {% csrf_token %}
        <input type="hidden" name="next" value="{{ next }}">

        <div>
          <label class="form-label">Email</label>
          <input type="email" name="email" placeholder="you@example.com"
                 value="{{ form.email.value|default:'' }}"
                 class="input-field w-full" required autofocus>
        </div>

        <div>
          <div class="flex items-center justify-between mb-1">
            <label class="form-label">Mật khẩu</label>
            <a href="{% url 'users:password_reset' %}" class="text-xs text-primary hover:underline">Quên mật khẩu?</a>
          </div>
          <input type="password" name="password" placeholder="••••••••"
                 class="input-field w-full" required>
        </div>

        <div class="flex items-center gap-2">
          <input type="checkbox" name="remember" id="remember" class="w-4 h-4 rounded accent-primary">
          <label for="remember" class="text-sm text-[#a8afc8]">Ghi nhớ đăng nhập</label>
        </div>

        <button type="submit" class="btn-primary w-full py-3 text-base">Đăng nhập</button>
      </form>

      <p class="text-center text-sm text-[#636b88] mt-6">
        Chưa có tài khoản?
        <a href="{% url 'users:register' %}" class="text-primary hover:underline font-medium">Đăng ký ngay</a>
      </p>
    </div>
  </div>
</div>
{% endblock %}
```

```html
<!-- apps/users/templates/users/register.html -->
{% extends 'base.html' %}
{% block title %}Đăng ký{% endblock %}

{% block content %}
<div class="min-h-[80vh] flex items-center justify-center px-4 py-12">
  <div class="w-full max-w-md">
    <div class="bg-[#0f1218] border border-[#222736] rounded-2xl p-8 shadow-2xl">
      <div class="text-center mb-8">
        <div class="text-4xl mb-3">🎬</div>
        <h1 class="text-2xl font-bold">Tạo tài khoản</h1>
        <p class="text-[#636b88] text-sm mt-1">Hoàn toàn miễn phí</p>
      </div>

      <form method="post"
            hx-post="{% url 'users:register' %}"
            hx-target="#register-form-area"
            class="space-y-4" id="register-form-area">
        {% csrf_token %}

        <div>
          <label class="form-label">Tên hiển thị</label>
          <input type="text" name="display_name" placeholder="Tên của bạn" class="input-field w-full" required>
        </div>

        <div>
          <label class="form-label">Email</label>
          <input type="email" name="email" placeholder="you@example.com"
                 class="input-field w-full" required
                 hx-post="{% url 'users:check_email' %}"
                 hx-trigger="blur"
                 hx-target="#email-feedback"
                 hx-include="[name='email']">
          <div id="email-feedback" class="mt-1 text-xs"></div>
        </div>

        <div>
          <label class="form-label">Mật khẩu</label>
          <input type="password" name="password1" placeholder="Tối thiểu 8 ký tự" class="input-field w-full" required>
        </div>

        <div>
          <label class="form-label">Xác nhận mật khẩu</label>
          <input type="password" name="password2" placeholder="Nhập lại mật khẩu" class="input-field w-full" required>
        </div>

        <p class="text-xs text-[#636b88]">
          Bằng cách đăng ký, bạn đồng ý với <a href="/terms" class="text-primary hover:underline">Điều khoản</a>
          và <a href="/privacy" class="text-primary hover:underline">Chính sách bảo mật</a>.
        </p>

        <button type="submit" class="btn-primary w-full py-3 text-base">Đăng ký</button>
      </form>

      <p class="text-center text-sm text-[#636b88] mt-6">
        Đã có tài khoản?
        <a href="{% url 'users:login' %}" class="text-primary hover:underline font-medium">Đăng nhập</a>
      </p>
    </div>
  </div>
</div>
{% endblock %}
```

---

### 23.11 CSS Components — `static/css/components.css`

```css
/* ── Buttons ─────────────────────────────────────────────── */
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center;
  background: #6272f0; color: white;
  padding: 10px 20px; border-radius: 8px;
  font-weight: 600; font-size: 14px;
  border: none; cursor: pointer;
  transition: all 150ms ease;
  text-decoration: none;
}
.btn-primary:hover { background: #7282ff; transform: translateY(-1px); box-shadow: 0 4px 20px rgba(98,114,240,.4); }
.btn-primary:active { transform: translateY(0); }

.btn-secondary {
  display: inline-flex; align-items: center; justify-content: center;
  background: #161b24; color: #a8afc8;
  padding: 10px 20px; border-radius: 8px;
  font-weight: 600; font-size: 14px;
  border: 1px solid #222736; cursor: pointer;
  transition: all 150ms ease; text-decoration: none;
}
.btn-secondary:hover { background: #1d2330; color: #dde1f0; border-color: #2d3447; }

/* ── Form Inputs ─────────────────────────────────────────── */
.input-field {
  background: #161b24; color: #dde1f0;
  border: 1px solid #222736; border-radius: 8px;
  padding: 10px 14px; font-size: 14px;
  transition: all 150ms ease; outline: none;
  font-family: 'Sora', sans-serif;
}
.input-field:focus { border-color: #6272f0; box-shadow: 0 0 0 3px rgba(98,114,240,.15); }
.input-field::placeholder { color: #636b88; }

.input-field-sm {
  background: #161b24; color: #a8afc8;
  border: 1px solid #222736; border-radius: 6px;
  padding: 6px 10px; font-size: 13px;
  transition: border-color 150ms; outline: none;
}
.input-field-sm:focus { border-color: #6272f0; }

.form-label { display: block; font-size: 13px; font-weight: 500; color: #a8afc8; margin-bottom: 6px; }

/* ── Badges ──────────────────────────────────────────────── */
.badge         { display: inline-block; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 4px; letter-spacing: .04em; }
.badge-primary { background: rgba(98,114,240,.15); color: #6272f0; border: 1px solid rgba(98,114,240,.3); }
.badge-outline { background: transparent; color: #a8afc8; border: 1px solid #2d3447; }
.badge-sm      { font-size: 10px; padding: 2px 6px; border-radius: 4px; font-weight: 700; }
.badge-purple  { background: rgba(167,139,250,.15); color: #a78bfa; }
.badge-blue    { background: rgba(56,200,240,.12); color: #38c8f0; }
.badge-green   { background: rgba(34,197,94,.12); color: #22c55e; }

/* ── Navigation ──────────────────────────────────────────── */
.nav-link {
  padding: 7px 12px; border-radius: 7px;
  font-size: 14px; font-weight: 500; color: #636b88;
  text-decoration: none; transition: all 150ms;
}
.nav-link:hover { background: #161b24; color: #dde1f0; }
.nav-link.active { color: #dde1f0; background: #1d2330; }

.mobile-nav-link {
  display: block; padding: 10px 12px; border-radius: 8px;
  font-size: 15px; color: #a8afc8; text-decoration: none;
  transition: all 150ms;
}
.mobile-nav-link:hover { background: #161b24; color: #dde1f0; }

.dropdown-item {
  display: block; padding: 8px 16px;
  font-size: 14px; color: #a8afc8;
  text-decoration: none; transition: all 100ms;
}
.dropdown-item:hover { background: #161b24; color: #dde1f0; }

/* ── Tab ─────────────────────────────────────────────────── */
.tab        { padding: 10px 16px; font-size: 14px; font-weight: 500; color: #636b88; border-bottom: 2px solid transparent; background: none; border-top: none; border-left: none; border-right: none; cursor: pointer; transition: all 150ms; }
.tab:hover  { color: #a8afc8; }
.tab-active { color: #dde1f0 !important; border-bottom-color: #6272f0 !important; }

/* ── Section typography ──────────────────────────────────── */
.section-title  { font-size: 18px; font-weight: 700; color: #dde1f0; letter-spacing: -.02em; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }

/* ── Movie row (horizontal scroll) ──────────────────────── */
.movie-row {
  display: flex; gap: 14px;
  overflow-x: auto; padding-bottom: 8px;
  scrollbar-width: none; -ms-overflow-style: none;
}
.movie-row::-webkit-scrollbar { display: none; }
.movie-row .movie-card { flex-shrink: 0; width: 160px; }

/* ── Movie card ──────────────────────────────────────────── */
.movie-card { position: relative; }

/* ── HTMX loading indicator ──────────────────────────────── */
.htmx-indicator { opacity: 0; transition: opacity 200ms; }
.htmx-request .htmx-indicator { opacity: 1; }
.htmx-request.htmx-indicator  { opacity: 1; }

/* ── Comment ─────────────────────────────────────────────── */
.comment-card {
  background: #0f1218; border: 1px solid #222736;
  border-radius: 12px; padding: 16px;
}

/* ── Pagination ──────────────────────────────────────────── */
.page-btn {
  padding: 7px 12px; border-radius: 7px; font-size: 14px;
  color: #636b88; text-decoration: none; border: 1px solid #222736;
  transition: all 150ms; background: #0f1218;
}
.page-btn:hover  { background: #161b24; color: #dde1f0; }
.page-btn.active { background: #6272f0; color: white; border-color: #6272f0; }

/* ── Scrollbar ───────────────────────────────────────────── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #2d3447; border-radius: 3px; }

/* ── Alpine cloak ────────────────────────────────────────── */
[x-cloak] { display: none !important; }

/* ── Responsive utilities ────────────────────────────────── */
@media (max-width: 640px) {
  .movie-row .movie-card { width: 130px; }
  .section-title { font-size: 16px; }
}
```

---

### 23.12 JavaScript — `static/js/app.js`

```javascript
// ── CSRF token helper ────────────────────────────────────────
function getCsrfToken() {
  return document.cookie.split(';')
    .find(c => c.trim().startsWith('csrftoken='))
    ?.split('=')[1] ?? '';
}

// ── HTMX config ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Auto-include CSRF token in all HTMX requests
  document.body.addEventListener('htmx:configRequest', (evt) => {
    evt.detail.headers['X-CSRFToken'] = getCsrfToken();
  });

  // Toast on HTMX success responses with HX-Toast header
  document.body.addEventListener('htmx:afterRequest', (evt) => {
    const msg = evt.detail.xhr.getResponseHeader('HX-Toast');
    if (msg) window.dispatchEvent(new CustomEvent('show-toast', { detail: { message: msg } }));
  });
});

// ── Toast manager (Alpine.js component) ─────────────────────
function toastManager() {
  return {
    toasts: [],
    show({ message, type = 'success' }) {
      const id = Date.now();
      this.toasts.push({ id, message, type, visible: true });
      setTimeout(() => {
        const t = this.toasts.find(t => t.id === id);
        if (t) t.visible = false;
        setTimeout(() => { this.toasts = this.toasts.filter(t => t.id !== id); }, 400);
      }, 3500);
    }
  };
}

// ── Lazy-load images ─────────────────────────────────────────
const imgObserver = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const img = entry.target;
      if (img.dataset.src) { img.src = img.dataset.src; imgObserver.unobserve(img); }
    }
  });
}, { rootMargin: '200px' });

document.querySelectorAll('img[data-src]').forEach(img => imgObserver.observe(img));

// ── Search dropdown close on outside click ───────────────────
document.addEventListener('click', (e) => {
  const dropdown = document.getElementById('search-results-dropdown');
  if (dropdown && !dropdown.parentElement.contains(e.target)) {
    dropdown.innerHTML = '';
  }
});

// ── Auto-next episode ─────────────────────────────────────────
function showAutoNext() {
  const bar  = document.getElementById('auto-next-bar');
  const fill = document.getElementById('auto-next-fill');
  const nextUrl = document.querySelector('[data-next-episode]')?.dataset.nextEpisode;
  if (!bar || !nextUrl) return;

  bar.classList.remove('hidden');
  let progress = 0;
  const timer = setInterval(() => {
    progress += 10;
    fill.style.width = progress + '%';
    if (progress >= 100) { clearInterval(timer); window.location.href = nextUrl; }
  }, 500);
}

// ── Scroll to player ─────────────────────────────────────────
function scrollToPlayer() {
  document.getElementById('player')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}
```

---

### 23.13 HLS Player — `static/js/player.js`

```javascript
// Full-featured HLS player with quality switching and subtitle support
class FilmPlayer {
  constructor(videoId, options = {}) {
    this.video   = document.getElementById(videoId);
    this.hls     = null;
    this.options = { maxBufferLength: 60, capLevelToPlayerSize: true, ...options };
  }

  load(m3u8Url, resumeTime = 0) {
    if (!this.video || !m3u8Url) return;

    if (Hls.isSupported()) {
      this.hls = new Hls(this.options);
      this.hls.loadSource(m3u8Url);
      this.hls.attachMedia(this.video);
      this.hls.on(Hls.Events.MANIFEST_PARSED, () => {
        if (resumeTime > 10) this.video.currentTime = resumeTime;
        this.video.play().catch(() => {});  // Autoplay may be blocked
        this._buildQualityMenu();
      });
      this.hls.on(Hls.Events.ERROR, (_, data) => {
        if (data.fatal) {
          switch (data.type) {
            case Hls.ErrorTypes.NETWORK_ERROR: this.hls.startLoad(); break;
            case Hls.ErrorTypes.MEDIA_ERROR:   this.hls.recoverMediaError(); break;
            default: console.error('Fatal HLS error:', data); break;
          }
        }
      });
    } else if (this.video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari — native HLS
      this.video.src = m3u8Url;
      if (resumeTime > 10) {
        this.video.addEventListener('loadedmetadata', () => { this.video.currentTime = resumeTime; }, { once: true });
      }
    }
  }

  _buildQualityMenu() {
    const container = document.getElementById('quality-menu');
    if (!container || !this.hls) return;
    container.innerHTML = '<button class="quality-opt" data-level="-1">Auto</button>';
    this.hls.levels.forEach((level, idx) => {
      const btn = document.createElement('button');
      btn.className  = 'quality-opt';
      btn.dataset.level = idx;
      btn.textContent = level.height ? `${level.height}p` : `Level ${idx + 1}`;
      btn.addEventListener('click', () => { this.hls.currentLevel = idx; });
      container.appendChild(btn);
    });
  }

  destroy() {
    if (this.hls) { this.hls.destroy(); this.hls = null; }
  }
}

// Auto-init if player exists
document.addEventListener('DOMContentLoaded', () => {
  const playerEl = document.getElementById('hls-player');
  if (!playerEl) return;

  const m3u8     = playerEl.dataset.src ?? '';
  const resume   = parseInt(playerEl.dataset.resume ?? '0', 10);
  const player   = new FilmPlayer('hls-player');
  player.load(m3u8, resume);

  // Keyboard shortcuts
  document.addEventListener('keydown', (e) => {
    if (['INPUT','TEXTAREA'].includes(e.target.tagName)) return;
    switch (e.key) {
      case ' ': e.preventDefault(); playerEl.paused ? playerEl.play() : playerEl.pause(); break;
      case 'ArrowRight': playerEl.currentTime += 10; break;
      case 'ArrowLeft':  playerEl.currentTime -= 10; break;
      case 'ArrowUp':    playerEl.volume = Math.min(1, playerEl.volume + 0.1); break;
      case 'ArrowDown':  playerEl.volume = Math.max(0, playerEl.volume - 0.1); break;
      case 'f': playerEl.requestFullscreen?.(); break;
    }
  });
});
```

---

### 23.14 Comment Partial — `templates/partials/comment.html`

```html
<div class="comment-card" id="comment-{{ comment.id }}" x-data="{ replyOpen: false }">
  <div class="flex items-start gap-3">
    <img src="{{ comment.user.avatar.url|default:'/static/img/avatar-default.webp' }}"
         class="w-8 h-8 rounded-full object-cover flex-shrink-0">
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1 flex-wrap">
        <span class="text-sm font-semibold text-[#dde1f0]">{{ comment.user.display_name|default:comment.user.email }}</span>
        <span class="text-xs text-[#636b88]">{{ comment.created_at|timesince }} trước</span>
      </div>
      <p class="text-sm text-[#a8afc8] leading-relaxed">{{ comment.content }}</p>

      <!-- Actions -->
      <div class="flex items-center gap-4 mt-2">
        <button hx-post="{% url 'comments:like' comment.id %}"
                hx-swap="outerHTML"
                hx-target="#like-{{ comment.id }}"
                class="flex items-center gap-1 text-xs text-[#636b88] hover:text-[#dde1f0] transition"
                id="like-{{ comment.id }}">
          👍 {{ comment.like_count }}
        </button>
        <button @click="replyOpen = !replyOpen"
                class="text-xs text-[#636b88] hover:text-primary transition">
          💬 Trả lời
        </button>
        {% if user == comment.user or user.is_staff %}
        <button hx-delete="{% url 'comments:delete' comment.id %}"
                hx-target="#comment-{{ comment.id }}"
                hx-swap="outerHTML"
                hx-confirm="Xóa bình luận này?"
                class="text-xs text-red-500/60 hover:text-red-400 transition ml-auto">
          Xóa
        </button>
        {% endif %}
      </div>

      <!-- Reply form (Alpine toggle) -->
      <div x-show="replyOpen" x-cloak x-data="{ replyOpen: false }" class="mt-3">
        <form hx-post="{% url 'comments:reply' comment.id %}"
              hx-target="#replies-{{ comment.id }}"
              hx-swap="beforeend"
              hx-on::after-request="this.reset(); replyOpen = false"
              class="flex gap-2">
          {% csrf_token %}
          <input type="text" name="body" placeholder="Viết trả lời..."
                 class="input-field flex-1 text-sm py-1.5" required maxlength="500">
          <button type="submit" class="btn-primary text-xs px-3 py-1.5">Gửi</button>
        </form>
      </div>

      <!-- Replies -->
      <div id="replies-{{ comment.id }}" class="mt-3 space-y-3 pl-4 border-l border-[#222736]">
        {% for reply in comment.replies.all|slice:":3" %}
        {% include 'partials/comment.html' with comment=reply %}
        {% endfor %}
      </div>
    </div>
  </div>
</div>
```

---

### 23.15 Search Dropdown Partial — `templates/partials/search_dropdown.html`

```html
<!-- Returned by hx-get on search input — instant preview -->
{% if movies %}
<div class="p-2">
  {% for movie in movies|slice:":6" %}
  <a href="{% url 'films:detail' movie.slug %}"
     class="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-[#161b24] transition group">
    {% if movie.poster_path %}
    <img src="{{ movie.poster_path }}" class="w-9 h-12 object-cover rounded flex-shrink-0">
    {% else %}
    <div class="w-9 h-12 bg-[#1d2330] rounded flex items-center justify-center text-lg flex-shrink-0">🎬</div>
    {% endif %}
    <div class="min-w-0 flex-1">
      <p class="text-sm font-medium text-[#dde1f0] truncate group-hover:text-primary transition">{{ movie.title }}</p>
      <p class="text-xs text-[#636b88]">{{ movie.medium_type }} · {{ movie.release_year }}</p>
    </div>
    {% if movie.imdb_rating %}
    <span class="text-yellow-400 text-xs font-bold flex-shrink-0">⭐ {{ movie.imdb_rating }}</span>
    {% endif %}
  </a>
  {% endfor %}

  {% if total_count > 6 %}
  <a href="{% url 'films:search' %}?q={{ query|urlencode }}"
     class="block text-center text-xs text-primary py-2 hover:underline">
    Xem tất cả {{ total_count }} kết quả →
  </a>
  {% endif %}
</div>
{% else %}
<div class="px-4 py-6 text-center text-[#636b88] text-sm">
  Không tìm thấy "<strong class="text-[#a8afc8]">{{ query }}</strong>"
</div>
{% endif %}
```

---

### 23.16 Pagination Partial — `templates/partials/pagination.html`

```html
{% if page_obj.has_other_pages %}
<nav class="flex items-center justify-center gap-2 mt-8 flex-wrap">
  {% if page_obj.has_previous %}
  <a href="?{% query_transform page=page_obj.previous_page_number %}" class="page-btn">‹ Trước</a>
  {% endif %}

  {% for num in page_obj.paginator.page_range %}
    {% if page_obj.number == num %}
    <span class="page-btn active">{{ num }}</span>
    {% elif num > page_obj.number|add:'-3' and num < page_obj.number|add:'3' %}
    <a href="?{% query_transform page=num %}" class="page-btn">{{ num }}</a>
    {% elif num == 1 or num == page_obj.paginator.num_pages %}
    <a href="?{% query_transform page=num %}" class="page-btn">{{ num }}</a>
    {% elif num == page_obj.number|add:'-3' or num == page_obj.number|add:'3' %}
    <span class="page-btn cursor-default">…</span>
    {% endif %}
  {% endfor %}

  {% if page_obj.has_next %}
  <a href="?{% query_transform page=page_obj.next_page_number %}" class="page-btn">Tiếp ›</a>
  {% endif %}
</nav>
{% endif %}
```

---

### 23.17 Views Update — `apps/films/views.py`

```python
# apps/films/views.py — Template views (không phải DRF)
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Prefetch
from django.views.decorators.http import require_GET
from django.core.cache import cache
from apps.films.models import Movie, Episode, Genre, Country, Person
from apps.films.tasks import increment_view_count   # BUG FIX: không import inline trong view function
from apps.history.models import WatchHistory
from apps.ratings.models import Rating              # BUG FIX: không import inline trong view function
from apps.watchlist.models import WatchlistItem


def home(request):
    # Featured hero (cache 5 min)
    featured = cache.get_or_set(
        'home_featured',
        lambda: Movie.objects.filter(is_featured=True, is_hidden=False)
                             .select_related().first(),
        300
    )

    # Trending (7 days)
    from apps.films.cache import get_trending_movies
    trending = Movie.objects.filter(
        id__in=[m['id'] for m in get_trending_movies()[:12]]
    ).prefetch_related('genres')

    # Continue watching (authenticated only)
    continue_watching = []
    if request.user.is_authenticated:
        continue_watching = (
            WatchHistory.objects.filter(user=request.user, completed=False)
            .select_related('episode__movie')
            .order_by('-watched_at')[:8]  # BUG FIX: watched_at (auto_now), không phải updated_at
        )

    # Genre sections (cache 10 min)
    # BUG FIX: Không cache QuerySet hay Model objects trực tiếp — django-redis JSONSerializer không serialize được.
    # Phải evaluate QuerySet thành list of dicts trước khi cache.
    genre_sections = cache.get('home_genre_sections')
    if not genre_sections:
        target_genres = Genre.objects.filter(
            slug__in=['hanh-dong', 'tinh-cam', 'kinh-di', 'hai-huoc', 'anime']
        )
        GENRE_EMOJIS = {'hanh-dong': '💥', 'tinh-cam': '💕', 'kinh-di': '👻', 'hai-huoc': '😂', 'anime': '⛩'}
        genre_sections = [
            {
                'genre_name': g.name,
                'genre_slug': g.slug,
                'emoji':      GENRE_EMOJIS.get(g.slug, '🎬'),
                'movie_ids':  list(
                    Movie.objects.filter(genres=g, is_hidden=False)
                                 .order_by('-view_count')
                                 .values_list('id', flat=True)[:12]
                ),
            }
            for g in target_genres
        ]
        cache.set('home_genre_sections', genre_sections, 600)

    # Hydrate genre_sections với Movie objects (không lưu vào cache)
    all_ids = {mid for s in genre_sections for mid in s['movie_ids']}
    movies_map = {m.id: m for m in Movie.objects.filter(id__in=all_ids).prefetch_related('genres')}
    genre_sections_hydrated = [
        {
            'genre_name': s['genre_name'],
            'genre_slug': s['genre_slug'],
            'emoji':      s['emoji'],
            'movies':     [movies_map[i] for i in s['movie_ids'] if i in movies_map],
        }
        for s in genre_sections
    ]

    new_releases = Movie.objects.filter(is_hidden=False).order_by('-created_at')[:12]

    return render(request, 'films/home.html', {
        'featured_movie':    featured,
        'trending':          trending,
        'continue_watching': continue_watching,
        'genre_sections':    genre_sections_hydrated,  # BUG FIX: dùng hydrated version (chứa Movie objects)
        'new_releases':      new_releases,
    })


def movie_detail(request, slug):
    movie = get_object_or_404(
        Movie.objects.prefetch_related(
            'genres', 'countries', 'tags', 'studios', 'trailers',
            Prefetch('episodes', queryset=Episode.objects.prefetch_related('subtitles')),
        ),
        slug=slug, is_hidden=False
    )

    # Season & episode logic
    current_season = int(request.GET.get('s', 1))
    current_ep_num = int(request.GET.get('tap', 1))

    season_episodes = movie.episodes.filter(season_number=current_season)
    current_episode = season_episodes.filter(episode_number=current_ep_num).first() or season_episodes.first()
    season_numbers  = sorted(movie.episodes.values_list('season_number', flat=True).distinct())

    # Watch progress (for resume)
    watch_progress = 0
    in_watchlist   = False
    user_rating    = None
    if request.user.is_authenticated and current_episode:
        hist = WatchHistory.objects.filter(
            user=request.user, episode=current_episode
        ).first()
        watch_progress = hist.progress_seconds if hist else 0
        in_watchlist   = WatchlistItem.objects.filter(user=request.user, movie=movie).exists()
        r = Rating.objects.filter(user=request.user, movie=movie).first()
        user_rating = r.score if r else None

    # Cast (top 10 cast members)
    cast = movie.moviecastcrew_set.filter(role='Cast').select_related('person').order_by('sort_order')[:10]

    # Related movies (same genre, cached)
    related_movies = Movie.objects.filter(
        genres__in=movie.genres.all(), is_hidden=False
    ).exclude(pk=movie.pk).distinct().order_by('-imdb_rating')[:10]

    # Increment view count (async via Celery)
    increment_view_count.delay(movie.pk)  # BUG FIX: import đã chuyển lên top-level

    return render(request, 'films/detail.html', {
        'movie':           movie,
        'current_episode': current_episode,
        'current_season':  current_season,
        'season_episodes': season_episodes,
        'season_numbers':  season_numbers,
        'cast':            cast,
        'trailers':        movie.trailers.all().order_by('sort_order'),
        'related_movies':  related_movies,
        'watch_progress':  watch_progress,
        'in_watchlist':    in_watchlist,
        'user_rating':     user_rating,
        'comments':        movie.comments.filter(parent=None).select_related('user')
                               .prefetch_related('replies__user')
                               .order_by('-created_at')[:20],
    })


@require_GET
def search_view(request):
    query   = request.GET.get('q', '').strip()
    movies  = Movie.objects.filter(is_hidden=False)

    if query:
        movies = movies.filter(title__icontains=query) | \
                 movies.filter(original_title__icontains=query)

    # Apply filters
    for field, param in [('medium_type', 'type'), ('status', 'status')]:
        val = request.GET.get(param)
        if val: movies = movies.filter(**{field: val})

    genre = request.GET.get('genre')
    if genre:    movies = movies.filter(genres__slug=genre)
    country = request.GET.get('country')
    if country:  movies = movies.filter(countries__code=country)  # BUG FIX: field là 'code' không phải 'country_code'
    year = request.GET.get('year')
    if year:     movies = movies.filter(release_year=year)

    sort_map = {
        '-imdb_rating': '-imdb_rating', '-view_count': '-view_count',
        '-release_year': '-release_year', '-created_at': '-created_at'
    }
    movies = movies.order_by(sort_map.get(request.GET.get('sort'), '-created_at'))
    movies = movies.distinct().prefetch_related('genres')

    paginator   = Paginator(movies, 24)
    page_obj    = paginator.get_page(request.GET.get('page', 1))
    total_count = paginator.count

    # HTMX partial response (search dropdown)
    if request.headers.get('HX-Request') and request.headers.get('HX-Trigger') == 'q':
        return render(request, 'partials/search_dropdown.html', {
            'movies': page_obj.object_list[:6],
            'total_count': total_count,
            'query': query,
        })

    return render(request, 'films/search.html', {
        'movies':      page_obj,
        'page_obj':    page_obj,
        'query':       query,
        'total_count': total_count,
        'genres':      Genre.objects.all(),
        'year_choices': range(2024, 1990, -1),
    })
```

---

### 23.18 URLs — `apps/films/urls.py`

```python
# apps/films/urls.py
from django.urls import path
from . import views

app_name = 'films'

urlpatterns = [
    path('',                   views.home,         name='home'),
    path('movies/',            views.search_view,  name='movies'),
    path('search/',            views.search_view,  name='search'),
    path('phim/<slug:slug>/',  views.movie_detail, name='detail'),
    path('nguoi/<slug:slug>/', views.person_detail, name='person'),
]
```

---

### 23.19 Responsive Breakpoints & Mobile UX

| Breakpoint | Width | Layout |
|---|---|---|
| `sm` | 640px | 2 cột grid, mobile nav mở |
| `md` | 768px | 3–4 cột grid |
| `lg` | 1024px | Sidebar hiện, 5 cột grid |
| `xl` | 1280px | 6 cột grid, layout max-w-7xl |

**Nguyên tắc mobile-first:**
- Hero banner: `h-[75vh]` → `h-[50vh]` trên mobile
- Movie row: horizontal scroll (không wrap) trên mobile
- Episode buttons: scroll ngang, không xuống dòng
- Player: luôn `aspect-video`, full width trên mobile
- Navbar: collapse thành hamburger menu dưới `md`
- Cast: scroll ngang thay vì grid
- Comment input: textarea collapse trên mobile

---

### 23.20 Performance Checklist (Frontend)

- [ ] **Lazy loading:** `loading="lazy"` trên tất cả ảnh `img` không critical
- [ ] **Image optimization:** Caddy phục vụ `.webp`, poster 300px width đủ
- [ ] **Font preconnect:** `<link rel="preconnect" href="https://fonts.googleapis.com">` trong `<head>`
- [ ] **HTMX target specificity:** chỉ replace phần nhỏ, không reload toàn trang
- [ ] **Redis cache:** home page, movie detail, genre sections — tránh query DB lặp lại
- [ ] **prefetch_related:** luôn dùng cho genres, countries, episodes trong list view
- [ ] **Tailwind production:** dùng `@tailwindcss/cli --minify` thay CDN khi production
- [ ] **HLS buffer:** `maxBufferLength: 60` — buffer 60s trước, phù hợp LAN nhanh
- [ ] **Auto-next episode:** chỉ trigger khi video kết thúc, không preload
- [ ] **HTMX `hx-boost`:** thêm vào `<body>` để navigation không reload full page

```html
<!-- body tag với hx-boost cho SPA-like navigation -->
<body hx-boost="true" hx-indicator="#page-loader" ...>
  <div id="page-loader" class="htmx-indicator fixed top-0 left-0 right-0 h-0.5 bg-primary z-50"></div>
</body>
```

### 23.21 Template Tag: query_transform (FIX-22)

```python
# apps/films/templatetags/query_helpers.py
from django import template

register = template.Library()

@template.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Giữ nguyên các query params hiện tại và ghi đè/thêm params mới.
    Dùng cho pagination: {% query_transform page=num %}
    """
    query = context['request'].GET.copy()
    for k, v in kwargs.items():
        query[k] = v
    return query.urlencode()
```

---

*FilmSite Architecture Plan v2.0 — Hoàn chỉnh & đã review*