import pysrt

def srt_to_vtt(input_file, output_file):
    subs = pysrt.open(input_file, encoding='utf-8')

    content = 'WEBVTT\n\n'
    for sub in subs:
        start_time = sub.start.to_time().strftime('%H:%M:%S.%f')[:-3]  # Convert start time to VTT format(%H:%M:%S.%f lần lượt là giờ, phút, giây và micro giây)
        end_time = sub.end.to_time().strftime('%H:%M:%S.%f')[:-3]  # Convert end time to VTT format
        content += f'{start_time} --> {end_time}\n'
        content += sub.text + '\n\n'

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(content)

# Chuyển đổi từ tệp SRT sang VTT
srt_to_vtt('Dark.S01E01.WEBRip.Netflix.vi.srt', 'Dark.S01E01.WEBRip.Netflix.vi.vtt')