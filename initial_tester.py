# initial_tester.py
import os
import logging
from utils.text_processing import remove_html_tags, preprocess_text, generate_valid_filename
from services.tts_service import generate_audio
from services.telegram_service import send_to_telegram
from services.anchor_uploader import upload_to_anchor

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InitialTester:
    def __init__(self):
        # Caminho da pasta de dados (relativo ao local do script)
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.input_folder = os.path.join(self.script_dir, '../data')
        self.audio_folder = os.path.join(self.input_folder, 'audio')
        os.makedirs(self.audio_folder, exist_ok=True)

    def test_text_processing(self):
        """Testa as funções de processamento de texto."""
        logger.info("🔧 Testando funções de processamento de texto...")
        try:
            # Testa remove_html_tags
            html_text = "<p>Este é um <b>teste</b> de tags HTML.</p>"
            clean_text = remove_html_tags(html_text)
            assert clean_text == "Este é um teste de tags HTML.", "Erro em remove_html_tags"

            # Testa preprocess_text
            raw_text = "Este é um teste. Com pontuações, espaços  extras e URLs como google.com."
            processed_text = preprocess_text(raw_text)
            expected_text = "Este é um teste Com pontuações espaços extras e URLs como google ponto com"
            assert processed_text == expected_text, f"Erro em preprocess_text. Esperado: '{expected_text}', Obtido: '{processed_text}'"

            # Testa generate_valid_filename
            title = "Título com caracteres especiais: *<>/\|?*"
            valid_filename = generate_valid_filename(title)
            assert "especiais" in valid_filename and " " not in valid_filename, "Erro em generate_valid_filename"

            logger.info("✅ Funções de processamento de texto testadas com sucesso.")
        except AssertionError as e:
            logger.error(f"❌ Falha no teste de processamento de texto: {e}")

    def test_tts_service(self):
        """Testa a geração de áudio."""
        logger.info("🔊 Testando geração de áudio...")
        try:
            test_text = "Este é um teste de geração de áudio."
            output_audio = os.path.join(self.audio_folder, 'test_audio.mp3')
            generate_audio(test_text, output_audio, speaker="Sofia Hellen", language="pt")
            assert os.path.exists(output_audio), "Arquivo de áudio não foi gerado."
            logger.info("✅ Geração de áudio testada com sucesso.")
        except Exception as e:
            logger.error(f"❌ Falha no teste de geração de áudio: {e}")

    def test_telegram_service(self):
        """Testa o envio de mensagens para o Telegram."""
        logger.info("📤 Testando envio para o Telegram...")
        try:
            send_to_telegram(
                title="Teste de Título",
                summary="Este é um teste de envio para o Telegram.",
                source="Fonte de Teste",
                source_link="#",
                audio_path=os.path.join(self.audio_folder, 'test_audio.mp3')
            )
            logger.info("✅ Envio para o Telegram testado com sucesso.")
        except Exception as e:
            logger.error(f"❌ Falha no teste de envio para o Telegram: {e}")

    def test_anchor_uploader(self):
        """Testa o upload de áudio para o Anchor."""
        logger.info("📤 Testando upload para o Anchor...")
        try:
            upload_to_anchor(
                audio_path=os.path.join(self.audio_folder, 'test_audio.mp3'),
                feed_name="Feed de Teste"
            )
            logger.info("✅ Upload para o Anchor testado com sucesso.")
        except Exception as e:
            logger.error(f"❌ Falha no teste de upload para o Anchor: {e}")

    def run_tests(self):
        """Executa todos os testes."""
        logger.info("🚀 Iniciando testes iniciais...")
        self.test_text_processing()
        self.test_tts_service()
        self.test_telegram_service()
        self.test_anchor_uploader()
        logger.info("🎉 Testes iniciais concluídos.")

if __name__ == "__main__":
    tester = InitialTester()
    tester.run_tests()