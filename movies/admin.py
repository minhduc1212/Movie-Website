from django.contrib import admin
from .models import Movie, Episode

# Giao diện nhúng: Cho phép thêm Tập phim ngay bên trong trang thêm Phim
class EpisodeInline(admin.TabularInline):
    model = Episode
    extra = 1  # Hiển thị sẵn 1 dòng trống để điền tập mới

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    # Các cột sẽ hiển thị ở trang danh sách Phim
    list_display = ('title', 'film_format', 'medium', 'status', 'release_year', 'imdb_rating')
    
    # Bộ lọc ở cạnh phải màn hình
    list_filter = ('film_format', 'medium', 'status', 'release_year')
    
    # Thanh tìm kiếm
    search_fields = ('title', 'director', 'cast', 'genre')
    
    inlines = [EpisodeInline]

@admin.register(Episode)
class EpisodeAdmin(admin.ModelAdmin):
    list_display = ('movie', 'episode_name', 'm3u8_path', 'movie_file_path', 'sub_path')
    
    search_fields = ('movie__title', 'episode_name')
    
    list_filter = ('movie',)