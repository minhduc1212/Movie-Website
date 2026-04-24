from django.db import models

# ==========================================
# BẢNG 1: MOVIE (Thông tin chung của phim)
# ==========================================
class Movie(models.Model):
    class Format(models.TextChoices):
        MOVIE = 'movie', 'Phim Lẻ'
        SERIES = 'series', 'Phim Bộ'
        SHORT = 'short', 'Phim Ngắn'

    class Medium(models.TextChoices):
        LIVE_ACTION = 'live_action', 'Live-Action'
        ANIMATION = 'animation', 'Hoạt Hình'
        ANIME = 'anime', 'Anime'

    class Status(models.TextChoices):
        ONGOING = 'ongoing', 'Đang Phát Sóng'
        COMPLETED = 'completed', 'Đã Hoàn Thành'
        TRAILER = 'trailer', 'Sắp Chiếu'

    # --- Ánh xạ các trường dữ liệu ---
    # 1. Movie name
    title = models.CharField(max_length=255, verbose_name="Tên Phim")
    
    # 2. Description
    description = models.TextField(blank=True, null=True, verbose_name="Mô Tả")
    
    # 3. Genre
    genre = models.CharField(max_length=255, blank=True, null=True, verbose_name="Thể Loại")
    
    # 4. Director
    director = models.CharField(max_length=255, blank=True, null=True, verbose_name="Đạo Diễn")
    
    # 5. cast
    cast = models.TextField(blank=True, null=True, verbose_name="Diễn Viên")
    
    # 6. Release_year
    release_year = models.IntegerField(blank=True, null=True, verbose_name="Năm Phát Hành")
    
    # 7. IMDB_Rating
    imdb_rating = models.FloatField(blank=True, null=True, verbose_name="Điểm IMDb")
    
    # 8. path of poster image (Dùng CharField để lưu đường dẫn Caddy tĩnh)
    poster_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường Dẫn Ảnh Bìa (Poster)")
    
    # 9. path of trailer
    trailer_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường Dẫn Trailer")
    
    # 10. Film Format
    film_format = models.CharField(max_length=20, choices=Format.choices, default=Format.MOVIE, verbose_name="Định Dạng Phim")
    
    # 11. Medium of film
    medium = models.CharField(max_length=20, choices=Medium.choices, default=Medium.LIVE_ACTION, verbose_name="Hình Thức Sản Xuất")
    
    # 12. status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED, verbose_name="Trạng Thái")
    
    # Thời gian tự động lưu lúc tạo dữ liệu
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày Tạo")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Phim"
        verbose_name_plural = "Danh Sách Phim"

    def __str__(self):
        if self.release_year:
            return f"{self.title} ({self.release_year})"
        return self.title


# ==========================================
# BẢNG 2: EPISODE (Thông tin chi tiết từng tập)
# ==========================================
class Episode(models.Model):
    # Khóa ngoại: Liên kết tập này thuộc về bộ phim nào ở bảng trên
    movie = models.ForeignKey(Movie, related_name='episodes', on_delete=models.CASCADE, verbose_name="Thuộc Phim")
    
    # Thêm trường episode_number để sắp xếp tập phim chuẩn xác hơn là xếp theo bảng chữ cái
    episode_number = models.PositiveIntegerField(default=1, verbose_name="Số Thứ Tự Tập")

    # Tên tập (VD: Tập 1, Tập 2, hoặc Full)
    episode_name = models.CharField(max_length=255, default="Tập 1", verbose_name="Tên Tập")
    
    # --- Ánh xạ các trường đường dẫn file (Path) ---
    
    # 13. Path of m3u8 (Dành cho luồng HLS siêu mượt)
    m3u8_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường Dẫn m3u8 (HLS)")
    
    movie_file_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường Dẫn Video Gốc")
    
    sub_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường Dẫn Phụ Đề")

    class Meta:
        ordering = ['episode_number']
        verbose_name = "Tập Phim"
        verbose_name_plural = "Danh Sách Tập Phim"

    def __str__(self):
        return f"{self.movie.title} - {self.episode_name}"