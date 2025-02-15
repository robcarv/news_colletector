import pyttsx3
import json
import os

# Initialize the TTS engine
engine = pyttsx3.init()

# List available voices
voices = engine.getProperty('voices')
for voice in voices:
    print(f"Voice: {voice.name} | ID: {voice.id}")

# Set a specific voice (optional)
engine.setProperty('voice', voices[0].id)  # Use the first voice in the list

# Adjust speech rate (optional)
engine.setProperty('rate', 150)  # Default is 200

# Adjust volume (optional)
engine.setProperty('volume', 1.0)  # Range: 0.0 to 1.0

# Function to convert text to audio
def text_to_audio(text, output_file):
    try:
        engine.save_to_file(text, output_file)
        engine.runAndWait()
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

    # Convert the combined text to a single audio file (MP3)
    output_file = os.path.join(audio_folder, "daily_news_summary.mp3")
    text_to_audio(combined_text, output_file)

    print(f"Text-to-audio conversion complete. Audio saved to {output_file}")

if __name__ == "__main__":
    main()