from TTS.api import TTS


tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True, gpu=False)

# Exibir os locutores disponíveis
# print(tts.is_multi_speaker)
# print(tts.speakers)
# # Certifique-se de usar o mesmo modelo que foi baixado
# tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=True, gpu=False)

# # Teste com um texto simples
# tts.tts_to_file(text="Teste de áudio com TTS.", speaker="br_speaker1", language="pt", file_path="teste_audio.wav")

# Carregar o modelo
# tts = TTS(model_name="tts_models--multilingual--vits", progress_bar=False)

# Verificar se o modelo tem um gerenciador de locutores
if hasattr(tts.synthesizer.tts_model, "speaker_manager"):
    speaker_manager = tts.synthesizer.tts_model.speaker_manager
    if speaker_manager:
        print("Locutores disponíveis:", speaker_manager.speakers)
    else:
        print("Este modelo não possui múltiplos locutores.")
else:
    print("Este modelo não possui um gerenciador de locutores.")


    # tts --model_name "tts_models/<language>/<dataset>/<model_name>"  --list_speaker_idxs 
