# Implantacao de Nhentai Downloader Self-Hosted -- Revisao com Ecossistema Sinkaroid

> **Para Hermes:** Usar subagent-driven-development para implementar tarefa por tarefa.

**Goal:** Implantar um downloader self-hosted de nhentai.net com PostgreSQL, UI React, downloads sincronos e assincronos, fallback Cloudflare, armazenamento persistente no TrueNAS, rodando no Raspberry Pi 5.

**Arquitetura Revisada:**
Reaproveitar o **ecossistema sinkaroid** (Jandapress + Tomoe) que ja resolve scraping de nhentai + outras fontes, e construir ao redor: (1) **Jandapress** como API REST para dados (get, search, random), (2) **Tomoe** como engine de download CLI (integrado como worker), (3) **Backend Manager** em Go/Python com fila Redis + PostgreSQL, (4) **Frontend React** para pesquisa e gerenciamento de download. Storage no TrueNAS via SMB.

**Tech Stack:**
- API de dados: **Jandapress** (Bun + Hono + Cheerio, ja resolve scraping nhentai)
- Download engine: **Tomoe** (Python, pip install, integrado como subprocess/worker)
- Backend Manager: Go (Gin) para orquestracao de fila + API REST propria
- Frontend: React + Vite + Tailwind
- DB: PostgreSQL 16 (Docker)
- Fila: Redis 7 (Docker)
- Containerizacao: Docker Compose
- Storage: bind mount SMB do TrueNAS (/mnt/truenas/comics)

---

## O Ecossistema Sinkaroid

Apos analisar os repositorios do sinkaroid, identificamos **2 projetos-chave** que ja resolvem 70% do problema:

### Jandapress (v10.0.4-alpha)
- **URL:** https://github.com/sinkaroid/jandapress
- **License:** MIT
- **Stack:** Bun + Hono + Cheerio + Redis (Keyv)
- **Features:**
  - REST API pronta (get, search, random) para **7 sites**: nhentai, pururin, hentaifox, hentai2read, simply-hentai, asmhentai, 3hentai
  - Saida JSON normalizada (title, tags, artist, images, pages)
  - Cache via Redis com TTL configurável
  - Docker image oficial: `ghcr.io/sinkaroid/jandapress:latest`
  - Suporta nhentai API v2 oficial com `NHENTAI_API_KEY`
  - CORS habilitado, sem autenticacao (uso interno)
  - **Descontinuou servico publico em marco/2026** -- forked e self-hosted e o caminho correto

### Tomoe (v3.7.1)
- **URL:** https://github.com/sinkaroid/tomoe
- **License:** MIT
- **Stack:** Python 3 + janda (biblioteca Jandapress)
- **Features:**
  - CLI downloader: `tomoe --nhentai 177013`
  - Suporta os mesmos 7 sites
  - Bulk download via JSON
  - Auto-render em PDF
  - Pip install: `pip install tomoe`

### Diagrama de integracao

```
[Frontend React] --> [Backend Manager (Go/Gin)] --> [Jandapress API (Bun)]
                          |                                |
                          v                                v
                     [PostgreSQL]                     [Redis Cache]
                     [Redis Queue]                         |
                          |                                |
                          v                                v
                    [Worker: Tomoe (Python)] --> [nhentai.net / CDN]
                          |
                          v
                    [TrueNAS SMB: /mnt/truenas/comics/]
```

---

## Tasks Revisadas

### Task 1: Fork/Configurar Jandapress como servico interno

**Objective:** Deploy do Jandapress como microservico no Docker Compose, configurado para cache Redis e API key nhentai.

**Files:**
- Create: `comics-downloader/jandapress/.env`
- Modify: `comics-downloader/docker-compose.yml`
- Create: `comics-downloader/scripts/test_jandapress.sh`

**Step 1: Adicionar Jandapress ao docker-compose.yml**

```yaml
version: '3.8'

volumes:
  postgres_data:
  redis_data:

networks:
  comics-net:
    driver: bridge

services:
  jandapress:
    image: ghcr.io/sinkaroid/jandapress:latest
    container_name: comics-jandapress
    restart: unless-stopped
    ports:
      - "3001:3000"
    networks:
      - comics-net
    environment:
      - PORT=3000
      - REDIS_URL=redis://comics-redis:6379
      - EXPIRE_CACHE=2
      - NHENTAI_API_KEY=${NHENTAI_API_KEY:-}
      - USER_AGENT=jandapress/10.0.4-alpha (comics-downloader)
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  redis:
    image: redis:7-alpine
    container_name: comics-redis
    restart: unless-stopped
    networks:
      - comics-net
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**Step 2: Script de teste do Jandapress**

```bash
#!/bin/bash
# scripts/test_jandapress.sh
echo "=== Testing Jandapress API ==="

# Test get gallery
echo "1. Get gallery 177013:"
curl -s http://localhost:3001/api/gallery/nhentai/177013 | python3 -m json.tool | head -20

# Test search
echo "2. Search 'fate':"
curl -s "http://localhost:3001/api/search/nhentai?q=fate&limit=3" | python3 -m json.tool | head -20

# Test random
echo "3. Random gallery:"
curl -s http://localhost:3001/api/random/nhentai | python3 -m json.tool | head -10

echo "=== Done ==="
```

**Step 3: Testar**

Run: `curl -s http://localhost:3001/api/gallery/nhentai/177013 | python3 -m json.tool`
Expected: JSON com title, tags, artist, image list, total pages

**Step 4: .env**

```
NHENTAI_API_KEY=
COMICS_STORAGE=/mnt/truenas/comics
POSTGRES_PASSWORD=changeme
```

**Step 5: Commit**

```bash
git add docker-compose.yml scripts/test_jandapress.sh .env.example
git commit -m "feat: Jandapress microservice + Redis for gallery metadata API"
```

---

### Task 2: PostgreSQL schema + modelos Go

**Objective:** Criar schema relacional para galerias, downloads, fila de tarefas, e historico.

**Files:**
- Create: `backend/internal/db/schema.sql`
- Create: `backend/internal/db/db.go`
- Create: `backend/internal/db/models.go`
- Modify: `docker-compose.yml` (adicionar postgres)

**Step 1: Schema SQL**

```sql
-- schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE galleries (
    id              INTEGER PRIMARY KEY,        -- nhentai gallery ID
    title           TEXT NOT NULL,
    title_english   TEXT,
    title_japanese  TEXT,
    artist          TEXT[] DEFAULT '{}',
    tags            TEXT[] DEFAULT '{}',
    parodies        TEXT[] DEFAULT '{}',
    characters      TEXT[] DEFAULT '{}',
    language        TEXT,
    num_pages       INTEGER NOT NULL DEFAULT 0,
    num_favorites   INTEGER DEFAULT 0,
    upload_date     TIMESTAMP,
    cover_url       TEXT,
    source          TEXT NOT NULL DEFAULT 'nhentai',
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|downloading|completed|failed
    metadata_json   JSONB,
    cbz_path        TEXT,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_galleries_status ON galleries(status);
CREATE INDEX idx_galleries_tags ON galleries USING GIN(tags);
CREATE INDEX idx_galleries_title ON galleries USING GIN(to_tsvector('simple', title));

CREATE TABLE download_queue (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    gallery_id      INTEGER NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
    mode            TEXT NOT NULL DEFAULT 'async',  -- sync|async
    priority        INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'queued', -- queued|running|completed|failed
    worker_id       TEXT,
    error_message   TEXT,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_queue_status ON download_queue(status);

CREATE TABLE tags_cache (
    tag_name        TEXT PRIMARY KEY,
    gallery_count   INTEGER DEFAULT 0,
    last_updated    TIMESTAMP DEFAULT NOW()
);
```

**Step 2: Models Go**

```go
// internal/db/models.go
package db

import (
    "time"
    "github.com/google/uuid"
)

type Gallery struct {
    ID            int       `json:"id" db:"id"`
    Title         string    `json:"title" db:"title"`
    TitleEnglish  *string   `json:"title_english,omitempty" db:"title_english"`
    TitleJapanese *string   `json:"title_japanese,omitempty" db:"title_japanese"`
    Artist        []string  `json:"artist" db:"artist"`
    Tags          []string  `json:"tags" db:"tags"`
    Parodies      []string  `json:"parodies" db:"parodies"`
    Characters    []string  `json:"characters" db:"characters"`
    Language      string    `json:"language" db:"language"`
    NumPages      int       `json:"num_pages" db:"num_pages"`
    NumFavorites  int       `json:"num_favorites" db:"num_favorites"`
    UploadDate    time.Time `json:"upload_date" db:"upload_date"`
    CoverURL      string    `json:"cover_url" db:"cover_url"`
    Source        string    `json:"source" db:"source"`
    Status        string    `json:"status" db:"status"`
    CbzPath       *string   `json:"cbz_path,omitempty" db:"cbz_path"`
    CreatedAt     time.Time `json:"created_at" db:"created_at"`
    UpdatedAt     time.Time `json:"updated_at" db:"updated_at"`
}

type DownloadJob struct {
    ID          uuid.UUID  `json:"id" db:"id"`
    GalleryID   int        `json:"gallery_id" db:"gallery_id"`
    Mode        string     `json:"mode" db:"mode"`
    Priority    int        `json:"priority" db:"priority"`
    Status      string     `json:"status" db:"status"`
    WorkerID    *string    `json:"worker_id,omitempty" db:"worker_id"`
    ErrorMsg    *string    `json:"error_message,omitempty" db:"error_message"`
    StartedAt   *time.Time `json:"started_at,omitempty" db:"started_at"`
    CompletedAt *time.Time `json:"completed_at,omitempty" db:"completed_at"`
    CreatedAt   time.Time  `json:"created_at" db:"created_at"`
}
```

**Step 3: Servico Postgres no compose**

```yaml
  postgres:
    image: postgres:16-alpine
    container_name: comics-db
    restart: unless-stopped
    networks:
      - comics-net
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backend/internal/db/schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    environment:
      - POSTGRES_USER=comics
      - POSTGRES_DB=comics
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U comics"]
      interval: 5s
      timeout: 5s
      retries: 5
```

**Step 4: Commit**

```bash
git add backend/internal/db/schema.sql backend/internal/db/models.go
git commit -m "feat: PostgreSQL schema for galleries, queue, and tags"
```

---

### Task 3: Integracao Backend Manager com Jandapress

**Objective:** Criar API Go (Gin) que consulta o Jandapress para metadata e gerencia a fila de downloads.

**Files:**
- Create: `backend/go.mod`
- Create: `backend/cmd/server/main.go`
- Create: `backend/internal/jandapress/client.go`
- Create: `backend/internal/jandapress/types.go`

**Step 1: Cliente Jandapress**

```go
// internal/jandapress/client.go
package jandapress

import (
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type Client struct {
    BaseURL    string  // http://jandapress:3000
    HTTPClient *http.Client
}

func New(baseURL string) *Client {
    return &Client{
        BaseURL: baseURL,
        HTTPClient: &http.Client{Timeout: 30 * time.Second},
    }
}

func (c *Client) GetGallery(source string, id int) (*GalleryResponse, error) {
    url := fmt.Sprintf("%s/api/gallery/%s/%d", c.BaseURL, source, id)
    resp, err := c.HTTPClient.Get(url)
    if err != nil {
        return nil, fmt.Errorf("jandapress get: %w", err)
    }
    defer resp.Body.Close()
    
    var result GalleryResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("jandapress decode: %w", err)
    }
    return &result, nil
}

func (c *Client) Search(source, query string, limit int) (*SearchResponse, error) {
    url := fmt.Sprintf("%s/api/search/%s?q=%s&limit=%d", c.BaseURL, source, query, limit)
    resp, err := c.HTTPClient.Get(url)
    // ...
}

func (c *Client) Random(source string) (*GalleryResponse, error) {
    url := fmt.Sprintf("%s/api/random/%s", c.BaseURL, source)
    // ...
}
```

**Step 2: Router Gin com endpoints**

```go
// cmd/server/main.go
package main

import (
    "github.com/gin-gonic/gin"
    "comics-downloader/internal/jandapress"
    "comics-downloader/internal/db"
)

func main() {
    r := gin.Default()
    janda := jandapress.New("http://jandapress:3000")
    database := db.Connect("postgresql://comics:pass@postgres:5432/comics")

    api := r.Group("/api")
    {
        // Metadata (via Jandapress)
        api.GET("/gallery/:id", func(c *gin.Context) {
            id, _ := strconv.Atoi(c.Param("id"))
            gallery, err := janda.GetGallery("nhentai", id)
            // ...
        })
        api.GET("/search", func(c *gin.Context) {
            q := c.Query("q")
            results, err := janda.Search("nhentai", q, 20)
            // ...
        })

        // Download management
        api.POST("/download/:id", handleCreateDownload(database))
        api.GET("/queue", handleListQueue(database))
        api.GET("/queue/:jobId", handleQueueStatus(database))

        // Stats
        api.GET("/stats", handleStats(database))
    }

    r.GET("/health", healthCheck(database))

    r.Run(":3000")
}
```

**Step 3: Dockerfile do backend**

```dockerfile
# backend/Dockerfile
FROM golang:1.22-alpine AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o server ./cmd/server/main.go

FROM alpine:3.19
RUN apk add --no-cache ca-certificates tzdata
COPY --from=build /app/server /server
EXPOSE 3000
CMD ["/server"]
```

**Step 4: Testar integracao**

Run: `curl -s http://localhost:3000/api/gallery/177013 | python3 -m json.tool`
Expected: JSON com dados da gallery (proxy do Jandapress)

**Step 5: Commit**

```bash
git add backend/go.mod backend/cmd/ backend/internal/jandapress/
git commit -m "feat: Go API server with Jandapress client integration"
```

---

### Task 4: Fila de Download com Redis + Worker Tomoe

**Objective:** Implementar fila de download via Redis (as suggestive) + worker Python que chama Tomoe para baixar.

**Files:**
- Create: `backend/internal/queue/redis.go`
- Create: `backend/worker/Dockerfile`
- Create: `backend/worker/worker.py`

**Step 1: Fila Redis no Go**

```go
// internal/queue/redis.go
package queue

import (
    "context"
    "encoding/json"
    "github.com/redis/go-redis/v9"
)

type Queue struct {
    client *redis.Client
    key    string // "download:queue"
}

type QueueItem struct {
    JobID     string `json:"job_id"`
    GalleryID int    `json:"gallery_id"`
    Source    string `json:"source"` // "nhentai"
    Mode      string `json:"mode"`   // "sync" | "async"
    OutputDir string `json:"output_dir"`
}

func (q *Queue) Enqueue(ctx context.Context, item QueueItem) error {
    data, _ := json.Marshal(item)
    return q.client.LPush(ctx, q.key, data).Err()
}

func (q *Queue) Dequeue(ctx context.Context) (*QueueItem, error) {
    data, err := q.client.RPop(ctx, q.key).Bytes()
    if err != nil {
        return nil, err
    }
    var item QueueItem
    json.Unmarshal(data, &item)
    return &item, nil
}

func (q *Queue) Len(ctx context.Context) int64 {
    return q.client.LLen(ctx, q.key).Val()
}
```

**Step 2: Worker Python com Tomoe**

```python
#!/usr/bin/env python3
# worker/worker.py
"""
Worker that consumes Redis queue and downloads galleries using Tomoe.

Usage:
    python worker.py
"""
import os
import json
import redis
import subprocess
import time
import sys
from pathlib import Path

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/data")
QUEUE_KEY = os.getenv("QUEUE_KEY", "download:queue")

r = redis.Redis.from_url(REDIS_URL)

def download_gallery(gallery_id: int, source: str, output_dir: str) -> dict:
    """Download gallery using tomoe CLI."""
    cmd = ["tomoe", f"--{source}", str(gallery_id)]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,  # 5 min timeout
        cwd=output_dir
    )
    
    return {
        "success": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": result.stdout[-500:],
        "stderr": result.stderr[-500:],
    }

def process_queue():
    print(f"Worker started, watching queue: {QUEUE_KEY}")
    sys.stdout.flush()
    
    while True:
        item_raw = r.rpop(QUEUE_KEY)
        if not item_raw:
            time.sleep(5)
            continue
        
        item = json.loads(item_raw)
        gallery_id = item["gallery_id"]
        source = item.get("source", "nhentai")
        output_dir = item.get("output_dir", OUTPUT_DIR)
        job_id = item.get("job_id", "unknown")
        
        print(f"[{job_id}] Downloading {source}:{gallery_id} -> {output_dir}")
        sys.stdout.flush()
        
        # Update queue status: running
        r.hset(f"job:{job_id}", "status", "running")
        r.hset(f"job:{job_id}", "started_at", time.time())
        
        try:
            result = download_gallery(gallery_id, source, output_dir)
            if result["success"]:
                print(f"[{job_id}] Completed")
                r.hset(f"job:{job_id}", "status", "completed")
            else:
                print(f"[{job_id}] Failed: {result['stderr']}")
                r.hset(f"job:{job_id}", "status", "failed")
                r.hset(f"job:{job_id}", "error", result["stderr"])
        except Exception as e:
            print(f"[{job_id}] Error: {e}")
            r.hset(f"job:{job_id}", "status", "failed")
            r.hset(f"job:{job_id}", "error", str(e))
        
        r.hset(f"job:{job_id}", "completed_at", time.time())
        sys.stdout.flush()

if __name__ == "__main__":
    process_queue()
```

**Step 3: Dockerfile do worker**

```dockerfile
# worker/Dockerfile
FROM python:3.11-slim

RUN pip install tomoe redis

COPY worker.py /worker.py

RUN mkdir -p /data
VOLUME /data

CMD ["python3", "/worker.py"]
```

**Step 4: Adicionar worker ao compose**

```yaml
  worker:
    build: ./worker
    container_name: comics-worker
    restart: unless-stopped
    networks:
      - comics-net
    volumes:
      - ${COMICS_STORAGE:-./data}:/data
    environment:
      - REDIS_URL=redis://comics-redis:6379
      - OUTPUT_DIR=/data
      - QUEUE_KEY=download:queue
    depends_on:
      redis:
        condition: service_healthy
    deploy:
      replicas: 1
```

**Step 5: Testar fila**

Run: `curl -X POST http://localhost:3000/api/download/177013 -d '{"mode":"async"}'`
Expected: `{"job_id": "...", "status": "queued"}`
Verificar: `curl http://localhost:3000/api/queue/{job_id}` -> "running" depois "completed"

**Step 6: Commit**

```bash
git add backend/internal/queue/ worker/
git commit -m "feat: Redis queue with Tomoe Python worker"
```

---

### Task 5: Frontend React

**Objective:** Interface web para pesquisar galerias, ver detalhes, e agendar downloads.

**Files:**
- Create: `frontend/` (Vite + React + Tailwind)
- Create: `frontend/Dockerfile`

**Step 1: Scaffold Vite**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install tailwindcss @tailwindcss/vite react-router-dom
```

**Step 2: Componentes**

```
frontend/src/
  pages/
    Search.tsx     -- Pesquisa via Jandapress
    Queue.tsx      -- Fila de downloads ativos
    Gallery.tsx    -- Detalhes da galeria (tags, preview, download btn)
  components/
    GalleryCard.tsx
    TagBadge.tsx
  api/
    client.ts      -- axios/fetch wrapper para backend Go
```

**Step 3: Fluxo da UI**

```
[Search page]
  Input + Search button -> GET /api/search?q=xxx (via backend -> Jandapress)
  Grid de GalleryCards com cover, title, tags, pages

[Clicar em uma gallery]
  GET /api/gallery/:id -> detalhes completos
  Botao "Download" com opcao Sync/Async
  POST /api/download/:id {mode: "sync|async"}

[Queue page]
  GET /api/queue -> lista jobs com status
  Polling a cada 5s para atualizar
  Auto-redirect quando sync complete -> download do CBZ
```

**Step 4: Dockerfile multi-stage**

```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Step 5: Commit**

```bash
git add frontend/
git commit -m "feat: React UI with search, gallery detail, download queue"
```

---

### Task 6: Cloudflare Fallback para o Jandapress

**Objective:** Quando o Jandapress falhar (CF block), usar bypass alternativo.

**Files:**
- Create: `backend/scripts/cf_bypass.py`
- Create: `backend/internal/jandapress/fallback.go`

**Step 1: Entender o cenario**

O **Jandapress** usa **Cheerio** (HTML scraping leve) e a **nhentai API v2 oficial** (se `NHENTAI_API_KEY` configurada). Se a API oficial estiver disponivel, nao ha Cloudflare porque e API direta. Se usar scraping da pagina HTML (fallback), o Cloudflare pode bloquear.

**Estrategia de fallback em camadas:**

```
1. Tenta Jandapress com NHENTAI_API_KEY (API oficial, sem CF)
2. Se falhar: Jandapress scraping via Cheerio (pode pegar CF)
3. Se CF bloquear: cloudscraper Python bypass
4. Ultimo recurso: Playwright headless
```

**Step 2: Script cloudscraper**

```python
#!/usr/bin/env python3
# scripts/cf_bypass.py
import cloudscraper
import json, sys

scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'linux', 'mobile': False},
    delay=15
)

def fetch_gallery(gallery_id):
    # Tenta API v2 primeiro
    url = f"https://nhentai.net/api/gallery/{gallery_id}"
    resp = scraper.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "gallery":
        print(json.dumps(fetch_gallery(int(sys.argv[2]))))
    elif cmd == "page":
        media_id, page_num, ext = sys.argv[2], int(sys.argv[3]), sys.argv[4]
        url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
        sys.stdout.buffer.write(scraper.get(url, timeout=30).content)
```

**Step 3: Fallback handler Go**

```go
// internal/jandapress/fallback.go
package jandapress

// Tenta Jandapress, fallback cloudscraper
func (c *Client) GetGalleryWithFallback(id int) (*GalleryResponse, error) {
    // Tenta Jandapress primeiro
    gallery, err := c.GetGallery("nhentai", id)
    if err == nil {
        return gallery, nil
    }
    
    // Fallback: cloudscraper Python
    cmd := exec.Command("python3", "scripts/cf_bypass.py", "gallery", fmt.Sprintf("%d", id))
    output, err := cmd.Output()
    if err != nil {
        return nil, fmt.Errorf("all fallbacks failed: %w", err)
    }
    
    // Converte raw API response para GalleryResponse
    var raw NhentaiRawGallery
    json.Unmarshal(output, &raw)
    return convertNhentaiRawToGallery(raw), nil
}
```

**Step 4: Testar fallback**

Run: `python3 scripts/cf_bypass.py gallery 177013 | python3 -m json.tool`
Expected: JSON valido mesmo se Jandapress estiver offline

**Step 5: Commit**

```bash
git add backend/scripts/ backend/internal/jandapress/fallback.go
git commit -m "feat: Cloudflare bypass fallback chain (API -> scraping -> cloudscraper)"
```

---

### Task 7: Storage TrueNAS + CBZ generation

**Objective:** Montar SMB do TrueNAS e gerar CBZ apos download.

**Files:**
- Create: `scripts/mount_truenas.sh`
- Create: `backend/internal/storage/fs.go`

**Step 1: Mount script**

```bash
#!/bin/bash
# scripts/mount_truenas.sh
TRUENAS_IP="${TRUENAS_IP:-192.168.68.124}"
SHARE="${SHARE:-comics}"
MOUNT="${MOUNT:-/mnt/truenas/comics}"
USER="${USER:-robert}"
PASS="${PASS}"

mkdir -p "$MOUNT"
mountpoint -q "$MOUNT" && { echo "Already mounted"; exit 0; }

mount -t cifs "//${TRUENAS_IP}/${SHARE}" "$MOUNT" \
    -o "username=${USER},password=${PASS},uid=1000,gid=1000,iocharset=utf8,noperm"
echo "Mounted at $MOUNT"
```

**Step 2: Storage service Go**

```go
// internal/storage/fs.go
package storage

import (
    "archive/zip"
    "io"
    "os"
    "path/filepath"
)

type FileStorage struct {
    BasePath string
}

// CreateCBZ compresses downloaded pages into a CBZ file
func (s *FileStorage) CreateCBZ(galleryID int) (string, error) {
    srcDir := filepath.Join(s.BasePath, "tomoe-nhentai", fmt.Sprintf("nhentai-%d*", galleryID))
    cbzPath := filepath.Join(s.BasePath, fmt.Sprintf("%d.cbz", galleryID))
    
    zipFile, err := os.Create(cbzPath)
    if err != nil { return "", err }
    defer zipFile.Close()
    
    writer := zip.NewWriter(zipFile)
    defer writer.Close()
    
    // Walk downloaded directory, add images to CBZ
    filepath.Walk(srcDir, func(path string, info os.FileInfo, err error) error {
        if info.IsDir() { return nil }
        f, _ := os.Open(path)
        defer f.Close()
        
        w, _ := writer.Create(info.Name())
        io.Copy(w, f)
        return nil
    })
    
    return cbzPath, nil
}
```

**Step 3: Integrar no worker (pos-download hook)**

```python
# No worker.py, apos download_gallery():
result = download_gallery(gallery_id, source, output_dir)
if result["success"]:
    # Gerar CBZ a partir dos arquivos baixados pelo Tomoe
    cbz_path = create_cbz(output_dir, gallery_id)
    # Atualizar status no Postgres via API
    update_gallery_status(gallery_id, "completed", cbz_path)
```

**Step 4: Commit**

```bash
git add scripts/mount_truenas.sh backend/internal/storage/
git commit -m "feat: TrueNAS SMB mount + CBZ generation from Tomoe output"
```

---

### Task 8: Deploy no Raspberry Pi 5

**Objective:** Script de deploy automatizado para o Pi, com ARM64 overrides.

**Files:**
- Create: `scripts/deploy_pi.sh`
- Create: `docker-compose.pi.yml`

**Step 1: Script deploy**

```bash
#!/bin/bash
# scripts/deploy_pi.sh
PI="${PI_USER:-robert}@${PI_IP:-192.168.68.117}"
DIR="/home/robert/comics-downloader"

rsync -avz --exclude node_modules --exclude .git ./ "$PI:$DIR/"

ssh "$PI" bash -s << 'EOF'
cd /home/robert/comics-downloader
set -a; source .env; set +a

# Mount TrueNAS
bash scripts/mount_truenas.sh

# Start stack
docker compose -f docker-compose.yml up -d --build

# Verify
sleep 10
curl -s http://localhost:3000/health
EOF
```

**Step 2: ARM64 compose override**

```yaml
# docker-compose.pi.yml (para --build local no Pi)
services:
  backend:
    build:
      args:
        GOARCH: arm64
  worker:
    build:
      args:
        - TARGETARCH=arm64
```

Nota: Jandapress (ghcr.io/sinkaroid/jandapress:latest), postgres:16-alpine, redis:7-alpine ja tem suporte ARM64 nativo.

**Step 3: Testar**

Run: `bash scripts/deploy_pi.sh`
Expected: containers rodando, healthcheck OK

**Step 4: Commit**

```bash
git add scripts/deploy_pi.sh docker-compose.pi.yml
git commit -m "feat: Pi5 deploy script with TrueNAS mount"
```

---

### Task 9: Healthcheck + Logging + Dashboard

**Objective:** Monitoramento do stack completo.

**Files:**
- Create: `backend/internal/monitor/health.go`

**Step 1: Endpoint /health**

```go
func healthCheck(db, redis, jandaCheck func() error) gin.HandlerFunc {
    return func(c *gin.Context) {
        c.JSON(200, gin.H{
            "status": "ok",
            "services": gin.H{
                "postgres":  db() == nil,
                "redis":     redis() == nil,
                "jandapress": jandaCheck() == nil,
            },
            "queue_size": redisLLen("download:queue"),
            "galleries_total": dbCountGalleries(),
            "storage_path": storageBasePath,
            "uptime": time.Since(startTime).String(),
        })
    }
}
```

**Step 2: Docker healthchecks**

```yaml
backend:
  healthcheck:
    test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
    interval: 30s

jandapress:
  healthcheck:
    test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
    interval: 30s
```

**Step 3: Commit**

```bash
git add backend/internal/monitor/
git commit -m "feat: health endpoint, docker healthchecks"
```

---

## Comparativo: Plano Original vs Revisado (Sinkaroid)

| Aspecto | Plano Original | Plano Revisado |
|---------|----------------|----------------|
| API de dados | Construir do zero (Go + cloudscraper) | **Reutilizar Jandapress** (Bun + Cheerio, 7 sites, testado) |
| Download engine | Go + cloudscraper subprocess | **Reutilizar Tomoe** (Python, pip install, bulk/PDF) |
| Bypass CF | cloudscraper manual | Jandapress (API v2 oficial) + fallback cloudscraper |
| Cache | Redis so para fila | Jandapress ja usa Redis (Keyv) para cache de metadata |
| Sites suportados | So nhentai | 7 sites de graca (nhentai, pururin, hentaifox, etc.) |
| Esforco de construcao | ~3.5h (11 tasks, construir tudo) | **~2h (9 tasks, integrar ecossistema)** |
| Manutencao | 100% nossa | Updates do Jandapress/Tomoe via git pull |
| Risco de API quebrar | Alto (nosso scraping) | Baixo (projeto ativo, sinkaroid mantem) |
| ARM64 compatibilidade | Precisava buildar Go ARM | Jandapress ja tem Docker ARM, Tomoe e Python puro |

## Resumo do que o sinkaroid ja entrega pronto

| Componente | O que faz | Nosso uso |
|------------|-----------|-----------|
| **Jandapress** | API REST: `GET /api/gallery/nhentai/:id`, `GET /api/search/nhentai?q=`, `GET /api/random/nhentai` | Servico interno no Docker, consultado pelo backend Go |
| **Tomoe** | `tomoe --nhentai 177013` baixa a galeria completa em pasta com JSON metadata | Chamado pelo worker Python para download real |
| **janda** (lib Python) | Cliente Python para Jandapress (ja usado pelo Tomoe) | Dependency do worker |

Nao precisamos construir scraping nem downloader -- so orquestrar.

## Tasks (Revisadas)

| Task | Descricao | Componentes sinkaroid | Estimativa |
|------|-----------|----------------------|------------|
| 1 | Jandapress como servico Docker | Usa ghcr.io/sinkaroid/jandapress | 10min |
| 2 | PostgreSQL schema + Go models | N/A (nosso) | 20min |
| 3 | Backend Go com cliente Jandapress | Consulta Jandapress para dados | 25min |
| 4 | Fila Redis + Worker com Tomoe | Worker chama `tomoe --nhentai` | 25min |
| 5 | Frontend React | N/A (nosso) | 30min |
| 6 | Cloudflare fallback chain | Jandapress API v2 + cloudscraper backup | 15min |
| 7 | Storage TrueNAS + CBZ | Processa saida do Tomoe | 15min |
| 8 | Deploy Pi5 | ARM64 nativo | 15min |
| 9 | Healthcheck + logging | N/A (nosso) | 10min |
| **Total** | | | **~2h** |

## Perguntas em Aberto

1. **Nome do projeto?** Sugiro algo generico como "comics-downloader" ou "gallery-downloader-v4" para manter consistencia com projetos anteriores, sem mencionar nhentai no nome publico.
2. **Tomoe como CLI ou como lib Python?** Atualmente usamos CLI (`subprocess.run(["tomoe", "--nhentai", "123"])`). Poderiamos usar a lib `janda` diretamente no worker Python, eliminando dependencia de subprocess.
3. **Cache de thumbnails?** As imagens do nhentai sao salvas no TrueNAS, mas thumbnails de busca poderiam ser cacheadas no Redis pelo Jandapress (ja tem `EXPIRE_CACHE`).
4. **Quantos workers concorrentes no Pi5?** Recomendo 1-2 workers para nao sobrecarregar. O Jandapress + Redis + Postgres ja consomem ~500MB RAM juntos.
