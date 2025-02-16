from TTS.api import TTS
import json
import os

# Função para detectar o idioma do feed com base no nome do arquivo
def detect_language(filename):
    if "folha" in filename.lower():
        return "pt"  # Português
    elif "bbci" in filename.lower():
        return "en"  # Inglês
    else:
        return "en"  # Default para inglês

# Função para converter texto em áudio usando Coqui TTS
def text_to_audio(text, output_file, language="en"):
    try:
        # Carregar o modelo TTS com base no idioma
        if language == "pt":
            tts = TTS(model_name="tts_models/pt/21st_century/vits", progress_bar=False, gpu=False)
        else:
            tts = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False, gpu=False)

        # Gerar o áudio e salvar no arquivo de saída
        tts.tts_to_file(text=text, file_path=output_file)
        print(f"Áudio salvo em {output_file}")
    except Exception as e:
        print(f"Erro ao converter texto em áudio: {e}")

# Função para limitar o tamanho do texto com base na duração estimada do áudio
def limit_text_length(text, max_duration_minutes=10, words_per_minute=150):
    max_words = max_duration_minutes * words_per_minute
    words = text.split()
    if len(words) > max_words:
        return " ".join(words[:max_words])
    return text

# Função para adicionar transições entre notícias
def add_transitions(summarized_news, language="en"):
    combined_text = ""
    if language == "pt":
        combined_text += "Resumo das notícias de hoje:\n\n"
    else:
        combined_text += "Today's news summary:\n\n"

    for i, item in enumerate(summarized_news):
        combined_text += f"{i + 1}. {item['summary']}\n\n"
        if i < len(summarized_news) - 1:
            if language == "pt":
                combined_text += "Próxima notícia:\n\n"
            else:
                combined_text += "Next news:\n\n"

    return combined_text

# Função principal
def main():
    data_folder = "../data"
    audio_folder = os.path.join(data_folder, "audio")
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder)

    # Listar todos os arquivos JSON resumidos na pasta de dados
    for filename in os.listdir(data_folder):
        if filename.endswith("_summarized_news.json"):
            # Detectar o idioma do feed
            language = detect_language(filename)

            # Carregar as notícias resumidas
            with open(os.path.join(data_folder, filename), "r", encoding="utf-8") as f:
                summarized_news = json.load(f)

            # Adicionar transições entre as notícias
            combined_text = add_transitions(summarized_news, language=language)

            # Limitar o texto a 10 minutos de áudio
            combined_text = limit_text_length(combined_text, max_duration_minutes=10)

            # Converter o texto combinado em um único arquivo de áudio (WAV)
            output_file = os.path.join(audio_folder, f"{filename.replace('_summarized_news.json', '_daily_news_summary.wav')}")
            text_to_audio(combined_text, output_file, language=language)

            print(f"Conversão de texto para áudio concluída. Áudio salvo em {output_file}")

if __name__ == "__main__":
    main()