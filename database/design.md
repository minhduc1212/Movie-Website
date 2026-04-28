# Thiết kế Cơ sở Dữ liệu Website Phim (Chi tiết)

Tài liệu này trình bày cấu trúc Database tối ưu cho hệ thống website phim, hỗ trợ cả **Phim lẻ (Movie/Cinema)** và **Phim bộ (TV Series/Drama)**.

---

## 1. Sơ đồ Quan hệ (Logic)
Để tránh trùng lặp dữ liệu, hệ thống được chia thành các bảng chính sau:
- **Movies**: Lưu thông tin gốc của bộ phim.
- **Episodes**: Lưu thông tin về các tập phim (Phim lẻ sẽ chỉ có 1 tập).
- **Genres**: Danh mục thể loại.
- **People**: Lưu thông tin Diễn viên & Đạo diễn.
- **Subtitles**: Quản lý phụ đề đa ngôn ngữ cho từng tập.

---

## 2. Chi tiết các Bảng (Tables)

### 2.1 Bảng `movies` (Thông tin chung)
Lưu trữ các thuộc tính định danh và mô tả của phim.

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `movie_id` | INT | Primary Key | ID duy nhất của phim. |
| `title` | VARCHAR(255) | Not Null | Tên phim. |
| `description` | TEXT | | Nội dung phim. |
| `release_year` | INT | | Năm phát hành. |
| `imdb_rating` | DECIMAL(3,1) | | Điểm IMDB. |
| `poster_path` | VARCHAR(500) | | Đường dẫn ảnh poster. |
| `film_format` | VARCHAR(50) | | Định dạng (2D, 3D, IMAX). |
| `status` | ENUM | | `Coming Soon`, `Ongoing`, `Completed`. |
| `medium_type` | ENUM | | `Movie` (Phim lẻ), `Series` (Phim bộ). |
| `created_at` | TIMESTAMP | | Ngày thêm vào hệ thống. |

### 2.2 Bảng `episodes` (Tập phim & Media)
Đây là bảng quan trọng nhất để phân biệt phim 1 tập và nhiều tập.

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `episode_id` | INT | Primary Key | ID duy nhất của tập. |
| `movie_id` | INT | Foreign Key | Liên kết với bảng `movies`. |
| `episode_number`| INT | | Tập số (Phim lẻ mặc định là 1). |
| `episode_name` | VARCHAR(255) | | Tên tập (ví dụ: Tập 1: Khởi nguồn). |
| `m3u8_path` | VARCHAR(500) | | Link stream HLS. |
| `movie_file_path`| VARCHAR(500) | | Link file gốc (MP4/MKV). |
| `duration` | INT | | Thời lượng (phút). |

### 2.3 Bảng `trailers`
Một phim có thể có nhiều trailer khác nhau.

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `trailer_id` | INT | Primary Key | |
| `movie_id` | INT | Foreign Key | Liên kết với bảng `movies`. |
| `trailer_path` | VARCHAR(500) | | Link video trailer (Youtube/Server). |
| `label` | VARCHAR(100) | | Nhãn (Teaser, Trailer 1, Trailer 2). |

### 2.4 Bảng `subtitles`
Phụ đề được gắn vào từng tập phim (vì mỗi tập có nội dung khác nhau).

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `sub_id` | INT | Primary Key | |
| `episode_id` | INT | Foreign Key | Liên kết với bảng `episodes`. |
| `language` | VARCHAR(50) | | Ngôn ngữ (Vietsub, Engsub). |
| `sub_path` | VARCHAR(500) | | Đường dẫn file (.vtt, .srt). |

### 2.5 Bảng `genres` & `movie_genres` (Thể loại)
Quan hệ Nhiều - Nhiều (Một phim có nhiều thể loại).

- **Bảng `genres`**: `genre_id`, `genre_name`.
- **Bảng `movie_genres`**: `movie_id`, `genre_id`.

### 2.6 Bảng `people` & `movie_cast_crew` (Diễn viên & Đạo diễn)
Quản lý Cast và Director trong cùng một bảng nhân sự để tối ưu.

- **Bảng `people`**: `person_id`, `full_name`, `avatar_path`, `bio`.
- **Bảng `movie_cast_crew`**:
    - `movie_id`: Foreign Key.
    - `person_id`: Foreign Key.
    - `role`: ENUM (`Director`, `Cast`).
    - `character_name`: Tên nhân vật (nếu là diễn viên).

---

## 3. Cách thức vận hành (Logic)

### Đối với Phim Chiếu Rạp (Phim lẻ - 1 tập)
1. Thêm 1 dòng vào bảng `movies` với `medium_type = 'Movie'`.
2. Thêm **duy nhất 1 dòng** vào bảng `episodes` với `episode_number = 1`.
3. Giao diện người dùng: Khi thấy là phim lẻ, hệ thống tự động lấy link media từ tập 1 và ẩn danh sách chọn tập.

### Đối với Phim Bộ (Series - Nhiều tập)
1. Thêm 1 dòng vào bảng `movies` với `medium_type = 'Series'`.
2. Thêm **nhiều dòng** vào bảng `episodes` tương ứng với số tập (Tập 1, Tập 2,...).
3. Giao diện người dùng: Hiển thị danh sách các tập phim dựa trên các bản ghi trong bảng `episodes` của `movie_id` đó.

---

## 4. Ví dụ truy vấn SQL lấy thông tin phim đầy đủ

```sql
SELECT 
    m.title, 
    m.release_year, 
    e.episode_number, 
    e.m3u8_path, 
    s.sub_path
FROM movies m
JOIN episodes e ON m.movie_id = e.movie_id
LEFT JOIN subtitles s ON e.episode_id = s.episode_id
WHERE m.movie_id = 123;
```
