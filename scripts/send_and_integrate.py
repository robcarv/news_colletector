import os
import requests
import logging
from dotenv import load_dotenv  # Importa a função para carregar o .env

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Constantes para o Telegram (carregadas do .env)
BOT_TOKEN = os.getenv('BOT_TOKEN')  # Obtém o token do bot do Telegram
CHAT_ID = os.getenv('CHAT_ID')  # Obtém o ID do chat do Telegram

# Função para enviar áudios para o Telegram
def send_audio_to_telegram(audio_path):
    """
    Envia um arquivo de áudio para um chat do Telegram usando a API do Bot.
    
    :param audio_path: Caminho do arquivo de áudio
    :return: Resposta da API do Telegram
    """
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendAudio"
    try:
        with open(audio_path, 'rb') as audio_file:
            files = {'audio': audio_file}
            data = {'chat_id': CHAT_ID}
            response = requests.post(url, files=files, data=data)
            response.raise_for_status()  # Levanta exceção em caso de erro HTTP
            logger.info(f"✅ Áudio {os.path.basename(audio_path)} enviado com sucesso para o Telegram.")
            return response.json()
    except Exception as e:
        logger.error(f"❌ Erro ao enviar áudio {os.path.basename(audio_path)} para o Telegram: {e}")
        return None

# Função para integrar com uma plataforma de podcast (exemplo básico)
def integrate_with_podcast_platform(audio_folder, podcast_rss_feed):
    """
    Integra os áudios gerados com uma plataforma de podcast.
    Aqui você pode adicionar a lógica para upload dos áudios e atualização do feed RSS.
    
    :param audio_folder: Pasta contendo os arquivos de áudio
    :param podcast_rss_feed: URL do feed RSS do podcast (se necessário)
    """
    logger.info("🔧 Integrando áudios com a plataforma de podcast...")
    # Exemplo básico: você pode adicionar a lógica de upload aqui
    for audio_file in os.listdir(audio_folder):
        if audio_file.endswith('.mp3'):
            audio_path = os.path.join(audio_folder, audio_file)
            logger.info(f"📤 Preparando para enviar {audio_file} para a plataforma de podcast...")
            # Adicione a lógica de upload aqui (depende da plataforma escolhida)
    logger.info("✅ Integração com a plataforma de podcast concluída.")

# Função principal
def main():
    """
    Função principal que envia os áudios para o Telegram e integra com a plataforma de podcast.
    """
    # Configurações
    audio_folder = '../data/audio/'  # Pasta onde os áudios estão armazenados
    podcast_rss_feed = 'URL_DO_SEU_FEED_RSS'  # Substitua pelo URL do feed RSS do podcast (se necessário)

    # Verifica se as variáveis de ambiente foram carregadas corretamente
    if not BOT_TOKEN or not CHAT_ID:
        logger.error("❌ Erro: BOT_TOKEN ou CHAT_ID não foram configurados no arquivo .env.")
        return

    # Envia os áudios para o Telegram
    for audio_file in os.listdir(audio_folder):
        if audio_file.endswith('.mp3'):
            audio_path = os.path.join(audio_folder, audio_file)
            send_audio_to_telegram(audio_path)

    # Integra com a plataforma de podcast (opcional)
    integrate_with_podcast_platform(audio_folder, podcast_rss_feed)

if __name__ == "__main__":
    main()