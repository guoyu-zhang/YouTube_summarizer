import os
import re
import requests
import psycopg2
import psycopg2.extras
from flask import Flask, request, jsonify
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig
import google.generativeai as genai
from googleapiclient.discovery import build
from dotenv import load_dotenv

# --- Setup and Configuration ---
load_dotenv()
app = Flask(__name__, static_folder='static', static_url_path='')

# API and Database Configuration
GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY")
YOUTUBE_API_KEY = os.environ.get("GOOGLE_CLOUD_API_KEY")
DATABASE_URL = os.environ.get("DATABASE_URL")

# Validate that all necessary environment variables are set
if not GEMINI_API_KEY:
    raise ValueError("No GOOGLE_API_KEY found for Gemini")
if not YOUTUBE_API_KEY:
    raise ValueError("No GOOGLE_CLOUD_API_KEY found for YouTube Data API")
if not DATABASE_URL:
    raise ValueError("No DATABASE_URL found for PostgreSQL")

genai.configure(api_key=GEMINI_API_KEY)

# --- Database Functions ---
def get_db_connection():
    """Establishes a connection to the PostgreSQL database."""
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    """Initializes the PostgreSQL database and creates the summaries table if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id SERIAL PRIMARY KEY,
            youtube_url TEXT NOT NULL,
            title TEXT NOT NULL,
            channel_title TEXT NOT NULL,
            thumbnail_url TEXT NOT NULL,
            summary TEXT NOT NULL,
            timestamp TIMESTAMPTZ DEFAULT NOW()
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# --- Helper Functions ---
def extract_video_id_from_url(url):
    """Extracts the YouTube video ID from a URL using regex."""
    regex = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(regex, url)
    return match.group(1) if match else None

def summarize_transcript(transcript):
    """Generates a summary of a video transcript using the Gemini API."""
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

def get_transcript_with_proxy(video_id):
    """Attempts to get transcript using proxy configuration."""
    proxy_username = os.environ.get("PROXY_USERNAME")
    proxy_password = os.environ.get("PROXY_PASSWORD")
    
    if not proxy_username or not proxy_password:
        print("No proxy credentials found, trying direct connection...")
        return YouTubeTranscriptApi.get_transcript(video_id)
    
    try:
        print(f"Attempting to get transcript for video {video_id} using proxy...")
        
        # Create proxy configuration
        proxy_config = WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )
        
        # Debug proxy configuration
        print(f"Proxy config created successfully")
        print(f"Proxy dict: {proxy_config.to_requests_dict()}")
        
        # Get transcript with proxy
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, 
            proxies=proxy_config.to_requests_dict()
        )
        
        print(f"Successfully retrieved transcript with proxy")
        return transcript_list
        
    except Exception as proxy_error:
        print(f"Proxy request failed: {proxy_error}")
        print("Attempting direct connection as fallback...")
        
        # Fallback to direct connection
        try:
            return YouTubeTranscriptApi.get_transcript(video_id)
        except Exception as direct_error:
            print(f"Direct connection also failed: {direct_error}")
            raise direct_error

# --- Flask Routes ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return app.send_static_file('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    """Fetches video metadata from the YouTube Data API."""
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
        return jsonify({
            'title': video_snippet['title'],
            'channel_title': video_snippet['channelTitle'],
            'thumbnail_url': video_snippet['thumbnails']['high']['url']
        })
    except Exception as e:
        print(f"--- YOUTUBE API ERROR --- \n{e}\n-------------------------")
        return jsonify({'error': 'An internal API error occurred.'}), 500

@app.route('/summarize', methods=['POST'])
def summarize_video():
    """Generates a summary from a video's transcript."""
    url = request.get_json().get('url')
    video_id = extract_video_id_from_url(url)
    if not video_id:
        return jsonify({'error': 'Could not extract video ID.'}), 400

    try:
        # Use the improved proxy function
        transcript_list = get_transcript_with_proxy(video_id)
        
        transcript = " ".join([d['text'] for d in transcript_list])
        summary = summarize_transcript(transcript)
        return jsonify({'summary': summary})
        
    except Exception as e:
        print(f"--- TRANSCRIPT API ERROR --- \n{e}\n-------------------------")
        error_message = str(e)
        
        # Provide more specific error messages
        if "blocked" in error_message.lower() or "cloud provider" in error_message.lower():
            return jsonify({'error': "YouTube has blocked this request. Please ensure your proxy is configured correctly."}), 500
        elif "transcript" in error_message.lower():
            return jsonify({'error': "Could not retrieve video transcript. The video may not have one, or it might be private."}), 500
        else:
            return jsonify({'error': f"An error occurred while processing the video: {error_message}"}), 500
    
@app.route('/save_summary', methods=['POST'])
def save_summary():
    """Saves a generated summary to the PostgreSQL database."""
    data = request.get_json()
    if not all(k in data for k in ['url', 'title', 'channel_title', 'thumbnail_url', 'summary']):
        return jsonify({'error': 'Missing data for saving.'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO summaries (youtube_url, title, channel_title, thumbnail_url, summary) VALUES (%s, %s, %s, %s, %s)",
        (data['url'], data['title'], data['channel_title'], data['thumbnail_url'], data['summary'])
    )
    conn.commit()
    cursor.close()
    conn.close()
    return jsonify({'success': True, 'message': 'Summary saved successfully!'})

@app.route('/get_summaries', methods=['GET'])
def get_summaries():
    """Retrieves all saved summaries from the database."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute("SELECT id, youtube_url, title, channel_title, thumbnail_url, summary, timestamp FROM summaries ORDER BY timestamp DESC")
    summaries = [dict(row) for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(summaries)

@app.route('/delete_summary/<int:summary_id>', methods=['DELETE'])
def delete_summary(summary_id):
    """Deletes a summary from the database by its ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM summaries WHERE id = %s", (summary_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': 'Summary deleted.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/test-proxy')
def test_proxy():
    """Test endpoint to verify proxy functionality."""
    proxy_username = os.environ.get("PROXY_USERNAME")
    proxy_password = os.environ.get("PROXY_PASSWORD")

    if not proxy_username or not proxy_password:
        return jsonify({"error": "Proxy credentials not configured"})

    try:
        proxy_config = WebshareProxyConfig(
            proxy_username=proxy_username,
            proxy_password=proxy_password,
        )

        session = requests.Session()
        session.headers.update({'Connection': 'close'})
        proxies = proxy_config.to_requests_dict()

        # Test the proxy by getting IP
        ip_response = session.get("https://api.ipify.org", proxies=proxies, timeout=10)
        proxy_ip = ip_response.text
        
        # Test if we can access YouTube through the proxy
        youtube_test = session.get("https://www.youtube.com", proxies=proxies, timeout=10)
        
        return jsonify({
            "proxy_ip": proxy_ip,
            "youtube_accessible": youtube_test.status_code == 200,
            "status": "success"
        })
        
    except Exception as e:
        return jsonify({"error": str(e), "status": "failed"})
    
@app.route('/init_db')
def init_db_route():
    init_db()
    return "Database initialized!"


# --- Main ---
if __name__ == '__main__':
    app.run(debug=True)