import feedparser
import json
from datetime import datetime, timedelta

# List of RSS feeds to collect news from
RSS_FEEDS = [
    "http://feeds.bbci.co.uk/news/rss.xml",  # BBC News
    "https://feeds.folha.uol.com.br/tec/rss091.xml",  # The New York Times
    "https://feeds.folha.uol.com.br/emcimadahora/rss091.xml",  # Folha de S.Paulo
]

# Function to collect news from an RSS feed
def collect_news(feed_url, max_news=20):
    feed = feedparser.parse(feed_url)
    news_items = []
    for entry in feed.entries[:max_news]:  # Limit the number of news items
        # Check if the news was published today
        if is_today(entry.published_parsed):
            news_items.append({
                "title": entry.title,
                "summary": entry.summary if "summary" in entry else "",
                "link": entry.link,
                "source": feed.feed.title,
                "publication_date": entry.published if "published" in entry else ""
            })
    return news_items

# Function to check if the publication date is today
def is_today(published_parsed):
    if not published_parsed:
        return False
    published_date = datetime(*published_parsed[:6])
    today = datetime.now()
    return published_date.date() == today.date()

# Main function
def main():
    all_news = []
    for feed_url in RSS_FEEDS:
        print(f"Collecting news from: {feed_url}")
        news = collect_news(feed_url, max_news=20)  # Collect a maximum of 20 news items per feed
        all_news.extend(news)

    # Save the collected news to a JSON file
    with open("../data/news.json", "w", encoding="utf-8") as f:
        json.dump(all_news, f, ensure_ascii=False, indent=4)

    print(f"Total news collected: {len(all_news)}")
    print("News saved to 'data/news.json'")

if __name__ == "__main__":
    main()