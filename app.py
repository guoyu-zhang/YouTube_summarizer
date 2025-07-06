import sqlite3
import os
import re
from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai
from googleapiclient.discovery import build
from dotenv import load_dotenv

# (All existing setup code remains the same)
load_dotenv()
def init_db():
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            youtube_url TEXT NOT NULL,
            title TEXT NOT NULL,
            channel_title TEXT NOT NULL, 
            thumbnail_url TEXT NOT NULL,
            summary TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

app = Flask(__name__, static_folder='static', static_url_path='')
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("GOOGLE_CLOUD_API_KEY")
if not GEMINI_API_KEY: raise ValueError("No GOOGLE_API_KEY found for Gemini")
if not YOUTUBE_API_KEY: raise ValueError("No GOOGLE_CLOUD_API_KEY found for YouTube Data API")
genai.configure(api_key=GEMINI_API_KEY)

# (All existing helper functions and API endpoints remain the same)
def extract_video_id_from_url(url):
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    return match.group(1) if match else None

def summarize_transcript(transcript):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are a helpful assistant that summarizes YouTube videos for users.
        Summarize the following YouTube video transcript in a clear and structured way.
        Transcript:
        \"\"\"
        {transcript}
        \"\"\"
        Please include the following in your summary:
        1. **Key Points or Sections**: List the main topics or arguments made in the video, broken down into detailed bullet points. Please expand these points to get the full idea across to lay users. For hard to understand concepts, it is best to expand on it further in a clear way.
        2. **Conclusion or Takeaway**: Summarize the main message or action the video encourages.
        Make the language natural and viewer-friendly. Avoid repetition and filler.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"An error occurred during summarization: {e}"

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    url = request.get_json().get('url')
    video_id = extract_video_id_from_url(url)
    if not video_id:
        return jsonify({'error': 'Invalid YouTube URL.'}), 400
    try:
        youtube_service = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        request_video_info = youtube_service.videos().list(part="snippet", id=video_id)
        response = request_video_info.execute()
        if not response.get('items'):
            return jsonify({'error': 'Video not found.'}), 404
        video_snippet = response['items'][0]['snippet']
        title = video_snippet['title']
        channel_title = video_snippet['channelTitle']
        thumbnail_url = video_snippet['thumbnails']['high']['url']
        return jsonify({
            'title': title,
            'channel_title': channel_title,
            'thumbnail_url': thumbnail_url
        })
    except Exception as e:
        print(f"--- YOUTUBE API ERROR --- \n{e}\n-------------------------")
        return jsonify({'error': 'An internal API error occurred.'}), 500

@app.route('/summarize', methods=['POST'])
def summarize_video():
    url = request.get_json().get('url')
    video_id = extract_video_id_from_url(url)
    if not video_id: return jsonify({'error': 'Could not extract video ID.'}), 400
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join([d['text'] for d in transcript_list])
        summary = summarize_transcript(transcript)
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': f"Could not retrieve transcript. Error: {e}"}), 500

@app.route('/save_summary', methods=['POST'])
def save_summary():
    data = request.get_json()
    if not all(k in data for k in ['url', 'title', 'channel_title', 'thumbnail_url', 'summary']):
        return jsonify({'error': 'Missing data for saving.'}), 400
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO summaries (youtube_url, title, channel_title, thumbnail_url, summary) VALUES (?, ?, ?, ?, ?)",
        (data['url'], data['title'], data['channel_title'], data['thumbnail_url'], data['summary'])
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Summary saved successfully!'})

@app.route('/get_summaries', methods=['GET'])
def get_summaries():
    conn = sqlite3.connect('summaries.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, youtube_url, title, channel_title, thumbnail_url, summary, timestamp FROM summaries ORDER BY timestamp DESC"
    )
    summaries = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(summaries)

# --- NEW ENDPOINT FOR DELETING ---
@app.route('/delete_summary/<int:summary_id>', methods=['DELETE'])
def delete_summary(summary_id):
    """Deletes a summary from the database by its ID."""
    try:
        conn = sqlite3.connect('summaries.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM summaries WHERE id = ?", (summary_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Summary deleted.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# --- Main Execution ---
if __name__ == '__main__':
    init_db()
    app.run(debug=True)