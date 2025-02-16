import feedparser
import json
from datetime import datetime, timedelta
import os

# List of RSS feeds to collect news from
RSS_FEEDS = [
    "https://feeds.folha.uol.com.br/tec/rss091.xml",  # Feed em português
    "http://feeds.bbci.co.uk/news/rss.xml",  # Feed em inglês
]

# Function to collect news from an RSS feed
def collect_news(feed_url, max_news=5):
    feed = feedparser.parse(feed_url)
    news_items = []
    print(f"\n🔍 Processing feed: {feed_url}")
    print(f"📰 Total entries found: {len(feed.entries)}")

    for entry in feed.entries:  # No limit here, we will limit the total later
        # Check if the news was published today
        if is_today(entry.published_parsed):
            news_items.append({
                "title": entry.title,
                "summary": entry.summary if "summary" in entry else "",
                "link": entry.link,
                "source": feed.feed.title,
                "publication_date": entry.published if "published" in entry else ""
            })
            print(f"✅ Added news item: {entry.title}")

            # Stop collecting if we have reached the total limit of 10 news items
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

    all_news = []  # List to store all collected news items

    for feed_url in RSS_FEEDS:
        print(f"\n🌐 Collecting news from: {feed_url}")
        news = collect_news(feed_url, max_news=10)  # Collect a maximum of 10 news items per feed

        # Add the collected news to the all_news list
        all_news.extend(news)

        # Save the collected news to a JSON file named after the feed source
        feed_name = feed_url.split("//")[1].split("/")[0].replace(".", "_")
        output_file = os.path.join(data_folder, f"{feed_name}_news.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=4)

        print(f"💾 News from {feed_url} saved to {output_file}")
        print(f"📄 Total news items saved for this feed: {len(news)}")

    # Save all collected news to a single JSON file (optional)
    output_file_all = os.path.join(data_folder, "all_today_news.json")
    with open(output_file_all, "w", encoding="utf-8") as f:
        json.dump(all_news[:10], f, ensure_ascii=False, indent=4)  # Save only the first 10 news items

    print(f"\n💾 All today's news saved to {output_file_all}")
    print(f"📄 Total news items saved across all feeds: {len(all_news[:10])}")

if __name__ == "__main__":
    main()