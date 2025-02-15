from gtts import gTTS
import json
import os

# Function to convert text to audio
def text_to_audio(text, output_file):
    try:
        tts = gTTS(text=text, lang='pt')  # Use 'pt' para português
        tts.save(output_file)
        print(f"Audio saved to {output_file}")
    except Exception as e:
        print(f"Error converting text to audio: {e}")

# Function to limit text length based on estimated audio duration
def limit_text_length(text, max_duration_minutes=10, words_per_minute=150):
    max_words = max_duration_minutes * words_per_minute
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return text

# Main function
def main():
    # Load the summarized news
    with open("../data/summarized_news.json", "r", encoding="utf-8") as f:
        summarized_news = json.load(f)

    # Create an audio folder if it doesn't exist
    audio_folder = "../data/audio"
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder)

    # Combine all summaries into a single text
    combined_text = "Today's news summary:\n\n"
    for i, item in enumerate(summarized_news):
        combined_text += f"{i + 1}. {item['summary']}\n\n"

    # Limit the text to 10 minutes of audio
    combined_text = limit_text_length(combined_text, max_duration_minutes=10)

    # Print the number of words for debugging
    word_count = len(combined_text.split())
    print(f"Number of words in the combined text: {word_count}")

    # Convert the combined text to a single audio file (MP3)
    output_file = os.path.join(audio_folder, "daily_news_summary.mp3")
    text_to_audio(combined_text, output_file)

    print(f"Text-to-audio conversion complete. Audio saved to {output_file}")

if __name__ == "__main__":
    main()