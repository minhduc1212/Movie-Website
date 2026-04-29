from django.db import models

# ==========================================
# BẢNG 1: MOVIE (Thông tin chung của phim)
# ==========================================
class Movie(models.Model):
    # Định nghĩa các lựa chọn cho ENUM
    class Status(models.TextChoices):
        COMING_SOON = 'COMING_SOON', 'Coming Soon'
        ONGOING = 'ONGOING', 'Ongoing'
        COMPLETED = 'COMPLETED', 'Completed'
        DROP = 'DROP', 'Drop'

    class MediumType(models.TextChoices):
        MOVIE = 'MOVIE', 'Phim lẻ'
        SERIES = 'SERIES', 'Phim bộ'
        THEATER = 'THEATER', 'Phim chiếu rạp'
        ANIME = 'ANIME', 'Anime'
        DOCUMENTARY = 'DOCUMENTARY', 'Phim tài liệu'


    # Các cột dữ liệu
    movie_id = models.AutoField(primary_key=True)
    title = models.CharField(max_length=255, null=False, verbose_name="Tên phim")
    description = models.TextField(blank=True, null=True, verbose_name="Nội dung phim")
    release_year = models.IntegerField(blank=True, null=True, verbose_name="Năm phát hành")
    imdb_rating = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        blank=True, 
        null=True, 
        verbose_name="Điểm IMDB"
    )
    poster_path = models.CharField(max_length=500, blank=True, null=True, verbose_name="Đường dẫn ảnh poster")
    film_format = models.CharField(max_length=50, blank=True, null=True, verbose_name="Định dạng (2D, 3D, IMAX)")
    
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMING_SOON,
        verbose_name="Trạng thái"
    )
    
    medium_type = models.CharField(
        max_length=10,
        choices=MediumType.choices,
        default=MediumType.MOVIE,
        verbose_name="Loại hình"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")

    class Meta:
        db_table = 'movies' # Tên bảng trong Database
        verbose_name = "Phim"
        verbose_name_plural = "Danh sách phim"

    def __str__(self):
        return self.title

