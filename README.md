<div align="center">

# LLM-NewsHub

### AI-Powered News Intelligence Platform

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
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

---

## Key Features

### Core Pipeline
- **Multi-source Scraping** — Fundus (news publishers) + Reddit (social media)
- **Fake News Detection** — Random Forest classifier with sentiment + feature analysis
- **Smart Clustering** — TF-IDF vectorization with silhouette-score-optimized K-Means
- **LLM Article Generation** — Multi-model support (GPT-4, Qwen, Gemini, Perplexity)
- **Multimedia Production** — Stable Diffusion images, TTS audio, Wav2Lip video sync

### New Features
- **Trend Analysis Engine** — Detects trending topics, category shifts, and sentiment patterns across dates
- **Multi-language Translation** — Translates articles to 10+ languages via LLM
- **Smart News Digest** — AI-powered daily digests with category breakdowns and key highlights
- **Fuzzy Search** — Typo-tolerant article search using fuzzy string matching

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
| FastAPI | REST API backend |
| React 18 (TypeScript) | Frontend UI |
| Material UI | Component library |
| Recharts | Data visualization |
| Docker Compose | Containerized deployment |
| Nginx | Reverse proxy |

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
# 1. Clone the repo
git clone https://github.com/manavaghera/LLM-NEWS-.git
cd LLM-NEWS-

# 2. Setup environment
conda create -n llm-news python=3.10
conda activate llm-news
pip install -r requirements.txt
python setup_nltk.py

# 3. Configure API keys
cp .env.example .env
# Edit .env with your keys

# 4. Run the full pipeline
python pipeline/run.py --date "2025-06-21"

# 5. Launch the web app
cd apps && docker compose up
```

Visit `http://localhost:3000`

---

## API Endpoints

<details>
<summary><strong>Core Endpoints</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/news` | List news articles |
| GET | `/api/news/articles/{date}/{group_id}` | Get article by ID |
| POST | `/api/chat` | Chat with news assistant |
| GET | `/api/config` | Get app configuration |

</details>

<details>
<summary><strong>Trend Analysis</strong></summary>

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trends/topics` | Trending topics with growth analysis |
| GET | `/api/trends/categories` | Category-level article count trends |
| GET | `/api/trends/sentiment` | Sentiment tracking per category |
| GET | `/api/trends/publishers` | Publisher & regional diversity analysis |

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
| GET | `/api/digest/daily/{date}` | Generate daily news digest |
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
│   │   └── core/            #     Configuration
│   └── frontend/            #   React frontend (TypeScript)
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
├── pipeline/                # Pipeline orchestration
└── infrastructure/          # Airflow & cloud
```

---

## Environment

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| OS | macOS / Linux / Windows | Linux |
| Python | 3.10+ | 3.10 |
| RAM | 8GB | 16GB |
| Docker | Optional | Required for web app |

---

## Contributing

Contributions are welcome! Feel free to open issues, submit pull requests, or fork this project.

---
