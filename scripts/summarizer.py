from transformers import pipeline
import json
import os

# Load the summarization pipeline
print("Loading the summarization model...")
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
print("Summarization model loaded successfully.")

# Function to summarize text
def summarize_text(text, max_length=130, min_length=30):
    try:
        print(f"Summarizing text: {text[:100]}...")  # Print the first 100 characters of the text
        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        print(f"Summary generated: {summary[0]['summary_text']}")
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing text: {e}")
        return text  # Return the original text if summarization fails

# Function to limit text length based on estimated audio duration
def limit_text_length(text, max_duration_minutes=10, words_per_minute=150):
    max_words = max_duration_minutes * words_per_minute
    words = text.split()
    if len(words) > max_words:
        print(f"Text truncated to {max_words} words (max duration: {max_duration_minutes} minutes).")
        return " ".join(words[:max_words])
    print(f"Text length is within the limit ({len(words)} words).")
    return text

# Main function
def main():
    # Load the collected news
    print("Loading collected news from 'data/news.json'...")
    with open("../data/news.json", "r", encoding="utf-8") as f:
        news = json.load(f)
    print(f"Loaded {len(news)} news items.")

    # Summarize each news item
    summarized_news = []
    for i, item in enumerate(news):
        print(f"\nProcessing news item {i + 1}/{len(news)}:")
        print(f"Title: {item['title']}")
        print(f"Source: {item['source']}")
        print(f"Publication Date: {item['publication_date']}")

        # Summarize the news content
        text_to_summarize = item["summary"] if item["summary"] else item["title"]
        summarized_text = summarize_text(text_to_summarize)

        # Add the summarized news to the list
        summarized_item = {
            "title": item["title"],
            "summary": summarized_text,
            "link": item["link"],
            "source": item["source"],
            "publication_date": item["publication_date"]
        }
        summarized_news.append(summarized_item)

    # Save the summarized news to a new JSON file
    output_file = "../data/summarized_news.json"
    print(f"\nSaving summarized news to '{output_file}'...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(summarized_news, f, ensure_ascii=False, indent=4)
    print(f"Summarized news saved to '{output_file}'.")

if __name__ == "__main__":
    main()