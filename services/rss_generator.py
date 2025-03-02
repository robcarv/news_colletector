import os
import xml.etree.ElementTree as ET
from datetime import datetime

def generate_rss_feed(language, audio_folder, output_folder):
    """
    Gera um feed RSS dinâmico baseado nos arquivos de áudio disponíveis.
    """
    rss_file = os.path.join(output_folder, f'news_{language}.xml')
    
    # Criar estrutura base do RSS
    rss = ET.Element('rss', version='2.0')
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = f'News Summary ({language.upper()})'
    ET.SubElement(channel, 'link').text = 'https://yourwebsite.com/rss'
    ET.SubElement(channel, 'description').text = f'Summarized news in {language.upper()}'
    
    # Buscar arquivos de áudio
    if not os.path.exists(audio_folder):
        print(f"Pasta de áudio não encontrada: {audio_folder}")
        return
    
    audio_files = [f for f in os.listdir(audio_folder) if f.endswith('.mp3')]
    
    for audio_file in audio_files:
        file_path = os.path.join(audio_folder, audio_file)
        file_url = f'https://seusite.com/{language}/{audio_file}'
        title = f'Resumo das Notícias - {audio_file.replace("_compiled.mp3", "").replace("_", " ")}'
        
        item = ET.SubElement(channel, 'item')
        ET.SubElement(item, 'title').text = title
        ET.SubElement(item, 'link').text = file_url
        ET.SubElement(item, 'description').text = 'No Summary'
        ET.SubElement(item, 'enclosure', url=file_url, type='audio/mpeg')
    
    # Salvar RSS
    tree = ET.ElementTree(rss)
    os.makedirs(output_folder, exist_ok=True)
    tree.write(rss_file, encoding='utf-8', xml_declaration=True)
    print(f"RSS gerado: {rss_file}")

# Configuração das pastas
script_dir = os.path.dirname(os.path.abspath(__file__))
data_folder = os.path.join(script_dir, 'rss_feeds')

# Gerar RSS dinâmico para cada idioma
generate_rss_feed('en', os.path.join(data_folder, 'en'), data_folder)
generate_rss_feed('pt', os.path.join(data_folder, 'pt'), data_folder)
