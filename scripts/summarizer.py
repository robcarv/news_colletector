from transformers import pipeline
import json
import os

# Load a smaller summarization model for better performance
summarizer = pipeline("summarization", model="t5-small")

# Function to summarize text
def summarize_text(text, max_length_ratio=0.5, min_input_length=20):
    # Skip summarization if the input text is too short
    if len(text.split()) < min_input_length:
        print("Input text is too short. Skipping summarization.")
        return text

    # Calculate max_length based on input text length
    input_length = len(text.split())
    max_length = max(8, int(input_length * max_length_ratio))  # Ensure a minimum length of 8

    try:
        summary = summarizer(text, max_length=max_length, min_length=5, do_sample=False)
        return summary[0]['summary_text']
    except Exception as e:
        print(f"Error summarizing text: {e}")
        return text

# Main function
def main():
    data_folder = "../data"
    # List all JSON files in the data folder
    for filename in os.listdir(data_folder):
        if filename.endswith("_news.json"):
            print(f"\nProcessing file: {filename}")
            # Load the collected news
            with open(os.path.join(data_folder, filename), "r", encoding="utf-8") as f:
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
            summarized_filename = filename.replace("_news.json", "_summarized_news.json")
            with open(os.path.join(data_folder, summarized_filename), "w", encoding="utf-8") as f:
                json.dump(summarized_news, f, ensure_ascii=False, indent=4)

            print(f"Summarized news saved to {summarized_filename}")

if __name__ == "__main__":
    main()