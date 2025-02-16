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
        return "pt"  # Default para português

# Função para converter texto em áudio usando Coqui TTS
def text_to_audio(text, output_file, language="en"):
    try:
        if not text or text.strip() == "":
            print("⚠️ Aviso: O texto está vazio. Pulando a geração de áudio.")
            return

        if language == "pt":
            model_path = "/home/robert/.local/share/tts/tts_models--pt--cv--vits/"
            if not os.path.exists(model_path):
                raise FileNotFoundError(f"Modelo TTS não encontrado em {model_path}")
            tts = TTS(model_path=model_path, progress_bar=False, gpu=False)
        else:
            tts = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False, gpu=False)

        tts.tts_to_file(text=text, file_path=output_file)
        print(f"Áudio salvo em {output_file}")
    except Exception as e:
        print(f"Erro ao converter texto em áudio: {e}")

# Função para adicionar transições entre notícias
def add_transitions(summarized_news, language="en"):
    combined_text = ""
    if language == "pt":
        combined_text += "Resumo das notícias de hoje:\n\n"
    else:
        combined_text += "Today's news summary:\n\n"

    for i, item in enumerate(summarized_news):
        if "summarized_text" in item and item["summarized_text"].strip() != "":
            combined_text += f"{i + 1}. {item['summarized_text']}\n\n"
            if i < len(summarized_news) - 1:
                if language == "pt":
                    combined_text += "Próxima notícia:\n\n"
                else:
                    combined_text += "Next news:\n\n"
        else:
            print(f"⚠️ Aviso: O campo 'summarized_text' está vazio ou ausente no item {i + 1}.")

    return combined_text

# Função principal
def main():
    data_folder = "../data"
    audio_folder = os.path.join(data_folder, "audio")
    if not os.path.exists(audio_folder):
        os.makedirs(audio_folder)

    # Listar todos os arquivos JSON na pasta de dados
    for filename in os.listdir(data_folder):
        if filename.endswith("_news.json"):
            # Detectar o idioma do feed
            language = detect_language(filename)

            # Carregar as notícias resumidas
            with open(os.path.join(data_folder, filename), "r", encoding="utf-8") as f:
                summarized_news = json.load(f)

            # Adicionar transições entre as notícias
            combined_text = add_transitions(summarized_news, language=language)

            # Converter o texto combinado em um único arquivo de áudio (WAV)
            output_file = os.path.join(audio_folder, f"{filename.replace('_news.json', '_daily_news_summary.wav')}")
            text_to_audio(combined_text, output_file, language=language)

            print(f"Conversão de texto para áudio concluída. Áudio salvo em {output_file}")

if __name__ == "__main__":
    main()