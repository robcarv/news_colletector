# Implantacao de Nhentai Downloader Self-Hosted no Homelab

> **Para Hermes:** Usar subagent-driven-development para implementar tarefa por tarefa.

**Goal:** Implantar um downloader self-hosted de nhentai.net via API, com PostgreSQL, UI React/Go, downloads sincronos e assincronos com fila, fallback Cloudflare, e armazenamento persistente no TrueNAS, rodando no Raspberry Pi 5.

**Arquitetura:**
Sistema em 3 camadas: (1) **Worker** em Go ou Python que consome fila Redis e baixa via API nhentai com bypass Cloudflare (cloudscraper/selenium-playwright), (2) **API Server** REST (FastAPI ou Gin) que gerencia fila de download e metadados, (3) **Frontend** React (Next.js ou Vite) para pesquisa, agendamento e monitoramento. PostgreSQL como banco relacional, Redis para fila de tarefas, armazenamento final no TrueNAS via bind mount NFS/SMB.

**Tech Stack:**
- Backend: Go (Gin) ou Python (FastAPI) -- recomendado Go pela performance em Raspberry Pi
- Frontend: React + Vite + Tailwind
- DB: PostgreSQL 16 (Docker)
- Cache/Fila: Redis 7 (Docker)
- Download engine: nhentai API wrapper + cloudscrape (bypass Cloudflare)
- Containerizacao: Docker Compose
- Storage: bind mount para SMB share do TrueNAS (/mnt/truenas/comics)

---
Depois de pesquisar os repositorios publicos no GitHub, **nenhum projeto existente atende a todos os requisitos** simultaneamente:

| Projeto | Postgres | UI Web | Fila Async | Docker | Bypass CF | Ativo |
|---------|----------|--------|------------|--------|-----------|-------|
| SongOfTheFallen/nhentai-downloader | SQLite | Sim | Parcial | Sim | Nao | 2024 |
| Kaizoku (oae/kaizoku) | **Sim** | Sim | Sim (Redis) | Sim | Nao (manga) | 2025 |
| yamete (jaymoulin) | Nao | Nao | Nao | Sim | Nao | 2023 |
| nhentai_archivist | Nao | Nao | Nao | Nao | Nao | 2023 |
| 9-FS/nhentai_archivist | Nao | Nao | Parcial | Nao | Nao | 2022 |

**Conclusao:** A abordagem mais viavel e **construir um novo sistema** inspirado na arquitetura do Kaizoku (Postgres + Redis + Go) mas especifico para nhentai, com os requisitos de fallback Cloudflare e storage no TrueNAS.

---

## Tasks

### Task 1: Setup do projeto -- estrutura Docker Compose + repositorio

**Objective:** Criar estrutura de diretorios, docker-compose.yml, e configuracao base do projeto.

**Files:**
- Create: `comics-downloader/docker-compose.yml`
- Create: `comics-downloader/.env.example`
- Create: `comics-downloader/README.md`

**Step 1: Criar estrutura de diretorios**

```bash
mkdir -p comics-downloader/{backend,frontend,nginx,scripts}
cd comics-downloader
```

**Step 2: Escrever docker-compose.yml**

```yaml
version: '3.8'

volumes:
  postgres_data:
  redis_data:

networks:
  comics-net:
    driver: bridge

services:
  postgres:
    image: postgres:16-alpine
    container_name: comics-db
    restart: unless-stopped
    networks:
      - comics-net
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=comics
      - POSTGRES_DB=comics
      - POSTGRES_PASSWORD=${DB_PASSWORD:-comics_secret}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U comics"]
      interval: 5s
      timeout: 5s
      retries: 5

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

  backend:
    build: ./backend
    container_name: comics-backend
    restart: unless-stopped
    networks:
      - comics-net
    ports:
      - "3000:3000"
    volumes:
      - ${COMICS_STORAGE:-./data}:/data
    environment:
      - DATABASE_URL=postgresql://comics:${DB_PASSWORD:-comics_secret}@postgres:5432/comics
      - REDIS_URL=redis://redis:6379/0
      - COMICS_PORT=3000
      - STORAGE_PATH=/data
      - TZ=America/Sao_Paulo
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build: ./frontend
    container_name: comics-frontend
    restart: unless-stopped
    networks:
      - comics-net
    ports:
      - "8080:80"
    environment:
      - API_URL=http://backend:3000
    depends_on:
      - backend
```

**Step 3: Escrever .env.example**

```env
# Database
DB_PASSWORD=comics_secret

# Storage (mount do TrueNAS SMB)
COMICS_STORAGE=/mnt/truenas/comics

# Timezone
TZ=America/Sao_Paulo
```

**Step 4: Commit**

```bash
git init
git add docker-compose.yml .env.example README.md
git commit -m "feat: docker-compose scaffold with postgres, redis, backend, frontend"
```

---

### Task 2: Backend Go -- modelo de dados e migrations (PostgreSQL)

**Objective:** Criar schema do banco de dados relacional com tabelas para galleries, downloads, e tags.

**Files:**
- Create: `backend/go.mod`
- Create: `backend/go.sum`
- Create: `backend/cmd/server/main.go`
- Create: `backend/internal/database/migrations.go`
- Create: `backend/internal/models/gallery.go`
- Create: `backend/internal/models/download.go`
- Create: `backend/internal/models/tag.go`

**Step 1: Inicializar modulo Go**

```bash
cd backend
go mod init github.com/robert/comics-downloader
go get github.com/jackc/pgx/v5
go get github.com/go-redis/redis/v8
go get github.com/gin-gonic/gin
```

**Step 2: Escrever modelo Gallery (Postgres SQL + struct)**

```go
// internal/models/gallery.go
package models

import "time"

type Gallery struct {
    ID          int       `json:"id" db:"id"`
    NhentaiID   int       `json:"nhentai_id" db:"nhentai_id"`
    Title       string    `json:"title" db:"title"`
    TitleJP     string    `json:"title_jp" db:"title_jp"`
    Pages       int       `json:"pages" db:"pages"`
    MediaID     string    `json:"media_id" db:"media_id"`
    CoverURL    string    `json:"cover_url" db:"cover_url"`
    Status      string    `json:"status" db:"status"` // pending, downloading, completed, error
    Downloaded  bool      `json:"downloaded" db:"downloaded"`
    CreatedAt   time.Time `json:"created_at" db:"created_at"`
    UpdatedAt   time.Time `json:"updated_at" db:"updated_at"`
}
```

```go
// internal/models/download.go
package models

import "time"

type DownloadJob struct {
    ID          int       `json:"id" db:"id"`
    GalleryID   int       `json:"gallery_id" db:"gallery_id"`
    Type        string    `json:"type" db:"type"` // sync, async
    Status      string    `json:"status" db:"status"` // queued, running, completed, failed
    Progress    int       `json:"progress" db:"progress"` // 0-100
    ErrorMsg    string    `json:"error_msg" db:"error_msg"`
    Retries     int       `json:"retries" db:"retries"`
    MaxRetries  int       `json:"max_retries" db:"max_retries"`
    CreatedAt   time.Time `json:"created_at" db:"created_at"`
    CompletedAt *time.Time `json:"completed_at" db:"completed_at"`
}
```

```go
// internal/models/tag.go
package models

type Tag struct {
    ID      int    `json:"id" db:"id"`
    Name    string `json:"name" db:"name"`
    Type    string `json:"type" db:"type"` // tag, artist, character, parodia, group, language, category
}

type GalleryTag struct {
    GalleryID int `json:"gallery_id"`
    TagID     int `json:"tag_id"`
}
```

**Step 3: Escrever migrations SQL**

```go
// internal/database/migrations.go
package database

var migrations = []string{
    `CREATE TABLE IF NOT EXISTS galleries (
        id SERIAL PRIMARY KEY,
        nhentai_id INTEGER UNIQUE NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        title_jp TEXT NOT NULL DEFAULT '',
        pages INTEGER NOT NULL DEFAULT 0,
        media_id TEXT NOT NULL DEFAULT '',
        cover_url TEXT NOT NULL DEFAULT '',
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        downloaded BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )`,
    `CREATE TABLE IF NOT EXISTS tags (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) UNIQUE NOT NULL,
        type VARCHAR(50) NOT NULL DEFAULT 'tag'
    )`,
    `CREATE TABLE IF NOT EXISTS gallery_tags (
        gallery_id INTEGER NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
        tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
        PRIMARY KEY (gallery_id, tag_id)
    )`,
    `CREATE TABLE IF NOT EXISTS download_jobs (
        id SERIAL PRIMARY KEY,
        gallery_id INTEGER NOT NULL REFERENCES galleries(id) ON DELETE CASCADE,
        type VARCHAR(10) NOT NULL DEFAULT 'async',
        status VARCHAR(20) NOT NULL DEFAULT 'queued',
        progress INTEGER NOT NULL DEFAULT 0,
        error_msg TEXT NOT NULL DEFAULT '',
        retries INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        completed_at TIMESTAMPTZ
    )`,
    `CREATE INDEX IF NOT EXISTS idx_galleries_status ON galleries(status)`,
    `CREATE INDEX IF NOT EXISTS idx_galleries_nhentai_id ON galleries(nhentai_id)`,
    `CREATE INDEX IF NOT EXISTS idx_download_jobs_status ON download_jobs(status)`,
}
```

**Step 4: Rodar as migrations**

Run: `go run cmd/server/main.go --migrate-only`
Expected: tabelas criadas, exit 0

**Step 5: Commit**

```bash
git add backend/
git commit -m "feat: postgres schema with galleries, tags, download_jobs"
```

---

### Task 3: Backend Go -- cliente nhentai API com fallback Cloudflare

**Objective:** Implementar cliente HTTP para a API do nhentai.net com multiplas estrategias de bypass para Cloudflare.

**Files:**
- Create: `backend/internal/nhentai/client.go`
- Create: `backend/internal/nhentai/api.go`
- Create: `backend/internal/nhentai/downloader.go`
- Create: `backend/internal/nhentai/types.go`

**Step 1: Escrever teste unitario**

```go
// internal/nhentai/client_test.go
package nhentai

import (
    "testing"
)

func TestFetchGalleryInfo(t *testing.T) {
    client := NewClient(ClientConfig{
        Timeout: 30,
    })
    info, err := client.FetchGalleryInfo(177013)
    if err != nil {
        t.Fatalf("expected no error, got %v", err)
    }
    if info.ID != 177013 {
        t.Fatalf("expected ID 177013, got %d", info.ID)
    }
}
```

**Step 2: Escrever cliente com fallback**

```go
// internal/nhentai/client.go
package nhentai

import (
    "fmt"
    "net/http"
    "time"
)

type ClientConfig struct {
    Timeout       int
    ProxyURL      string
    CookiesDir    string
    CfClearance   string
    UserAgent     string
}

type Client struct {
    httpClient    *http.Client
    config        ClientConfig
    fallbacks     []DownloadStrategy
}
```

Estrategias de download em ordem de fallback:

1. **API direta** -- `GET https://nhentai.net/api/gallery/{id}` (pode cair com CF)
2. **Cloudscraper** -- via subprocess Python (bypass CF automatico)
3. **Playwright** -- via chromedp (headless browser, ultimo recurso)

```go
// internal/nhentai/api.go
package nhentai

// GalleryInfo representa a resposta da API do nhentai
type GalleryInfo struct {
    ID       int    `json:"id"`
    MediaID  string `json:"media_id"`
    Title    struct {
        English string `json:"english"`
        Japanese string `json:"japanese"`
        Pretty   string `json:"pretty"`
    } `json:"title"`
    Images   struct {
        Pages []ImageInfo `json:"pages"`
        Cover ImageInfo   `json:"cover"`
        Thumb ImageInfo   `json:"thumbnail"`
    } `json:"images"`
    NumPages int    `json:"num_pages"`
    Tags     []struct {
        ID   int    `json:"id"`
        Type string `json:"type"`
        Name string `json:"name"`
        URL  string `json:"url"`
    } `json:"tags"`
}

type ImageInfo struct {
    T string `json:"t"` // jpg, png, gif
    W int    `json:"w"`
    H int    `json:"h"`
}
```

**Step 3: Executar teste**

Run: `go test ./internal/nhentai/ -v -run TestFetchGalleryInfo`
Expected: PASS (ou SKIP se API offline, com log claro)

**Step 4: Commit**

```bash
git add backend/internal/nhentai/
git commit -m "feat: nhentai API client with Cloudflare bypass fallback strategies"
```

---

### Task 4: Backend Go -- sistema de fila de download (async + sync)

**Objective:** Implementar gerenciamento de fila com Redis (para async) e execucao direta (para sync), com persistencia em Postgres.

**Files:**
- Modify: `backend/internal/models/download.go`
- Create: `backend/internal/queue/manager.go`
- Create: `backend/internal/queue/worker.go`
- Create: `backend/internal/queue/redis_queue.go`

**Step 1: Escrever teste de fila**

```go
// internal/queue/manager_test.go
package queue

import (
    "context"
    "testing"
)

func TestEnqueueAndDequeue(t *testing.T) {
    // ...
}
```

**Step 2: Implementar RedisQueue**

```go
// internal/queue/redis_queue.go
package queue

import (
    "context"
    "encoding/json"
    "github.com/go-redis/redis/v8"
)

type QueueItem struct {
    JobID     int    `json:"job_id"`
    GalleryID int    `json:"gallery_id"`
    NhentaiID int    `json:"nhentai_id"`
    Type      string `json:"type"` // sync, async
}

type RedisQueue struct {
    client *redis.Client
    key    string
}

func (q *RedisQueue) Enqueue(ctx context.Context, item QueueItem) error {
    data, _ := json.Marshal(item)
    return q.client.LPush(ctx, q.key, data).Err()
}

func (q *RedisQueue) Dequeue(ctx context.Context) (*QueueItem, error) {
    data, err := q.client.BRPop(ctx, 0, q.key).Result()
    if err != nil {
        return nil, err
    }
    var item QueueItem
    json.Unmarshal([]byte(data[1]), &item)
    return &item, nil
}
```

**Step 3: Implementar Worker**

Worker que:
- Escuta Redis queue continuamente (goroutine)
- Para cada item: atualiza status para "running" no Postgres
- Chama o downloader
- Em caso de erro: tenta fallback Cloudflare, retry ate 3x
- Atualiza progresso a cada pagina baixada
- Ao finalizar: status "completed" + caminho do arquivo

**Step 4: Rota REST para download sync vs async**

- `POST /api/download/:id` + `?mode=sync|async`
- Sync: espera o worker terminar (channel/goroutine)
- Async: enfileira e retorna job_id imediatamente

**Step 5: Commit**

```bash
git add backend/internal/queue/
git commit -m "feat: Redis queue + worker for sync/async downloads with retry"
```

---

### Task 5: Backend Go -- API REST (Gin)

**Objective:** Implementar endpoints REST para buscar, agendar e monitorar downloads.

**Files:**
- Create: `backend/internal/api/router.go`
- Create: `backend/internal/api/handlers.go`
- Create: `backend/internal/api/middleware.go`

**Step 1: Definir endpoints**

| Method | Path | Descricao |
|--------|------|-----------|
| GET | /api/galleries | Listar galleries (paginado, filtro por status) |
| GET | /api/galleries/search | Buscar por titulo/tag |
| GET | /api/galleries/:id | Detalhes de uma gallery |
| POST | /api/galleries | Adicionar por nhentai ID |
| POST | /api/download/:id | Iniciar download (?mode=sync|async) |
| GET | /api/download/:id/status | Status do download |
| GET | /api/jobs | Listar jobs de download |
| GET | /api/stats | Estatisticas (total, baixados, pendentes) |
| POST | /api/galleries/bulk | Adicionar varios IDs de uma vez |

**Step 2: Escrever handlers**

```go
// internal/api/handlers.go
package api

func (h *Handler) SearchGalleries(c *gin.Context) {
    query := c.Query("q")
    tags := c.QueryArray("tags")
    page, _ := strconv.Atoi(c.DefaultQuery("page", "1"))
    
    galleries, total, err := h.db.SearchGalleries(query, tags, page)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    c.JSON(200, gin.H{"galleries": galleries, "total": total, "page": page})
}

func (h *Handler) CreateDownload(c *gin.Context) {
    id, _ := strconv.Atoi(c.Param("id"))
    mode := c.DefaultQuery("mode", "async")
    
    job, err := h.queue.CreateJob(id, mode)
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    if mode == "sync" {
        result := h.queue.WaitForJob(job.ID)
        c.JSON(200, result)
    } else {
        c.JSON(202, gin.H{"job_id": job.ID, "status": "queued"})
    }
}
```

**Step 3: Testar endpoints**

Run: `go test ./internal/api/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add backend/internal/api/
git commit -m "feat: REST API with gallery search, download queue, stats"
```

---

### Task 6: Frontend React -- projeto e componentes base

**Objective:** Criar projeto React com Vite, Tailwind, e componentes de UI para pesquisa e gerenciamento.

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/pages/Dashboard.tsx`
- Create: `frontend/src/pages/Search.tsx`
- Create: `frontend/src/pages/GalleryDetail.tsx`
- Create: `frontend/src/components/GalleryCard.tsx`
- Create: `frontend/src/components/DownloadQueue.tsx`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/Dockerfile`
- Create: `frontend/nginx.conf`

**Step 1: Inicializar projeto**

```bash
cd frontend
npm create vite@latest . -- --template react-ts
npm install tailwindcss @tailwindcss/vite react-router-dom
```

**Step 2: Componente GalleryCard**

```tsx
// src/components/GalleryCard.tsx
interface GalleryCardProps {
  id: number;
  title: string;
  coverUrl: string;
  pages: number;
  status: string;
  downloaded: boolean;
  tags: string[];
}

export function GalleryCard({ id, title, coverUrl, pages, status, downloaded, tags }: GalleryCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
      <div className="relative aspect-[3/4]">
        <img src={coverUrl} alt={title} className="w-full h-full object-cover" />
        {downloaded && (
          <span className="absolute top-2 right-2 bg-green-600 text-xs px-2 py-1 rounded">
            Downloaded
          </span>
        )}
      </div>
      <div className="p-3">
        <h3 className="text-sm font-medium text-white truncate">{title}</h3>
        <p className="text-xs text-gray-400 mt-1">{pages} pages</p>
        {status === "downloading" && (
          <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
            <div className="bg-blue-500 h-2 rounded-full w-1/3"></div>
          </div>
        )}
        <div className="flex flex-wrap gap-1 mt-2">
          {tags.slice(0, 3).map((t) => (
            <span key={t} className="text-xs bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded">
              {t}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
```

**Step 3: Pagina Search com filtros**

```tsx
// src/pages/Search.tsx
export function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Gallery[]>([]);

  const handleSearch = async () => {
    const data = await api.getGalleries({ q: query });
    setResults(data.galleries);
  };

  const handleDownload = async (id: number, mode: "sync" | "async") => {
    await api.createDownload(id, mode);
  };

  return (
    <div className="container mx-auto p-4">
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by title, tag, artist..."
          className="flex-1 bg-gray-800 text-white px-4 py-2 rounded-lg border border-gray-700"
        />
        <button onClick={handleSearch}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700">
          Search
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        {results.map((g) => (
          <GalleryCard key={g.id} {...g} />
        ))}
      </div>
    </div>
  );
}
```

**Step 4: Dockerfile para frontend (multi-stage)**

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
git commit -m "feat: React frontend with search, gallery cards, download queue"
```

---

### Task 7: Script Cloudflare bypass -- cloudscraper helper

**Objective:** Criar script Python auxiliar para bypass do Cloudflare via cloudscraper, chamado pelo backend Go como subprocess.

**Files:**
- Create: `backend/scripts/cf_bypass.py`
- Create: `backend/internal/nhentai/cf_bypass.go`

**Step 1: Script Python cloudscraper**

```python
#!/usr/bin/env python3
# scripts/cf_bypass.py
"""Bypass Cloudflare protection for nhentai using cloudscraper.

Usage:
    python cf_bypass.py gallery 177013
    python cf_bypass.py page 177013 1 jpg
"""
import cloudscraper
import json
import sys
import os

scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'linux',
        'mobile': False,
    }
)

def fetch_gallery(gallery_id):
    url = f"https://nhentai.net/api/gallery/{gallery_id}"
    resp = scraper.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

def fetch_page(media_id, page_num, ext="jpg"):
    url = f"https://i.nhentai.net/galleries/{media_id}/{page_num}.{ext}"
    resp = scraper.get(url, timeout=30)
    resp.raise_for_status()
    return resp.content

if __name__ == "__main__":
    command = sys.argv[1]
    if command == "gallery":
        result = fetch_gallery(int(sys.argv[2]))
        print(json.dumps(result))
    elif command == "page":
        data = fetch_page(sys.argv[2], int(sys.argv[3]), sys.argv[4])
        sys.stdout.buffer.write(data)
    else:
        print(json.dumps({"error": "unknown command"}), file=sys.stderr)
        sys.exit(1)
```

**Step 2: Wrapper Go**

```go
// internal/nhentai/cf_bypass.go
package nhentai

import (
    "encoding/json"
    "os/exec"
)

type CfBypass struct {
    ScriptPath string
}

func (c *CfBypass) FetchGallery(id int) (*GalleryInfo, error) {
    cmd := exec.Command("python3", c.ScriptPath, "gallery", fmt.Sprintf("%d", id))
    output, err := cmd.Output()
    if err != nil {
        return nil, fmt.Errorf("cf_bypass error: %w", err)
    }
    var info GalleryInfo
    if err := json.Unmarshal(output, &info); err != nil {
        return nil, fmt.Errorf("cf_bypass parse error: %w", err)
    }
    return &info, nil
}

func (c *CfBypass) DownloadPage(mediaID string, pageNum int, ext string) ([]byte, error) {
    cmd := exec.Command("python3", c.ScriptPath, "page", mediaID, 
        fmt.Sprintf("%d", pageNum), ext)
    return cmd.Output()
}
```

**Step 3: Testar bypass**

Run: `python3 scripts/cf_bypass.py gallery 177013 | python3 -m json.tool`
Expected: JSON com dados da gallery (ou log informativo se CF blocker ativo)

**Step 4: Commit**

```bash
git add backend/scripts/ backend/internal/nhentai/cf_bypass.go
git commit -m "feat: Cloudflare bypass via cloudscraper Python helper"
```

---

### Task 8: Storage layer -- integracao com TrueNAS via SMB/NFS

**Objective:** Configurar persistencia dos CBZs no TrueNAS e mapear como volume Docker.

**Files:**
- Modify: `docker-compose.yml`
- Create: `scripts/mount_truenas.sh`
- Create: `backend/internal/storage/fs.go`

**Step 1: Script de montagem SMB**

```bash
#!/bin/bash
# scripts/mount_truenas.sh
# Mount TrueNAS SMB share for comics storage

TRUENAS_IP="${TRUENAS_IP:-192.168.68.124}"
SHARE_NAME="${SHARE_NAME:-comics}"
MOUNT_POINT="${MOUNT_POINT:-/mnt/truenas/comics}"
SMB_USER="${SMB_USER:-robert}"
SMB_PASS="${SMB_PASS}"

mkdir -p "$MOUNT_POINT"

if mountpoint -q "$MOUNT_POINT"; then
    echo "Already mounted at $MOUNT_POINT"
    exit 0
fi

mount -t cifs "//${TRUENAS_IP}/${SHARE_NAME}" "$MOUNT_POINT" \
    -o "username=${SMB_USER},password=${SMB_PASS},uid=1000,gid=1000,iocharset=utf8,file_mode=0755,dir_mode=0755,noperm"

echo "Mounted $SHARE_NAME at $MOUNT_POINT"
```

**Step 2: Service no docker-compose**

```yaml
# Adicionar ao docker-compose.yml
backend:
  volumes:
    - ${COMICS_STORAGE:-./data}:/data:rshared
```

O diretorio `${COMICS_STORAGE}` (ex: `/mnt/truenas/comics`) e montado no container como `/data`. O backend salva os CBZs em `/data/{gallery_id}/`.

**Step 3: Storage service Go**

```go
// internal/storage/fs.go
package storage

import (
    "fmt"
    "os"
    "path/filepath"
)

type FileStorage struct {
    BasePath string // /data
}

func (s *FileStorage) SaveGallery( galleryID int, pages [][]byte, format string ) (string, error) {
    dir := filepath.Join(s.BasePath, fmt.Sprintf("%d", galleryID))
    os.MkdirAll(dir, 0755)
    
    // Salva paginas como CBZ (zip)
    cbzPath := filepath.Join(s.BasePath, fmt.Sprintf("%d.cbz", galleryID))
    // ... zip logic ...
    
    return cbzPath, nil
}

func (s *FileStorage) GetGalleryPath(galleryID int) string {
    return filepath.Join(s.BasePath, fmt.Sprintf("%d", galleryID))
}

func (s *FileStorage) GalleryExists(galleryID int) bool {
    _, err := os.Stat(filepath.Join(s.BasePath, fmt.Sprintf("%d.cbz", galleryID)))
    return err == nil
}
```

**Step 4: Testar montagem**

Run: `sudo bash scripts/mount_truenas.sh && ls -la /mnt/truenas/comics`
Expected: diretorio montado com arquivos do TrueNAS visiveis

**Step 5: Adicionar ao fstab (persistente)**

```bash
echo "//192.168.68.124/comics /mnt/truenas/comics cifs username=robert,password=<pass>,uid=1000,gid=1000,iocharset=utf8,_netdev 0 0" | sudo tee -a /etc/fstab
```

**Step 6: Commit**

```bash
git add scripts/ backend/internal/storage/ docker-compose.yml
git commit -m "feat: TrueNAS SMB mount and file storage layer"
```

---

### Task 9: Deploy no Raspberry Pi 5

**Objective:** Executar o stack completo no Raspberry Pi 5 (192.168.68.117), com storage apontando para o TrueNAS.

**Files:**
- Create: `scripts/deploy_pi.sh`
- Create: `docker-compose.pi.yml` (override ARM-specific)

**Step 1: Script de deploy**

```bash
#!/bin/bash
# scripts/deploy_pi.sh
set -e

PI_HOST="${PI_USER:-robert}@${PI_IP:-192.168.68.117}"
PROJECT_DIR="/home/robert/comics-downloader"

echo "=== Deploying comics-downloader to Pi ==="

# 1. Sync project
rsync -avz --exclude 'node_modules' --exclude '.git' \
    ./ "$PI_HOST:$PROJECT_DIR/"

# 2. SSH and deploy
ssh "$PI_HOST" << 'EOF'
    cd /home/robert/comics-downloader

    # Load env
    set -a; source .env; set +a

    # Mount TrueNAS storage
    export TRUENAS_IP=192.168.68.124
    export COMICS_STORAGE=/mnt/truenas/comics
    bash scripts/mount_truenas.sh

    # Pull images (ARM-compatible)
    docker compose -f docker-compose.yml pull

    # Start stack
    docker compose -f docker-compose.yml up -d --build

    # Verify
    sleep 5
    curl -s http://localhost:3000/api/stats | head -c 200
    echo ""
    echo "=== Deploy complete ==="
EOF
```

**Step 2: docker-compose.pi.yml (ARM overrides)**

```yaml
# docker-compose.pi.yml
version: '3.8'
services:
  backend:
    platform: linux/arm64
    build:
      context: ./backend
      dockerfile: Dockerfile.arm
  
  postgres:
    image: postgres:16-alpine  # Ja suporta ARM64
  
  redis:
    image: redis:7-alpine  # Ja suporta ARM64
```

**Step 3: Dockerfile.arm para backend**

```dockerfile
# backend/Dockerfile.arm
FROM golang:1.22-alpine AS build
RUN apk add --no-cache gcc musl-dev
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o server ./cmd/server/main.go

FROM alpine:3.19
RUN apk add --no-cache python3 py3-pip ca-certificates tzdata
RUN pip3 install cloudscraper
COPY --from=build /app/server /server
COPY scripts/cf_bypass.py /scripts/cf_bypass.py
EXPOSE 3000
CMD ["/server"]
```

**Step 4: Testar deploy**

Run: `bash scripts/deploy_pi.sh`
Expected: containers running, API respondendo em http://192.168.68.117:3000

**Step 5: Commit**

```bash
git add scripts/deploy_pi.sh docker-compose.pi.yml backend/Dockerfile.arm
git commit -m "feat: Pi deploy script with ARM64 Dockerfile and TrueNAS mount"
```

---

### Task 10: Integracao com Komga (opcional)

**Objective:** Apos download, importar automaticamente os CBZs no Komga para leitura via browser.

**Files:**
- Create: `backend/internal/komga/client.go`
- Create: `backend/internal/komga/importer.go`

**Step 1: Cliente Komga API**

```go
// internal/komga/client.go
package komga

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
)

type Client struct {
    BaseURL  string
    Username string
    Password string
    token    string
}

func (c *Client) Login() error {
    // POST /api/v1/auth/login
    // ...
}

func (c *Client) ImportFile(path string) error {
    // POST /api/v1/books  (multipart upload)
    // ...
}
```

**Step 2: Hook pos-download**

```go
// internal/komga/importer.go
package komga

// Chamado apos completar download com sucesso
func (c *Client) ImportDownloadedGallery(galleryID int, cbzPath string) error {
    if err := c.Login(); err != nil {
        return fmt.Errorf("komga login: %w", err)
    }
    return c.ImportFile(cbzPath)
}
```

**Step 3: Commit**

```bash
git add backend/internal/komga/
git commit -m "feat: Komga auto-import integration"
```

---

### Task 11: Healthcheck, logging e monitoring

**Objective:** Adicionar endpoints de saude, logging estruturado, e metricas basicas.

**Files:**
- Create: `backend/internal/monitor/health.go`
- Create: `backend/internal/monitor/logger.go`

**Step 1: Endpoint /health**

```go
func (h *Handler) Health(c *gin.Context) {
    c.JSON(200, gin.H{
        "status": "ok",
        "postgres": h.db.Ping() == nil,
        "redis": h.redis.Ping() == nil,
        "storage": h.storage.Check() == nil,
        "uptime": time.Since(startTime).String(),
        "queued_jobs": h.queue.Count(),
        "total_galleries": h.db.CountGalleries(),
    })
}
```

**Step 2: Logging estruturado**

```go
package monitor

import (
    "log/slog"
    "os"
)

var Logger = slog.New(slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
    Level: slog.LevelInfo,
}))

// Uso: monitor.Logger.Info("download completed", "gallery_id", id, "pages", n)
```

**Step 3: Adicionar ao Docker healthcheck**

```yaml
backend:
  healthcheck:
    test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
```

**Step 4: Commit**

```bash
git add backend/internal/monitor/
git commit -m "feat: health endpoint, structured logging, docker healthcheck"
```

---

## Verificacao Final

Apos todas as tasks, verificar:

- [ ] `docker compose up -d` sobe sem erros no Pi5
- [ ] `curl http://192.168.68.117:3000/health` retorna 200 OK
- [ ] `curl http://192.168.68.117:3000/api/galleries/search?q=test` retorna resultados
- [ ] Frontend em `http://192.168.68.117:8080` carrega e pesquisa
- [ ] Download async: `POST /api/download/123?mode=async` retorna job_id
- [ ] Download sync: `POST /api/download/123?mode=sync` baixa e retorna CBZ
- [ ] Fallback Cloudflare ativo quando API direta falha
- [ ] CBZ salvo em `/mnt/truenas/comics/` (montagem SMB)
- [ ] Komga mostra o CBZ importado (se configurado)
- [ ] `docker compose logs` sem erros

## Riscos e Tradeoffs

| Risco | Mitigacao |
|-------|-----------|
| nhentai API muda ou cai | Fallback cloudscraper + Playwright |
| Cloudflare bloqueia todas as requests | Rotacao de User-Agent + proxy pool |
| Raspberry Pi 5 RAM insuficiente (8GB) | Workers configurados para 2 downloads concorrentes |
| Storage SMB lento para downloads grandes | Usar NFS para melhor performance, ou storage local no Pi com sync periodico |
| Perda de dados no Redis | Jobs persistem em Postgres; Redis usado so como fila volatil |
| ARM64 incompatibilidade de imagens | Precisa buildar backend Go nativamente; postgres/redis ja tem ARM |

## Perguntas em Aberto

1. **Prefere Go ou Python como backend?** Go e mais leve para Pi e performatico para concorrencia, mas Python tem cloudscraper nativo. Solucao hibrida proposta: Go server + subprocess Python para bypass.
2. **Formato de saida preferido?** CBZ (Comic Book Zip) para compatibilidade com Komga/Kavita, ou pastas com metadados JSON?
3. **Deve integrar com Komga automaticamente ou manter separado?** Se o TrueNAS share ja e lido pelo Komga,
4. **Cache das imagens nhentai?** As imagens sao salvas localmente, mas as URLs de thumbnail/cover podem ser cacheadas pra nao re-baixar.
5. **Quantos downloads concorrentes no Pi5?** Recomendo comecar com 2 workers para nao sobrecarregar RAM/CPU.

---

## Resumo do Plano

| Task | Descricao | Arquivos | Estimativa |
|------|-----------|----------|------------|
| 1 | Docker Compose scaffold | 3 | 10min |
| 2 | Postgres schema + models | 6 | 20min |
| 3 | nhentai API client + CF bypass | 5 | 30min |
| 4 | Redis queue + workers | 4 | 25min |
| 5 | REST API (Gin) | 3 | 20min |
| 6 | Frontend React + Vite | 10 | 45min |
| 7 | Cloudflare bypass script | 2 | 15min |
| 8 | TrueNAS SMB storage | 3 | 15min |
| 9 | Deploy no Raspberry Pi 5 | 3 | 20min |
| 10 | Komga integration (opcional) | 2 | 15min |
| 11 | Healthcheck + monitoring | 2 | 10min |
| **Total** | | ~43 | ~3.5h |
