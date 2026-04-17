import subprocess

def convert_to_hls(input_video, output_hls):
    cmd = [
        'ffmpeg', '-i', f'"{input_video}"', '-c:v', 'libx264', '-c:a', 'aac',
        '-hls_time', '10', '-hls_list_size', '0', '-f', 'hls', f'"{output_hls}"'
    ]
    result = subprocess.run(" ".join(cmd), capture_output=True, text=True, shell=True)
  

# Thay đổi tên file video nguồn và file output HLS ở đây
input_video = 'D:/LT/Movie Website/Test HLS/static/Dark - S01E01 - Geheimnisse.mkv'
output_hls = 'D:/LT/Movie Website/Test HLS/static/Dark - S01E01 - Geheimnisse.m3u8'

convert_to_hls(input_video, output_hls)