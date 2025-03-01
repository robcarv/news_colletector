# services/spotify_audio_uploader.py
import os
import requests
import logging
from dotenv import load_dotenv

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Configurações da API do Spotify
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
TOKEN_URL = "https://accounts.spotify.com/api/token"
UPLOAD_URL = "https://api.spotify.com/v1/me/audiobooks"  # Endpoint para upload de áudios

# Função para obter o token de acesso
def get_access_token():
    try:
        response = requests.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(CLIENT_ID, CLIENT_SECRET)
        )
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            logger.error(f"Erro ao obter token de acesso: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Erro na requisição de token: {e}")
        return None

# Função para fazer upload de um arquivo de áudio
def upload_to_spotify(audio_path, feed_name):
    """
    Envia o áudio compilado para o Spotify.
    :param audio_path: Caminho do arquivo de áudio compilado.
    :param feed_name: Nome do feed.
    """
    token = get_access_token()
    if not token:
        logger.error("Token de acesso não obtido. Verifique as credenciais do Spotify.")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Metadados do áudio
    metadata = {
        "name": f"Resumo das Notícias - {feed_name}",
        "description": f"Resumo das notícias de {feed_name}.",
        "public": True  # Define se o áudio será público ou privado
    }

    try:
        # Primeiro, cria o registro do áudio na API
        response = requests.post(UPLOAD_URL, headers=headers, json=metadata)
        
        if response.status_code == 201:
            audio_id = response.json().get("id")
            logger.info(f"Áudio registrado com sucesso! ID: {audio_id}")

            # Agora, faz o upload do arquivo de áudio
            upload_file_url = f"{UPLOAD_URL}/{audio_id}/tracks"
            with open(audio_path, "rb") as audio_file:
                files = {"file": (os.path.basename(audio_path), audio_file, "audio/mpeg")}
                upload_response = requests.post(upload_file_url, headers=headers, files=files)
                
                if upload_response.status_code == 201:
                    logger.info("Upload do áudio concluído com sucesso!")
                    logger.info(f"Resposta: {upload_response.json()}")
                else:
                    logger.error(f"Erro no upload do áudio: {upload_response.text}")
        else:
            logger.error(f"Erro ao registrar o áudio: {response.text}")
    except Exception as e:
        logger.error(f"Erro durante o upload: {e}")