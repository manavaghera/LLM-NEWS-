<div align="center">

# LLM-NewsHub

### AI-Powered News Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.142-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-24-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)](https://scikit-learn.org)

<br>

**Scrape. Classify. Cluster. Generate. Deliver.**

An end-to-end AI pipeline that transforms raw news data into intelligent, multimedia content — fully automated with Large Language Models.

<br>

![Architecture](LLM-News/source/demo.gif)

</div>

---

## Overview

LLM-NewsHub automates the entire news production workflow using cutting-edge AI:

| Stage | What It Does |
|-------|-------------|
| **Scrape** | Collects articles from Fundus publishers and Reddit discussions |
| **Structure** | Extracts event/statement cards with metadata from raw content |
| **Classify** | Categorizes articles (KNN/SVC) and detects fake news (Random Forest) |
| **Cluster** | Groups related stories using TF-IDF + K-Means with optimal K detection |
| **Generate** | Creates full articles with LLMs, including images and audio |
| **Deliver** | Serves everything through a modern React + FastAPI web app |

There are two ways to produce the news:

- **Quick news** (`pipeline/quick_news.py`, recommended): public RSS feeds + one AI key. Groups the same
  event across outlets, writes articles, fact-checks every sentence against its sources, compares how
  outlets covered multi-source stories, and adds images and audio. Runs in a few minutes.
- **Full pipeline** (`pipeline/run.py`): the original research pipeline above. Needs Reddit and
  RapidAPI keys, Kaggle datasets and trained classifiers.

---

## Key Features

### Core Pipeline
- **Multi-source Scraping** — Fundus (news publishers) + Reddit (social media)
- **Fake News Detection** — Random Forest classifier with sentiment + feature analysis
- **Smart Clustering** — TF-IDF vectorization with silhouette-score-optimized K-Means
- **LLM Article Generation** — Multi-model support (GPT-4, Qwen, Gemini, Perplexity)
- **Multimedia Production** — Stable Diffusion images, TTS audio, Wav2Lip video sync

### Trust
- **Every claim sourced** — numbered citations link each section to the original reporting
- **Fact-check pass** — a second model checks every sentence against the sources and removes
  unsupported ones; the article shows what was removed and why (`CHECK_MODEL` can be a different model)
- **"How each outlet covered it"** — angle, tone, emphasis and omissions per outlet for multi-source stories
- **Accuracy tracking** — share of statements removed per day and per model, plus reader reports, on Trends
- **Full text only where allowed** — articles are fetched only from publishers that haven't opted out of
  AI use and whose robots.txt allows it; everything else uses RSS summaries

### Reading
- **Web app** — front page by category, archive search, follow topics ("For you"), saved stories
- **Chat** — streaming answers that cite the article's sources or the day's stories
- **Daily digest** with a spoken briefing; per-article audio, also in 10 translated languages
- **Trends** — named topics, coverage and tone by category, publishers cited
- **Sharing** — link previews for chat apps and social sites, RSS feed, optional daily email

---

## Architecture

```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  Scrapers    │───>│  Card Gen    │───>│  Classifier   │
│  (Fundus,    │    │  (Event &    │    │  (Category +  │
│   Reddit)    │    │  Statement)  │    │  Fake News)   │
└─────────────┘    └──────────────┘    └───────┬───────┘
                                               │
                   ┌──────────────┐    ┌───────▼───────┐
                   │  Article Gen │<───│   Clustering  │
                   │  (LLM)       │    │  (TF-IDF +    │
                   └──────┬───────┘    │   K-Means)    │
                          │            └───────────────┘
              ┌───────────┼───────────┐
              ▼           ▼           ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │  Image   │ │  Audio   │ │ Summary  │
        │  (SD)    │ │  (TTS)   │ │  Video   │
        └──────────┘ └──────────┘ └──────────┘
              │           │           │
              └───────────┼───────────┘
                          ▼
                   ┌──────────────┐     ┌──────────────┐
                   │  Web App     │────>│  Analytics   │
                   │  (React +    │     │  (Trends,    │
                   │  FastAPI)    │     │   Digest,    │
                   └──────────────┘     │   Translate) │
                                        └──────────────┘
```

---

## Tech Stack

<details>
<summary><strong>Backend Pipeline</strong></summary>

| Technology | Purpose |
|-----------|---------|
| Python 3.10 | Core language |
| PyTorch | Deep learning framework |
| HuggingFace Transformers | LLM integration |
| sentence-transformers | Semantic embeddings |
| scikit-learn | Classification (KNN, SVC, Random Forest) & Clustering (K-Means) |
| NLTK / TextBlob / VADER | NLP & Sentiment Analysis |
| BeautifulSoup / PRAW / feedparser | Web scraping |
| tiktoken | Token counting & optimization |

</details>

<details>
<summary><strong>Web Application</strong></summary>

| Technology | Purpose |
|-----------|---------|
| FastAPI | REST API backend, streaming chat (server-sent events) |
| React 19 + TypeScript + Vite | Frontend (`LLM-News/apps/web`) |
| TanStack Query, React Router | Data loading and routing |
| Tailwind CSS, Radix UI | Styling and accessible dialogs |
| Recharts | Data visualization |
| edge-tts | Spoken summaries and briefings |
| SQLite | Reader reports |
| Docker Compose + Nginx | Containerized deployment and reverse proxy |

</details>

<details>
<summary><strong>Infrastructure</strong></summary>

| Technology | Purpose |
|-----------|---------|
| Docker | Containerization |
| Airflow | Workflow orchestration |
| Kubernetes / Minikube | Container orchestration |
| Alibaba Cloud | Cloud deployment |

</details>

---

## Quick Start

```bash
# 1. Clone and configure (all commands from LLM-News/)
git clone https://github.com/manavaghera/LLM-NEWS-.git
cd LLM-NEWS-/LLM-News
cp .env.example .env        # add an AI key, e.g. OPENROUTER_API_KEY, and LLM_PUBLISHER=OPENROUTER
                            # (free for testing: NVIDIA_API_KEY from build.nvidia.com, LLM_PUBLISHER=NVIDIA)

# 2. Write today's news (Python 3.11)
python -m venv .venv
.venv/bin/pip install -r requirements/quick_news.txt     # Windows: .venv\Scripts\pip
.venv/bin/python pipeline/quick_news.py

# 3. Run the website with Docker...
cd apps && docker compose up --build                     # http://localhost:3000

# ...or without Docker (two terminals; see LLM-News/apps/README.md)
cd apps && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --port 8000
cd apps/web && npm ci && npm run dev                     # http://localhost:5173
```

`pipeline/daily_update.py --every 07:00` refreshes the news every morning (and prepares the digest and
briefing). The original full pipeline is still available: `python pipeline/run.py --date YYYY-MM-DD`
(see `LLM-News/quick_start.md`).

---

## API Endpoints

<details>
<summary><strong>Core Endpoints</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check and configured AI providers |
| GET | `/api/news?date=` | Stories of an edition |
| GET | `/api/news/dates` | Every edition (`?limit=` for the newest N) |
| GET | `/api/news/search?q=` | Search every edition |
| GET | `/api/news/articles/{date}/{group_id}` | Full article |
| GET | `/api/news/articles/{date}/{group_id}/related` | Earlier coverage of the same story |
| POST | `/api/chat/stream` | Chat (server-sent events, cites numbered sources) |
| GET | `/api/chat/models` | Models the chat can use |
| GET | `/api/audio/article/{date}/{group_id}/{lang}` | Spoken summary (English or a translation) |
| POST | `/api/reports` | Reader reports a problem (list: `GET` with `X-Admin-Token`) |
| GET | `/share/{date}/{group_id}` | Link-preview page for chat apps and social sites |
| GET | `/feed.xml` | RSS feed |

AI endpoints are rate-limited per visitor (`AI_RATE_LIMIT`) and capped per day (`AI_DAILY_CALL_LIMIT`).

</details>

<details>
<summary><strong>Trend Analysis</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trends/topics` | Trending topics with growth analysis |
| GET | `/api/trends/categories` | Category-level article count trends |
| GET | `/api/trends/sentiment` | Sentiment tracking per category |
| GET | `/api/trends/publishers` | Publisher & regional diversity analysis |
| GET | `/api/trends/accuracy` | Fact-check results per day and model, reader reports |

</details>

<details>
<summary><strong>Translation</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/translate/languages` | List supported languages |
| POST | `/api/translate/article` | Translate full article to target language(s) |
| POST | `/api/translate/text` | Translate arbitrary text |

</details>

<details>
<summary><strong>Digest</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/digest/daily/{date}` | Daily news digest (written once, then saved) |
| GET | `/api/digest/daily/{date}/audio` | The digest read aloud |
| GET | `/api/digest/daily` | Digest for latest date |
| POST | `/api/digest/category` | Category-specific digest |

</details>

---

## Project Structure

```
LLM-NewsHub/
├── apps/                    # Web application
│   ├── app/                 #   FastAPI backend
│   │   ├── api/endpoints/   #     REST API endpoints
│   │   ├── services/        #     Business logic
│   │   └── core/            #     Configuration, AI providers, rate limits
│   ├── tests/               #   Backend tests (pytest)
│   └── web/                 #   React frontend (Vite + TypeScript)
├── pipeline/                # quick_news.py (RSS news), daily_update.py, email_digest.py,
│                            #   news_checks.py (fact-check), full_text.py, media.py; run.py (full pipeline)
├── tests/                   # Pipeline tests
├── scrapers/                # Data collection
│   ├── fundus/              #   News article scraper
│   ├── reddit/              #   Reddit scraper
│   └── trust_score/         #   Publisher trust scoring
├── card/                    # Content structuring
├── classifier/              # ML models
│   ├── category/            #   News classifier (KNN/SVC)
│   └── fake_news/           #   Fake news detector (RF)
├── cluster/                 # TF-IDF + K-Means clustering
├── generate_article/        # LLM article generation
├── deployment/              # Multimedia generation
│   ├── audio/               #   TTS
│   ├── image/               #   Stable Diffusion
│   ├── summary/             #   Video summary
│   └── video/               #   Wav2Lip
├── evaluate/                # Quality evaluation (BLEU, ROUGE)
└── infrastructure/          # Airflow & cloud
```

---

## Environment

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| OS | macOS / Linux / Windows | Linux |
| Python | 3.11 (website, quick news) | 3.11 |
| Node.js | 22 (website) | 22 |
| RAM | 2GB (website, quick news); 8GB+ (full pipeline) | 16GB for the full pipeline |
| Docker | Optional | Easiest way to run the website |

Tests: `cd LLM-News/apps && python -m pytest tests`, `cd LLM-News && python -m pytest tests`,
`cd LLM-News/apps/web && npm test`, and browser tests with `npm run test:e2e` (Playwright). GitHub Actions
runs them all on every push and pull request.

To put the site online with HTTPS, see "Put it online" in [LLM-News/apps/README.md](LLM-News/apps/README.md).

---

## Contributing

Contributions are welcome! Feel free to open issues, submit pull requests, or fork this project.

---
