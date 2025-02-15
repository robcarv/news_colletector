from transformers import pipeline
import json

# Load the summarization pipeline
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Function to summarize text
def summarize_text(text, max_length=130, min_length=30):
    try:
        # Adjust max_length if the input is too short
        input_length = len(text.split())
        if input_length < max_length:
            max_length = min(input_length, 50)  # Set a smaller max_length for short texts
            min_length = min(input_length // 2, 10)  # Adjust min_length proportionally

        summary = summarizer(text, max_length=max_length, min_length=min_length, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing text: {e}")
        return text  # Return the original text if summarization fails

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

    print("Summarization complete. Summarized news saved to 'data/summarized_news.json'.")

if __name__ == "__main__":
    main()