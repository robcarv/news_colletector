# News Collector

RSS feed collector with TTS (Text-to-Speech) audio generation and Telegram delivery. Optimized for Raspberry Pi.

**Branches:**
- `main` - Current version (v3.2)
- `legacy-v1` - Original version (archived)

## Features

- **17 RSS feeds** covering news and music (BR, IE, UK, US)
- **Per-language TTS**: PT-BR (Edge-TTS AntonioNeural), EN (Piper Amy - offline)
- **Consolidated summaries**: 1 audio (headlines) + 1 message (full summary with links) per feed
- **History cache**: Prevents duplicate delivery of the same article
- **Cron-based scheduling**: Configurable intervals for each feed
- **Telegram delivery**: Auto-posts to configured channels

## Infrastructure

Runs on Pi501 (192.168.68.117). Managed via systemd timer.

## Related

- [dashy-homelab](https://github.com/robcarv/dashy-homelab) - Dashboard with all services
- [azura-cast-customizations](https://github.com/robcarv/azura-cast-customizations) - AzuraCast theme for Dublin Calling
