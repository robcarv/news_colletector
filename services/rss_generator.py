# services/rss_generator.py
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from xml.dom import minidom

# Configuração de logs
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_rss_feed(feed_name, episodes, output_folder):
    """
    Gera um arquivo RSS feed para o podcast.
    :param feed_name: Nome do podcast.
    :param episodes: Lista de episódios (cada episódio é um dicionário com título, descrição, link, etc.).
    :param output_folder: Pasta onde o arquivo RSS será salvo.
    :return: Caminho do arquivo RSS gerado.
    """
    try:
        # Cria a estrutura do RSS feed
        rss = ET.Element("rss", version="2.0", xmlns_itunes="http://www.itunes.com/dtds/podcast-1.0.dtd")

        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = feed_name
        ET.SubElement(channel, "description").text = f"Resumo das notícias de {feed_name}."
        ET.SubElement(channel, "link").text = "https://seusite.com/podcast"
        ET.SubElement(channel, "language").text = "pt-br"
        ET.SubElement(channel, "itunes:author").text = "Seu Nome"
        ET.SubElement(channel, "itunes:category", text="News")
        ET.SubElement(channel, "itunes:explicit").text = "no"
        ET.SubElement(channel, "itunes:image", href="https://seusite.com/imagem.jpg")

        # Adiciona os episódios
        for episode in episodes:
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = episode["title"]
            ET.SubElement(item, "description").text = episode["description"]
            ET.SubElement(item, "link").text = episode["link"]
            ET.SubElement(item, "enclosure", url=episode["audio_url"], length=str(episode["file_size"]), type="audio/mpeg")
            ET.SubElement(item, "pubDate").text = episode["pub_date"]
            ET.SubElement(item, "guid").text = episode["link"]
            ET.SubElement(item, "itunes:duration").text = episode["duration"]

        # Converte o XML para uma string formatada
        xml_str = minidom.parseString(ET.tostring(rss)).toprettyxml(indent="  ")

        # Salva o arquivo RSS
        rss_file_path = os.path.join(output_folder, f"{feed_name}_feed.rss")
        with open(rss_file_path, "w", encoding="utf-8") as f:
            f.write(xml_str)

        logger.info(f"✅ Feed RSS gerado e salvo em: {rss_file_path}")
        return rss_file_path
    except Exception as e:
        logger.error(f"❌ Erro ao gerar o feed RSS: {e}")
        return None