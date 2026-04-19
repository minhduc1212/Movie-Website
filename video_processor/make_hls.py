import os
import sys
import subprocess
import shutil
import django

# ==========================================
# 1. KẾT NỐI SCRIPT VỚI DJANGO
# ==========================================
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from movies.models import Movie, Episode

# ==========================================
# 2. CẤU HÌNH ĐƯỜNG DẪN
# ==========================================
RAW_DIR = os.path.join(os.path.dirname(__file__), 'raw_videos')
MEDIA_HLS_DIR = os.path.join(PROJECT_DIR, 'media', 'hls_streams')

def process_videos():
    print(">>> Bắt đầu quét thư mục raw_videos...")
    
    # Lọc ra các file video (mp4, mkv)
    for filename in os.listdir(RAW_DIR):
        if filename.endswith(('.mp4', '.mkv')):
            video_path = os.path.join(RAW_DIR, filename)
            base_name = os.path.splitext(filename)[0] # Lấy tên phim bỏ đuôi
            
            print(f"\n[+] Đang xử lý: {base_name}")
            
            # Tạo thư mục riêng cho phim này trong media
            movie_out_dir = os.path.join(MEDIA_HLS_DIR, base_name)
            os.makedirs(movie_out_dir, exist_ok=True)
            
            m3u8_path = os.path.join(movie_out_dir, "output.m3u8")
            db_m3u8_path = f"hls_streams/{base_name}/output.m3u8" # Đường dẫn lưu vào DB
            
            # ==========================================
            # 3. BĂM VIDEO BẰNG FFMPEG (Byte-Range)
            # ==========================================
            # Nếu là MKV, ưu tiên copy luồng video để siêu tốc. Nếu mp4 thì convert chuẩn web
            if filename.endswith('.mkv'):
                print("    -> Nhận diện file MKV, tiến hành copy luồng (Fast mode)...")
                # Thêm '-sn' vào đây
                cmd = ['ffmpeg', '-y', '-i', video_path, '-sn', '-c', 'copy', '-hls_time', '10', '-hls_list_size', '0', '-hls_flags', 'single_file', '-f', 'hls', m3u8_path]
            else:
                print("    -> Nhận diện file MP4, tiến hành tối ưu HLS...")
                # Thêm '-sn' vào đây
                cmd = ['ffmpeg', '-y', '-i', video_path, '-sn', '-profile:v', 'baseline', '-level', '3.0', '-start_number', '0', '-hls_time', '10', '-hls_list_size', '0', '-hls_flags', 'single_file', '-f', 'hls', m3u8_path]
            
            # Chạy FFmpeg
            # Mình thêm check=True để nếu FFmpeg lỗi, Python sẽ dừng lại báo đỏ luôn, không in dòng Success giả dối nữa
            subprocess.run(cmd, check=True) 
            print("    -> Đã tạo xong file HLS!")

            # ==========================================
            # 4. TÌM VÀ XỬ LÝ PHỤ ĐỀ (NẾU CÓ)
            # ==========================================
            sub_path_for_db = ""
            for sub_ext in ['.vtt', '.srt']:
                potential_sub = os.path.join(RAW_DIR, base_name + sub_ext)
                if os.path.exists(potential_sub):
                    print(f"    -> Đã tìm thấy phụ đề: {base_name}{sub_ext}")
                                   
                    if sub_ext == '.srt':
                        # Convert srt sang vtt siêu tốc bằng ffmpeg
                        vtt_name = base_name + ".vtt"
                        vtt_out_path = os.path.join(movie_out_dir, vtt_name)
                        subprocess.run(['ffmpeg', '-y', '-i', potential_sub, vtt_out_path])
                        sub_path_for_db = f"hls_streams/{base_name}/{vtt_name}"
                        print("    -> Đã convert và di chuyển phụ đề (.vtt)!")
                    else:
                        # Nếu đã là vtt thì copy thẳng sang
                        shutil.copy(potential_sub, os.path.join(movie_out_dir, base_name + ".vtt"))
                        sub_path_for_db = f"hls_streams/{base_name}/{base_name}.vtt"
                    break # Tìm thấy 1 cái sub là ngừng

            # ==========================================
            # 5. LƯU VÀO DATABASE BẢN MỚI
            # ==========================================
            # Tạo Phim (Nếu chưa có)
            movie_obj, created = Movie.objects.get_or_create(
                title=base_name,
                defaults={'film_format': 'movie', 'status': 'completed'}
            )
            
            # Tạo Tập phim (Gắn vào bộ phim trên)
            Episode.objects.create(
                movie=movie_obj,
                episode_name="Tập Full (HLS)",
                m3u8_path=db_m3u8_path,
                sub_path=sub_path_for_db # Có sub thì lưu, không có thì bỏ trống
            )
            print("    -> ĐÃ LƯU THÀNH CÔNG VÀO DATABASE!")

if __name__ == "__main__":
    process_videos()
    print("\n>>> HOÀN TẤT QUY TRÌNH!")