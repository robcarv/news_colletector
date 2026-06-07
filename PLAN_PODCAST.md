# 🎙️ News Collector → Audio Podcast Automático

## Visão Geral

Transformar o **News Collector** existente (que já coleta RSS, gera áudio PT/EN e envia pro Telegram) em um **podcast automático de notícias** — com feed RSS de áudio, página web hospedada localmente, e possibilidade de monetização.

---

## Cenário Atual

```
Feeds RSS (17 fontes) 
    → News Collector (coleta + resume)
    → edge-tts (PT) / Piper (EN)
    → Telegram (audio + texto)
```

## Cenário Desejado

```
Feeds RSS (17+ fontes)
    → News Collector (coleta + resume) 
    → edge-tts / Piper (áudio PT/EN)
    → Telegram (como já faz)
    → RSS Feed de Áudio ← NOVO
    → Página Web Estática ← NOVO
    → YouTube / Spotify (opcional) ← NOVO
```

---

## Etapa 1 — Repositório Local de Áudios

Criar uma estrutura de arquivos organizada no TrueNAS (192.168.68.124):

```
/mnt/nvme1/PodcastNews/
├── episodes/
│   ├── 2026-06-07-edicao-manha.mp3
│   ├── 2026-06-07-edicao-tarde.mp3
│   └── 2026-06-08-edicao-manha.mp3
├── feed.xml          ← RSS de áudio (atualizado automaticamente)
└── index.html        ← Player web (atualizado automaticamente)
```

**O que fazer:** Modificar o `main.py` do News Collector para:
1. Salvar o áudio gerado em `PodcastNews/episodes/` com nome padronizado
2. Manter um arquivo `episodes.json` com metadados (título, data, duração, resumo)
3. Regenerar o `feed.xml` a cada execução

---

## Etapa 2 — RSS Feed de Áudio (Podcast)

O RSS de podcast é um formato padrão que **qualquer app de podcast** entende (Apple Podcasts, Spotify, Google Podcasts, AntennaPod, etc).

### Estrutura do feed.xml

```xml
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>Notícias do Dia — PT/EN</title>
    <description>Resumo das principais notícias em português e inglês</description>
    <link>http://192.168.68.124:8080/podcast/</link>
    <language>pt</language>
    <itunes:author>Seu Nome</itunes:author>
    
    <item>
      <title>Edição 07/06/2026 — Manhã</title>
      <enclosure url="http://192.168.68.124:8080/podcast/episodes/2026-06-07-edicao-manha.mp3" 
                 type="audio/mpeg" length="5242880"/>
      <pubDate>Sun, 07 Jun 2026 08:00:00 +0100</pubDate>
      <description>Resumo das notícias desta manhã...</description>
      <itunes:duration>300</itunes:duration>
    </item>
  </channel>
</rss>
```

### Servindo localmente

**Opção A — Nginx no TrueNAS** (recomendado, mais robusto):
- TrueNAS Scale já tem Nginx internamente
- Criar um dataset `PodcastNews` com share HTTP
- Servir na porta 8081 ou subdomínio

**Opção B — Servidor Python simples** (mais rápido de configurar):
```bash
# Rodar como serviço no RPi5
cd /mnt/truenas_media/PodcastNews
python3 -m http.server 8081 --bind 0.0.0.0
```

**Opção C — Jellyfin**: Já tem Jellyfin no TrueNAS, pode adicionar o áudio como biblioteca de música.

---

## Etapa 3 — Página Web Player

Uma página HTML simples que funciona como player de podcast:

```html
<!DOCTYPE html>
<html>
<head>
  <title>Podcast Notícias</title>
</head>
<body>
  <h1>📰 Notícias do Dia</h1>
  <div id="episodes">
    <!-- Gerado automaticamente -->
    <div class="episode">
      <h3>Edição 07/06/2026 — Manhã</h3>
      <audio controls src="episodes/2026-06-07-edicao-manha.mp3"></audio>
    </div>
  </div>
</body>
</html>
```

Pode ser servido pelo mesmo HTTP server da etapa 2.

---

## Etapa 4 — Automatização (Cron Job)

Adicionar ao cron existente do News Collector:

```bash
# Cron atual (já existe)
0 8,20 * * * cd /home/robert/Documents/vscode_projects/news_colletector && python3 main.py

# Após main.py executar, o áudio já estará salvo no TrueNAS
# O feed RSS e a página HTML são regenerados automaticamente
```

O `main.py` modificado fará:
1. Coleta as notícias (já faz)
2. Gera áudio (já faz)
3. Envia pro Telegram (já faz)
4. **Salva cópia no TrueNAS/PodcastNews/** (NOVO)
5. **Atualiza feed.xml** (NOVO)
6. **Atualiza index.html** (NOVO)

---

## Etapa 5 — Distribuição (Opcional)

### Onde hospedar o feed RSS para alcançar mais pessoas:

| Serviço | Custo | Descrição |
|---------|-------|-----------|
| **GitHub Pages** | Grátis | Hospedar o feed.xml + player como site estático. Basta subir pra um repo público |
| **Cloudflare Pages** | Grátis | Mesma ideia, melhor CDN global |
| **Netlify** | Grátis | Faz deploy automático via git push |
| **Próprio servidor** | Já tem | Servir do TrueNAS/RPi5 na rede local |

### Monetização:

| Método | Descrição | Viabilidade |
|--------|-----------|-------------|
| **Anchor/Spotify** | Enviar o RSS pro Anchor (grátis), que distribui pra Spotify, Apple, Google | ✅ **Melhor opção** — 100% gratuito, alcance máximo |
| **YouTube** | Automatizar upload do áudio com thumbnail gerada | ⚠️ Dá trabalho, precisa de conta |
| **Apoia.se / Padrim** | Crowdfunding brasileiro | ✅ Se tiver audiência |
| **Buy Me a Coffee** | Doações internacionais | ✅ Fácil de configurar |
| **Anchor Ads** | Anúncios automáticos no Anchor | ⚠️ Precisa de mínimo de ouvintes |
| **Newsletter (Substack)** | Texto + áudio no mesmo lugar | ✅ Bom complemento |

### Fluxo de monetização recomendado:

```
1. RSS feed hospedado no GitHub Pages (grátis)
2. Enviar feed pro Anchor/Spotify (grátis, distribui pra todos players)
3. Adicionar link de doação (Buy Me a Coffee ou Apoia.se)
4. Com audiência: ativar anúncios do Anchor
```

---

## Resumo das Tarefas

### Fazer agora (1-2 horas):

1. Modificar `main.py` para salvar áudio no TrueNAS
2. Criar script que gera `feed.xml` e `index.html`
3. Subir servidor HTTP no TrueNAS (Nginx ou Python)
4. Testar feed no app de podcast (AntennaPod)

### Fazer depois (opcional):

5. Hospedar feed no GitHub Pages
6. Enviar pro Anchor/Spotify
7. Configurar página com player bonito
8. Adicionar doações

---

## Perguntas pra você decidir:

1. **Onde hospedar:** Servir do TrueNAS local (só você ouve) ou GitHub Pages (público)?
2. **Idioma:** Um podcast só PT, ou dois canais (PT + EN)?
3. **Frequência:** 2x/dia como já faz, ou compilar tudo num áudio diário?
4. **Player web:** Quer uma página bonita ou só o feed RSS pra jogar no app de podcast?
5. **Monetização:** Quer começar com doações ou já pensar em anúncios?
