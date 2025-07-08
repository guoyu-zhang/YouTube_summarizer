from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from youtube_transcript_api.proxies import WebshareProxyConfig

proxy_config = WebshareProxyConfig(
    proxy_username="kzhang333",
    proxy_password="lzhang333"
)

try:
    api = YouTubeTranscriptApi(proxy_config=proxy_config)
    transcript = api.get_transcript("ShYKkPPhOoc")  # Use video ID
    print("Transcript snippet:", transcript[:2])
except Exception as e:
    print("Error fetching transcript:", e)
