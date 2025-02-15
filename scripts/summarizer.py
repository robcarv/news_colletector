from transformers import pipeline
import json
import os

# Load the summarization model
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Function to summarize text
def summarize_text(text, max_length=200, min_length=50):
    try:
        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing text: {e}")
        return text

# Main function
def main():
    # Load the collected news
    with open("../data/news.json", "r", encoding="utf-8") as f:
        news = json.load(f)

    # Summarize each news item
    summarized_news = []
    for item in news:
        summarized_item = {
            "title": item["title"],
            "summary": summarize_text(item["summary"] if item["summary"] else item["title"]),
            "link": item["link"],
            "source": item["source"],
            "publication_date": item["publication_date"]
        }
        summarized_news.append(summarized_item)

    # Save the summarized news to a new JSON file
    with open("../data/summarized_news.json", "w", encoding="utf-8") as f:
        json.dump(summarized_news, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    main()