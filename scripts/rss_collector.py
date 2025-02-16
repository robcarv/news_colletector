import feedparser
import json
from datetime import datetime, timedelta
import os

# List of RSS feeds to collect news from
RSS_FEEDS = [
    "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",
]

# Function to collect news from an RSS feed
def collect_news(feed_url, max_news=5):
    feed = feedparser.parse(feed_url)
    news_items = []
    print(f"\n🔍 Processing feed: {feed_url}")
    print(f"📰 Total entries found: {len(feed.entries)}")

    for entry in feed.entries:
        if is_today(entry.published_parsed):
            news_items.append({
                "title": entry.title,
                "summary": entry.summary if "summary" in entry else "",
                "link": entry.link,
                "source": feed.feed.title,
                "publication_date": entry.published if "published" in entry else ""
            })
            print(f"✅ Added news item: {entry.title}")

            if len(news_items) >= max_news:
                print(f"🚫 Reached the limit of {max_news} news items for this feed.")
                break

    print(f"📥 Total news items collected from {feed_url}: {len(news_items)}")
    return news_items

# Function to check if the publication date is today
def is_today(published_parsed):
    if not published_parsed:
        print("⚠️ Warning: No publication date found for an entry.")
        return False
    published_date = datetime(*published_parsed[:6])
    today = datetime.now()
    return published_date.date() == today.date()

# Main function
def main():
    # Create a data folder if it doesn't exist
    data_folder = "../data"
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)
        print(f"📁 Created data folder: {data_folder}")

    for feed_url in RSS_FEEDS:
        print(f"\n🌐 Collecting news from: {feed_url}")
        news = collect_news(feed_url, max_news=10)

        # Save the collected news to a JSON file named after the feed source
        feed_name = feed_url.split("//")[1].split("/")[0].replace(".", "_")
        output_file = os.path.join(data_folder, f"{feed_name}_news.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=4)

        print(f"💾 News from {feed_url} saved to {output_file}")
        print(f"📄 Total news items saved for this feed: {len(news)}")

if __name__ == "__main__":
    main()