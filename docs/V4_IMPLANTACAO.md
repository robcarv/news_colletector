# NewsBot v4 — Documentação de Implantação

**Branch:** `v4`  
**Data:** 20/06/2026  
**Base:** `main` (54c246b)

---

## ✅ Melhorias implantadas

### 1. Piper TTS Offline (PT-BR + EN)
- **PT-BR:** `pt_BR-faber-medium.onnx` (61MB) — voz masculina, 0.2x real-time
- **EN:** `en_US-amy-medium.onnx` (61MB) — voz feminina, 0.2x real-time
- **Fallback:** Edge-TTS automático se Piper falhar
- **Localização:** `piper/piper` (binário ARM64) + `piper_voices/`

### 2. Normalizador de Números e Datas
- `src/normalizer.py` — converte antes do TTS:
  - `2026` → `dois mil e vinte e seis`
  - `15:30` → `quinze e meia`
  - `2026-06-19` → `dezenove de junho de dois mil e vinte e seis`
  - `R$ 50` → `cinquenta reais`
  - `85%` → `oitenta e cinco por cento`
  - `1.5M` → `um vírgula cinco milhões`

### 3. Podcast Diário
- `src/podcast.py` — gera MP3 concatenado:
  - Intro musical (tom 440Hz, 8s com fade)
  - Saudação com data natural
  - Notícias por feed com pausas
  - Encerramento
  - Outro musical (tom 330Hz, 6s com fade)
- Saída: `data/audio/podcast_YYYY-MM-DD.mp3`

---

## 🧪 Resultados dos Testes

### Normalizador PT-BR
```
✅ Em 2026, 85% de alta → "dois mil e vinte e seis, oitenta e cinco por cento"
✅ Às 15:30             → "quinze e meia"
✅ R$ 50                → "cinquenta reais"
✅ 1.5M                 → "um vírgula cinco milhões"
```

### Normalizador EN
```
✅ 2026    → "two thousand and twenty-six"
✅ 15:30   → "fifteen thirty"
✅ 85%     → "eighty-five percent"
```

### TTS Pipeline
```
✅ PT: Piper faber — 316KB WAV — ~2.5s de áudio
✅ EN: Piper amy — 328KB WAV — ~3s de áudio
✅ Normalização aplicada antes do TTS
✅ Fallback Edge-TTS funcional como backup
```

### Pipeline Principal (main.py)
```
⚠️ NÃO TESTADO com --dry-run real (sem feeds novos no momento)
✅ Código importa todos os novos módulos sem erro
✅ sync_git.sh corrigido (fetch + stash + rebase)
```

---

## ⚠️ Pendências / Riscos

| Item | Status | Ação |
|------|--------|------|
| AzuraCast integração | ❌ Não implementado | Precisa de API key + configurar playlist manualmente |
| Podcast flag no main.py | ❌ Não integrado | O módulo existe mas não é chamado pelo main.py atual |
| Teste com feeds reais | ⚠️ Pendente | Testar no próximo run do crontab (18:00) ou rodar `python main.py --dry-run` |
| Vozes Piper no .gitignore | ⚠️ 61MB cada | Arquivos grandes no repo — considere adicionar ao .gitignore e baixar no setup |

---

## 🔄 Como reverter

Se algo quebrar, voltar para `main`:

```bash
cd /home/robert/Documents/vscode_projects/news_colletector
git checkout main
# O crontab volta a usar a versão estável
```

O backup está em `/tmp/news_colletector_backup_20260620_1644.tar.gz` (81MB).

---

## 📋 Próximos passos sugeridos

1. **Testar com `--dry-run`:** `python main.py --dry-run`
2. **Integrar podcast no main.py:** Adicionar flag `--podcast` e chamar `generate_podcast()`
3. **Configurar AzuraCast:** Obter API key, criar playlist "News Jingles"
4. **Adicionar .gitignore:** Ignorar `piper_voices/*.onnx` (>60MB) e baixar no deploy
5. **Merge para main:** Após testar 1-2 runs do crontab sem erros
