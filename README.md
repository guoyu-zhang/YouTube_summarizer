# YouTube Video Summarizer

This is a simple web app that takes a YouTube video URL, retrieves the transcript and generates a summary using the Gemini API.

Summaries can be saved to and managed from a PostgreSQL database.

Built with:

- Python
- Google Gemini API
- YouTube Data API
- PostgreSQL
- Simple HTML, CSS & JavaScript frontend

---

## Features

- Extracts video transcripts (with proxy support)
- Uses Gemini to generate summaries
- Save summaries to a database and view them anytime

---

## Installation

1. **Clone the repo**

```bash
git clone https://github.com/guoyu-zhang/YouTube_summarizer.git
cd YouTube_summarizer
```

2. **Create venv and install requirements**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. **Set environement variables**

Create a .env in the root with the following.

```bash
GOOGLE_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_API_KEY=your_youtube_data_api_key
DATABASE_URL=postgresql://username:password@host:port/dbname

# Optional - adding these will allow for proxies and deployment on cloud services, as YouTube blocks cloud IPs.
PROXY_USERNAME=your_proxy_username
PROXY_PASSWORD=your_proxy_password
```

3. **Running the app**

```bash
python app.py
```

## TODO Features

Add user authentication to allow for multiple users.
