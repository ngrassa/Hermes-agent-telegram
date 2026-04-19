from youtube_transcript_api import YouTubeTranscriptApi
import yt_dlp, os

CHANNEL_URL = "https://www.youtube.com/@ngrassa"
OUTPUT_DIR  = os.path.expanduser("~/Telegram/docs/youtube")
os.makedirs(OUTPUT_DIR, exist_ok=True)

ydl_opts = {'quiet': True, 'extract_flat': True, 'playlist_items': '1-30'}
with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info   = ydl.extract_info(CHANNEL_URL, download=False)
    videos = info.get('entries', [])

print(f"{len(videos)} vidéos trouvées\n")

api = YouTubeTranscriptApi()

for video in videos:
    video_id = video.get('id')
    title    = video.get('title', video_id)
    print(f"→ {title}")
    try:
        transcript = api.fetch(video_id, languages=['fr','en','ar'])
        text = " ".join([t.text for t in transcript])
        fname = f"{OUTPUT_DIR}/{video_id}.md"
        with open(fname, 'w', encoding='utf-8') as f:
            f.write(f"# {title}\n\n")
            f.write(f"URL : https://youtube.com/watch?v={video_id}\n\n")
            f.write(text)
        print(f"  ✅ {len(text)} caractères")
    except Exception as e:
        print(f"  ⚠️  {e}")

print("\nTerminé !")
