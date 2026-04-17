Giai đoạn 1: Thiết lập Hệ sinh thái trên Windows (Tuần 1)
Mục tiêu là cài đặt và đảm bảo tất cả các công cụ nền tảng giao tiếp được với nhau trên môi trường Windows.

Cơ sở dữ liệu: Cài đặt PostgreSQL (bản Windows). Sử dụng công cụ pgAdmin 4 đi kèm để tạo database có tên movie_db.

Trạm xử lý Video: Tải FFmpeg bản biên dịch cho Windows, giải nén vào C:\ffmpeg. Thêm thư mục C:\ffmpeg\bin vào biến môi trường Path của Windows. Mở Command Prompt gõ ffmpeg -version để xác nhận thành công.

Web Server: Tải file caddy.exe và đặt vào thư mục quản lý máy chủ (ví dụ: C:\Caddy\).

Môi trường Python: Tạo thư mục dự án my_movie_web, mở Terminal tại đó, tạo môi trường ảo và cài đặt các thư viện lõi:

DOS
python -m venv venv
venv\Scripts\activate
pip install django psycopg2 waitress
Giai đoạn 2: Xây dựng Lõi Backend Django (Tuần 2)
Thiết lập xương sống cho web để quản lý danh sách phim và đường dẫn HLS.

Khởi tạo Project: Chạy django-admin startproject core . và tạo một app mới python manage.py startapp movies.

Cấu hình CSDL: Trong settings.py, thay thế SQLite mặc định bằng cấu hình PostgreSQL trỏ tới movie_db.

Thiết lập thư mục tĩnh: Cấu hình rõ ràng STATIC_ROOT (chứa CSS/JS) và MEDIA_ROOT (nơi sẽ chứa các file HLS) trong settings.py.

Xây dựng Models: Tạo bảng Movie (thông tin phim) và Episode (tập phim). Bảng Episode sẽ có một trường video_url để lưu đường dẫn tới file .m3u8 (ví dụ: media/hls_streams/phim_a/tap_1/output.m3u8).

Giai đoạn 3: Hệ thống Tự động hóa Byte-Range HLS (Tuần 3)
Thay vì gõ lệnh băm video bằng tay, hãy tận dụng kỹ năng Python để xây dựng một cỗ máy tự động hoàn toàn.

Tạo thư mục video_processor/raw_videos để chứa file MP4 tải về.

Viết một script Python sử dụng thư viện subprocess. Kịch bản hoạt động:

Script quét thư mục raw_videos.

Nếu thấy file .mp4 mới, script gọi lệnh FFmpeg băm thành Byte-Range HLS:
ffmpeg -i input.mp4 -profile:v baseline -level 3.0 -start_number 0 -hls_time 10 -hls_list_size 0 -hls_flags single_file -f hls output.m3u8

Sau khi FFmpeg chạy xong (tạo ra 1 file output.m3u8 và 1 file output.ts lớn), script tự động di chuyển cụm file này vào thư mục media/hls_streams/ của Django.

Script dùng ORM của Django tự động tạo một bản ghi Episode mới trong database, trỏ video_url tới file .m3u8 vừa tạo.

Giai đoạn 4: Tự động hóa Metadata (Crawler) (Tuần 4)
Để kho dữ liệu phong phú mà không tốn công nhập liệu tay:

Tạo thư mục crawlers/ độc lập.

Viết các script Python gọi API từ các nguồn dữ liệu mở (như Consumet, Anify, hoặc Jikan cho anime) để lấy thông tin như tóm tắt phim, ảnh bìa (poster), điểm đánh giá.

Lưu ảnh bìa tải về vào thư mục media/posters/ và chèn thông tin text vào bảng Movie trong PostgreSQL.

Giai đoạn 5: Frontend & Giao diện Phát (Tuần 5)
Xây dựng giao diện xem phim thực tế.

Giao diện cốt lõi: Viết các template HTML/CSS cho Trang chủ (hiển thị poster phim dạng lưới) và Trang chi tiết (hiển thị thông tin và trình phát video).

Tích hợp Trình phát: Trong template xem phim, nhúng thư viện video.js (hoặc hls.js).

Cấu hình thẻ <video> nhận dữ liệu từ trường video_url của Django. Trình duyệt sẽ tự động đọc file .m3u8, sau đó tự hiểu cách lấy các đoạn byte tương ứng từ file .ts lớn để phát phim mượt mà.

Giai đoạn 6: Triển khai Caddy & Mạng LAN (Tuần 6)
Kết nối các thành phần lại với nhau để tạo thành một server hoàn chỉnh trên Windows.

Khởi chạy Backend: Trong môi trường ảo Python, dùng Waitress để chạy Django:
waitress-serve --port=8000 core.wsgi:application

Cấu hình Web Server: Tạo file Caddyfile trong thư mục C:\Caddy\ với nội dung định tuyến:

Plaintext
localhost:80, 192.168.1.x:80 {
    route /static/* {
        file_server { root C:\Đường_dẫn_tới_Project }
    }
    route /media/* {
        file_server { root C:\Đường_dẫn_tới_Project }
    }
    reverse_proxy localhost:8000
}
Chạy Caddy: Mở Command Prompt tại C:\Caddy\, chạy lệnh caddy run.

Phát sóng: Vào Windows Defender Firewall mở port 80 (TCP Inbound). Vào cấu hình Router Wi-Fi thiết lập IP tĩnh cho máy tính của bạn (thay 192.168.1.x trong Caddyfile bằng IP đó).

Hoàn thành 6 giai đoạn này, bạn sẽ sở hữu một hệ thống streaming nội bộ cực kỳ mạnh mẽ, sạch sẽ, hoàn toàn tự động hóa từ khâu xử lý video gốc cho đến việc phát HLS trên trình duyệt.