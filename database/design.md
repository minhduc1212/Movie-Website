# Thiết kế Cơ sở Dữ liệu Website Phim (Hoàn chỉnh & Chi tiết)

Tài liệu này trình bày cấu trúc Database tối ưu cho hệ thống website phim, hỗ trợ đầy đủ các loại nội dung: **Phim lẻ (Movie)**, **Phim bộ (Series)**, **Anime**, **Phim ngắn**, **Documentary** và nhiều định dạng khác.

---

## 1. Sơ đồ Quan hệ (Logic)

```
movies ──< episodes ──< subtitles
  │
  ├──< trailers
  ├──< movie_genres >── genres
  ├──< movie_cast_crew >── people
  ├──< movie_countries >── countries
  └──< movie_languages >── languages
```

Nguyên tắc thiết kế:
- Tránh trùng lặp dữ liệu (3NF).
- Phim lẻ và phim bộ dùng chung schema, phân biệt qua `medium_type`.
- Mọi đường dẫn media lưu dạng URL tương đối hoặc CDN URL.
- Phụ đề gắn vào từng tập (episode), không gắn vào phim (movie).

---

## 2. Chi tiết các Bảng (Tables)

### 2.1 Bảng `movies` — Thông tin chung

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `movie_id` | INT | PRIMARY KEY, AUTO_INCREMENT | ID duy nhất của phim |
| `title` | VARCHAR(255) | NOT NULL | Tên phim (ngôn ngữ hiển thị chính) |
| `original_title` | VARCHAR(255) | | Tên gốc (tiếng bản địa, ví dụ: 기생충) |
| `slug` | VARCHAR(300) | UNIQUE, NOT NULL | URL-friendly slug (ví dụ: ky-sinh-trung-2019) |
| `short_description` | VARCHAR(500) | | Mô tả ngắn cho card preview |
| `description` | TEXT | | Nội dung / cốt truyện đầy đủ |
| `release_year` | INT | | Năm phát hành |
| `release_date` | DATE | | Ngày phát hành chính thức |
| `end_year` | INT | | Năm kết thúc (dành cho series đã hoàn thành) |
| `imdb_rating` | DECIMAL(3,1) | | Điểm IMDB (0.0 – 10.0) |
| `imdb_id` | VARCHAR(20) | UNIQUE | ID trên IMDB (ví dụ: tt1375666) |
| `site_rating` | DECIMAL(3,1) | | Điểm do người dùng website vote |
| `site_votes` | INT | DEFAULT 0 | Số lượt vote của người dùng |
| `poster_path` | VARCHAR(500) | | Ảnh poster dọc (2:3) cho trang chi tiết |
| `thumbnail_path` | VARCHAR(500) | | Ảnh thumbnail ngang (16:9) cho card |
| `backdrop_path` | VARCHAR(500) | | Ảnh nền rộng cho banner/hero section |
| `film_format` | ENUM | | Xem danh sách §4.5 |
| `medium_type` | ENUM | NOT NULL | Xem danh sách §4.6 |
| `status` | ENUM | NOT NULL | Xem danh sách §4.7 |
| `content_rating` | ENUM | | Xem danh sách §4.8 (G, PG, PG-13, R, NC-17...) |
| `original_language` | VARCHAR(10) | | Ngôn ngữ gốc (ISO 639-1: vi, en, ko, ja...) |
| `total_episodes` | INT | | Tổng số tập (NULL nếu chưa kết thúc) |
| `total_seasons` | INT | DEFAULT 1 | Tổng số mùa |
| `is_featured` | TINYINT(1) | DEFAULT 0 | Đánh dấu phim nổi bật (banner trang chủ) |
| `is_hidden` | TINYINT(1) | DEFAULT 0 | Ẩn khỏi danh sách công khai |
| `view_count` | BIGINT | DEFAULT 0 | Tổng lượt xem |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Ngày thêm vào hệ thống |
| `updated_at` | TIMESTAMP | ON UPDATE NOW() | Lần cập nhật cuối |

---

### 2.2 Bảng `episodes` — Tập phim & Media

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `episode_id` | INT | PRIMARY KEY, AUTO_INCREMENT | ID duy nhất của tập |
| `movie_id` | INT | FOREIGN KEY → movies | Liên kết phim |
| `season_number` | INT | DEFAULT 1 | Số mùa (Season 1, 2, 3...) |
| `episode_number` | INT | NOT NULL | Số tập trong mùa (phim lẻ = 1) |
| `episode_name` | VARCHAR(255) | | Tên tập (ví dụ: Tập 1: Khởi nguồn) |
| `description` | TEXT | | Mô tả nội dung tập |
| `m3u8_path` | VARCHAR(500) | | URL stream HLS (ưu tiên dùng) |
| `m3u8_path_480p` | VARCHAR(500) | | HLS stream chất lượng 480p |
| `m3u8_path_720p` | VARCHAR(500) | | HLS stream chất lượng 720p |
| `m3u8_path_1080p` | VARCHAR(500) | | HLS stream chất lượng 1080p |
| `m3u8_path_4k` | VARCHAR(500) | | HLS stream chất lượng 4K |
| `movie_file_path` | VARCHAR(500) | | Link file gốc (MP4/MKV) để download |
| `thumbnail_path` | VARCHAR(500) | | Ảnh thumbnail của tập |
| `duration` | INT | | Thời lượng (tính bằng phút) |
| `air_date` | DATE | | Ngày phát sóng tập này |
| `view_count` | BIGINT | DEFAULT 0 | Lượt xem riêng của tập |
| `is_free` | TINYINT(1) | DEFAULT 1 | Miễn phí hay yêu cầu Premium |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Ngày thêm tập |

> **Logic phim lẻ vs phim bộ:**
> - Phim lẻ → 1 dòng trong `episodes`, `season_number = 1`, `episode_number = 1`.
> - Phim bộ → nhiều dòng, `season_number` tăng theo mùa, `episode_number` tăng theo tập.

---

### 2.3 Bảng `trailers`

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `trailer_id` | INT | PRIMARY KEY, AUTO_INCREMENT | |
| `movie_id` | INT | FOREIGN KEY → movies | |
| `trailer_path` | VARCHAR(500) | NOT NULL | URL YouTube hoặc server nội bộ |
| `label` | ENUM | | `Teaser`, `Trailer`, `Trailer 2`, `Trailer 3`, `Official Trailer`, `Final Trailer`, `Clip`, `Behind the Scenes`, `Opening`, `Ending` |
| `language` | VARCHAR(10) | | Ngôn ngữ trailer (vi, en...) |
| `sort_order` | INT | DEFAULT 0 | Thứ tự hiển thị |

---

### 2.4 Bảng `subtitles` — Phụ đề đa ngôn ngữ

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `sub_id` | INT | PRIMARY KEY, AUTO_INCREMENT | |
| `episode_id` | INT | FOREIGN KEY → episodes | Gắn vào từng tập |
| `language_code` | VARCHAR(10) | NOT NULL | ISO 639-1 (vi, en, ko, zh, ja...) |
| `language_label` | VARCHAR(50) | | Nhãn hiển thị (Vietsub, Engsub, Korsub...) |
| `sub_path` | VARCHAR(500) | NOT NULL | Đường dẫn file phụ đề |
| `format` | ENUM | | `vtt`, `srt`, `ass`, `ssa` |
| `is_default` | TINYINT(1) | DEFAULT 0 | Phụ đề mặc định khi load player |

---

### 2.5 Bảng `genres` & `movie_genres` — Thể loại

**Bảng `genres`:**

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `genre_id` | INT | PRIMARY KEY | |
| `genre_name` | VARCHAR(100) | UNIQUE, NOT NULL | Tên thể loại |
| `slug` | VARCHAR(120) | UNIQUE | URL slug |
| `description` | TEXT | | Mô tả thể loại |

**Bảng `movie_genres`** (quan hệ nhiều-nhiều):

| Cột | Kiểu dữ liệu | Ràng buộc |
| :--- | :--- | :--- |
| `movie_id` | INT | FOREIGN KEY → movies |
| `genre_id` | INT | FOREIGN KEY → genres |

---

### 2.6 Bảng `people` & `movie_cast_crew` — Diễn viên & Đạo diễn

**Bảng `people`:**

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `person_id` | INT | PRIMARY KEY | |
| `full_name` | VARCHAR(255) | NOT NULL | Tên đầy đủ |
| `original_name` | VARCHAR(255) | | Tên gốc (bản địa) |
| `slug` | VARCHAR(300) | UNIQUE | URL slug |
| `avatar_path` | VARCHAR(500) | | Ảnh đại diện |
| `bio` | TEXT | | Tiểu sử |
| `birth_date` | DATE | | Ngày sinh |
| `nationality` | VARCHAR(100) | | Quốc tịch |
| `gender` | ENUM | | `Male`, `Female`, `Non-binary`, `Unknown` |

**Bảng `movie_cast_crew`:**

| Cột | Kiểu dữ liệu | Ràng buộc | Mô tả |
| :--- | :--- | :--- | :--- |
| `movie_id` | INT | FOREIGN KEY → movies | |
| `person_id` | INT | FOREIGN KEY → people | |
| `role` | ENUM | NOT NULL | Xem §4.9 |
| `character_name` | VARCHAR(255) | | Tên nhân vật (nếu là diễn viên) |
| `sort_order` | INT | DEFAULT 0 | Thứ tự hiển thị trong credit |

---

### 2.7 Bảng `countries` & `movie_countries` — Quốc gia sản xuất

**Bảng `countries`:**

| Cột | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `country_code` | CHAR(2) | PRIMARY KEY — ISO 3166-1 alpha-2 (US, KR, JP...) |
| `country_name` | VARCHAR(100) | Tên quốc gia hiển thị |

**Bảng `movie_countries`** (quan hệ nhiều-nhiều):

| Cột | Kiểu dữ liệu | Ràng buộc |
| :--- | :--- | :--- |
| `movie_id` | INT | FOREIGN KEY → movies |
| `country_code` | CHAR(2) | FOREIGN KEY → countries |

---

### 2.8 Bảng `tags` & `movie_tags` — Tag / Từ khóa

**Bảng `tags`:** `tag_id`, `tag_name`, `slug`

**Bảng `movie_tags`:** `movie_id`, `tag_id`

> Tags khác Genre: dùng cho SEO và gợi ý nội dung liên quan. Ví dụ: `#thời-gian-du-hành`, `#siêu-anh-hùng-dc`, `#based-on-manga`.

---

### 2.9 Bảng `studios` & `movie_studios` — Hãng sản xuất

**Bảng `studios`:** `studio_id`, `studio_name`, `logo_path`, `country_code`, `website`

**Bảng `movie_studios`:** `movie_id`, `studio_id`, `role` (ENUM: `Production`, `Distribution`, `Co-Production`)

---

## 3. Các Danh sách Giá trị (ENUM Lists)

### 3.1 Thể loại phim — `genres`

| Nhóm | Thể loại |
| :--- | :--- |
| **Hành động** | Action, Martial Arts, War, Western |
| **Phiêu lưu** | Adventure, Fantasy, Sci-Fi |
| **Hài** | Comedy, Romantic Comedy (RomCom), Satire, Dark Comedy |
| **Tình cảm** | Romance, Drama, Melodrama |
| **Kinh dị** | Horror, Psychological Horror, Supernatural Horror, Slasher |
| **Huyền bí** | Mystery, Thriller, Suspense, Crime, Noir |
| **Tài liệu** | Documentary, Docuseries, Mockumentary, Biographical |
| **Hoạt hình** | Animation, Anime, Stop Motion, CGI |
| **Gia đình** | Family, Kids, Coming of Age |
| **Đặc biệt** | Historical, Political, Legal, Medical, Sports, Music, Dance, Food |
| **Siêu anh hùng** | Superhero, Comic Book Adaptation |
| **Khác** | Disaster, Survival, Zombie, Vampire, Wuxia, Isekai, Mecha |

---

### 3.2 Medium Type — `medium_type`

| Giá trị | Mô tả |
| :--- | :--- |
| `Movie` | Phim lẻ chiếu rạp (điện ảnh), thường ≥ 60 phút |
| `Series` | Phim bộ truyền hình, nhiều tập |
| `Mini Series` | Phim bộ giới hạn số tập (thường 4–10 tập) |
| `Anime` | Hoạt hình Nhật Bản phong cách Anime |
| `Anime Movie` | Phim điện ảnh Anime |
| `Animated Series` | Phim bộ hoạt hình (không phải Anime) |
| `Documentary` | Phim tài liệu độc lập (≥ 40 phút) |
| `Docuseries` | Phim tài liệu nhiều tập |
| `TV Movie` | Phim sản xuất cho truyền hình / streaming |
| `Short Film` | Phim ngắn (< 40 phút) |
| `Web Series` | Series sản xuất cho nền tảng web / YouTube |
| `OVA` | Original Video Animation — Anime phát hành thẳng DVD/BD |
| `ONA` | Original Net Animation — Anime phát hành thẳng online |
| `Special` | Tập đặc biệt, Holiday Special |
| `Live Action` | Phim người thật đóng (chuyển thể từ manga/anime) |
| `Stand-up Comedy` | Chương trình hài độc thoại |
| `Concert / Performance` | Ghi hình buổi biểu diễn trực tiếp |

---

### 3.3 Status — `status`

| Giá trị | Mô tả |
| :--- | :--- |
| `Coming Soon` | Chưa phát hành, đã có thông tin |
| `Now Showing` | Đang chiếu tại rạp |
| `Ongoing` | Phim bộ đang phát sóng (chưa kết thúc) |
| `Completed` | Đã hoàn thành toàn bộ tập / đã ra rạp xong |
| `Hiatus` | Tạm dừng phát sóng, chưa có lịch tiếp theo |
| `Cancelled` | Bị hủy bỏ, không tiếp tục sản xuất |
| `Announced` | Mới được công bố, chưa có trailer hay ngày phát hành |

---

### 3.4 Film Format — `film_format`

| Giá trị | Mô tả |
| :--- | :--- |
| `2D` | Định dạng tiêu chuẩn |
| `3D` | Ba chiều |
| `IMAX` | IMAX tiêu chuẩn |
| `IMAX 3D` | IMAX kết hợp 3D |
| `IMAX 2D` | IMAX không 3D |
| `4DX` | Ghế chuyển động + hiệu ứng môi trường |
| `4DX 3D` | 4DX kết hợp 3D |
| `ScreenX` | Màn hình bao quanh 270° |
| `Dolby Cinema` | Âm thanh Dolby Atmos + hình ảnh Dolby Vision |
| `Dolby Atmos` | Chỉ âm thanh Dolby Atmos |
| `HDR` | High Dynamic Range |
| `4K UHD` | Độ phân giải 4K |
| `4K HDR` | 4K kết hợp HDR |
| `8K` | Độ phân giải 8K |
| `HFR` | High Frame Rate (48fps / 60fps) |
| `D-BOX` | Ghế rung theo phim |

---

### 3.5 Content Rating — `content_rating`

| Hệ thống | Giá trị | Mô tả |
| :--- | :--- | :--- |
| **Quốc tế / Mỹ (MPAA)** | `G` | Mọi lứa tuổi |
| | `PG` | Cần hướng dẫn của phụ huynh |
| | `PG-13` | Không phù hợp dưới 13 tuổi |
| | `R` | Dưới 17 tuổi cần người lớn đi kèm |
| | `NC-17` | Chỉ dành cho người trên 17 tuổi |
| **Việt Nam** | `P` | Phổ biến mọi đối tượng |
| | `C13` | Không phổ biến cho người dưới 13 tuổi |
| | `C16` | Không phổ biến cho người dưới 16 tuổi |
| | `C18` | Không phổ biến cho người dưới 18 tuổi |
| | `K` | Chỉ trẻ em xem cùng người giám hộ |
| **Hàn Quốc** | `All` | Mọi lứa tuổi |
| | `12+` | Từ 12 tuổi trở lên |
| | `15+` | Từ 15 tuổi trở lên |
| | `18+` | Từ 18 tuổi trở lên |
| | `R` | Hạn chế (phim người lớn) |

---

### 3.6 Vai trò trong đoàn phim — `movie_cast_crew.role`

| Giá trị | Mô tả |
| :--- | :--- |
| `Director` | Đạo diễn |
| `Cast` | Diễn viên |
| `Screenwriter` | Biên kịch |
| `Producer` | Nhà sản xuất |
| `Executive Producer` | Nhà sản xuất điều hành |
| `Cinematographer` | Quay phim (Director of Photography) |
| `Composer` | Nhạc sĩ soạn nhạc nền |
| `Editor` | Dựng phim |
| `Production Designer` | Thiết kế sản xuất |
| `Costume Designer` | Thiết kế trang phục |
| `Visual Effects Supervisor` | Giám sát hiệu ứng hình ảnh |
| `Stunt Coordinator` | Điều phối diễn viên đóng thế |
| `Voice Actor` | Lồng tiếng (dành cho Anime / hoạt hình) |

---

### 3.7 Ngôn ngữ phụ đề phổ biến — `subtitles.language_code`

| Code | Nhãn hiển thị |
| :--- | :--- |
| `vi` | Vietsub |
| `en` | Engsub |
| `ko` | Korsub |
| `zh-hans` | Chinese Simplified (Phồn thể giản) |
| `zh-hant` | Chinese Traditional (Phồn thể phức) |
| `ja` | Japanese |
| `th` | Thai |
| `id` | Indonesian |
| `fr` | French |
| `es` | Spanish |
| `pt` | Portuguese |
| `de` | German |
| `ar` | Arabic |
| `hi` | Hindi |
| `ru` | Russian |

---

### 3.8 Quốc gia sản xuất phổ biến — `countries`

| Code | Quốc gia |
| :--- | :--- |
| `US` | Hoa Kỳ |
| `KR` | Hàn Quốc |
| `JP` | Nhật Bản |
| `CN` | Trung Quốc |
| `VN` | Việt Nam |
| `TH` | Thái Lan |
| `IN` | Ấn Độ |
| `GB` | Anh |
| `FR` | Pháp |
| `DE` | Đức |
| `IT` | Ý |
| `ES` | Tây Ban Nha |
| `AU` | Úc |
| `CA` | Canada |
| `HK` | Hồng Kông |
| `TW` | Đài Loan |
| `ID` | Indonesia |
| `MX` | Mexico |
| `BR` | Brazil |
| `RU` | Nga |

---

### 3.9 Đường dẫn media — Quy ước đặt tên

| Trường | Định dạng gợi ý | Ví dụ |
| :--- | :--- | :--- |
| `poster_path` | `/images/posters/{movie_id}.webp` | `/images/posters/123.webp` |
| `thumbnail_path` | `/images/thumbs/{movie_id}.webp` | `/images/thumbs/123.webp` |
| `backdrop_path` | `/images/backdrops/{movie_id}.webp` | `/images/backdrops/123.webp` |
| `m3u8_path` | `https://cdn.example.com/hls/{movie_id}/ep{ep}/master.m3u8` | `.../hls/123/ep1/master.m3u8` |
| `m3u8_path_480p` | `https://cdn.example.com/hls/{movie_id}/ep{ep}/480p.m3u8` | |
| `m3u8_path_720p` | `https://cdn.example.com/hls/{movie_id}/ep{ep}/720p.m3u8` | |
| `m3u8_path_1080p` | `https://cdn.example.com/hls/{movie_id}/ep{ep}/1080p.m3u8` | |
| `m3u8_path_4k` | `https://cdn.example.com/hls/{movie_id}/ep{ep}/4k.m3u8` | |
| `movie_file_path` | `/storage/movies/{movie_id}/ep{ep}_1080p.mp4` | `/storage/movies/123/ep1_1080p.mp4` |
| `sub_path` (.vtt) | `/subs/{episode_id}/{lang}.vtt` | `/subs/456/vi.vtt` |
| `sub_path` (.srt) | `/subs/{episode_id}/{lang}.srt` | `/subs/456/en.srt` |
| `trailer_path` (YouTube) | `https://youtu.be/{video_id}` | `https://youtu.be/AbCdEf12345` |
| `trailer_path` (server) | `/media/trailers/{movie_id}/trailer1.mp4` | |
| `avatar_path` (people) | `/images/people/{person_id}.webp` | `/images/people/789.webp` |
| `logo_path` (studio) | `/images/studios/{studio_id}.webp` | `/images/studios/1.webp` |

---

## 4. Cách thức vận hành (Logic)

### 4.1 Phim lẻ (Movie)
1. Thêm 1 dòng vào `movies` với `medium_type = 'Movie'`, `total_seasons = 1`, `total_episodes = 1`.
2. Thêm **đúng 1 dòng** vào `episodes` với `season_number = 1`, `episode_number = 1`.
3. Frontend: Ẩn danh sách chọn tập, tự động lấy media từ episode duy nhất.

### 4.2 Phim bộ nhiều mùa (Series)
1. Thêm 1 dòng vào `movies` với `medium_type = 'Series'`.
2. Thêm nhiều dòng vào `episodes`, tăng `season_number` theo mùa và `episode_number` theo tập.
3. Frontend: Hiển thị dropdown chọn mùa → danh sách tập tương ứng.

### 4.3 Anime
1. `medium_type = 'Anime'` hoặc `'Anime Movie'`.
2. Gắn genre `Anime` + các thể loại phụ (`Action`, `Fantasy`, `Romance`...).
3. Bảng `subtitles`: thêm phụ đề tiếng Nhật (`ja`) là mặc định nếu là bản gốc.

### 4.4 OVA / Special
1. `medium_type = 'OVA'` hoặc `'Special'`.
2. Liên kết với series chính qua một trường `parent_movie_id` (nên thêm vào bảng `movies`).

---

## 5. Ví dụ SQL

### 5.1 Lấy thông tin đầy đủ một phim

```sql
SELECT 
    m.title,
    m.original_title,
    m.release_year,
    m.imdb_rating,
    m.medium_type,
    m.status,
    m.film_format,
    m.content_rating,
    e.season_number,
    e.episode_number,
    e.episode_name,
    e.m3u8_path,
    e.duration,
    s.language_label AS subtitle_lang,
    s.sub_path
FROM movies m
JOIN episodes e ON m.movie_id = e.movie_id
LEFT JOIN subtitles s ON e.episode_id = s.episode_id
WHERE m.movie_id = 123
ORDER BY e.season_number, e.episode_number;
```

### 5.2 Lấy danh sách thể loại và diễn viên của phim

```sql
SELECT 
    m.title,
    GROUP_CONCAT(DISTINCT g.genre_name ORDER BY g.genre_name SEPARATOR ', ') AS genres,
    GROUP_CONCAT(DISTINCT CASE WHEN mc.role = 'Director' THEN p.full_name END SEPARATOR ', ') AS directors,
    GROUP_CONCAT(DISTINCT CASE WHEN mc.role = 'Cast' THEN p.full_name END ORDER BY mc.sort_order SEPARATOR ', ') AS cast_members
FROM movies m
LEFT JOIN movie_genres mg ON m.movie_id = mg.movie_id
LEFT JOIN genres g ON mg.genre_id = g.genre_id
LEFT JOIN movie_cast_crew mc ON m.movie_id = mc.movie_id
LEFT JOIN people p ON mc.person_id = p.person_id
WHERE m.movie_id = 123
GROUP BY m.movie_id;
```

### 5.3 Tìm kiếm phim theo thể loại + quốc gia + năm

```sql
SELECT m.movie_id, m.title, m.release_year, m.imdb_rating, m.poster_path
FROM movies m
JOIN movie_genres mg ON m.movie_id = mg.movie_id
JOIN genres g ON mg.genre_id = g.genre_id
JOIN movie_countries mc ON m.movie_id = mc.movie_id
WHERE g.slug = 'action'
  AND mc.country_code = 'KR'
  AND m.release_year BETWEEN 2020 AND 2024
  AND m.status != 'Coming Soon'
  AND m.is_hidden = 0
ORDER BY m.imdb_rating DESC
LIMIT 20;
```

---

## 6. Ghi chú & Khuyến nghị

| Vấn đề | Khuyến nghị |
| :--- | :--- |
| **Ảnh poster** | Lưu cả 3 dạng: `poster_path` (2:3), `thumbnail_path` (16:9), `backdrop_path` (21:9). Dùng định dạng WebP để tiết kiệm băng thông |
| **HLS stream** | Tách thành 4 chất lượng riêng (480p → 4K). Master playlist nên dùng adaptive bitrate |
| **Phụ đề** | Ưu tiên định dạng `.vtt` cho HLS. `.srt` dùng cho download |
| **Slug** | Tạo slug từ title + năm để tránh trùng lặp (ví dụ: `tinh-yeu-2024`) |
| **Parent ID** | Thêm `parent_movie_id` vào bảng `movies` cho OVA/Special liên kết về series chính |
| **Full-text Search** | Đánh index FULLTEXT trên `title`, `original_title`, `description` để hỗ trợ tìm kiếm |
| **CDN URL** | Lưu CDN URL thay vì đường dẫn tuyệt đối để dễ migrate storage |
| **Soft delete** | Dùng `is_hidden = 1` thay vì xóa thật để giữ lịch sử dữ liệu |