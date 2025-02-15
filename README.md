# News Collector and Summarizer

This project collects news from RSS feeds, summarizes the content using NLP, and converts the summaries into audio.

## Features

- **RSS Feed Collection**: Fetches news from multiple RSS feeds.
- **Text Summarization**: Uses Hugging Face's `facebook/bart-large-cnn` model to summarize news content.
- **Audio Conversion**: Converts summarized text into audio (future feature).
- **GitHub Integration**: Automatically pushes updates to GitHub.

## Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/seu-usuario/news_colletector.git
Install dependencies:

bash
Copy
pip install -r requirements.txt
Run the RSS collector:

bash
Copy
python scripts/rss_collector.py
Run the summarizer:

bash
Copy
python scripts/summarizer.py