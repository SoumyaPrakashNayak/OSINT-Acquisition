# OSINT Intelligence Component

A standalone, modular Open Source Intelligence (OSINT) data-acquisition and candidate discovery component designed for law-enforcement intelligence platforms, architected for eventual integration into **S.I.R.I.S. (Smart Intelligence for Real-Time Investigation Support)**.

---

## 1. Overview

The OSINT Intelligence Component independently solves the earliest phase of the intelligence acquisition pipeline: converting known target person identifiers into structured, deterministic search queries and gathering candidate public web and news sources.

Crucially, this component treats all discovered records as **unverified candidate results**. It does not perform person resolution, automated entity extraction, or draw investigative conclusions—those belong to downstream phases in S.I.R.I.S.

---

## 2. Current Scope

This repository implements strictly:

* **Phase 0 — Foundation & API**: FastAPI application, structured error handling, correlation ID middleware, and Pydantic validation for `TargetPerson`.
* **Phase 1 — Query Generation**: Deterministic, prioritized query generation heuristics without combinatorial explosion.
* **Phase 2 — Web / News Discovery**: Provider abstraction layer (`SearchProvider`), deterministic `MockSearchProvider`, real `HttpSearchProvider` (SearXNG / SerpAPI / Tavily), URL validation, domain extraction, tracking-parameter sanitization, deduplication, and fault-tolerant query execution.
* **Phase 3 — Web Content Acquisition**: Safe, asynchronous HTTP web resource retrieval, `WebFetcher` abstraction, `MockWebFetcher`, `HttpWebFetcher`, SSRF & private IP range blocking, streaming response-size limits, redirect control, SHA-256 cryptographic hashing, normalized `WebDocument`, structured acquisition error contracts, controlled concurrency batching, and API endpoints (`POST /osint/fetch`, `POST /osint/fetch-batch`).
* **Phase 4 — Web Content Extraction**: Deterministic, passive HTML extraction from authoritative `WebDocument`, non-content & boilerplate elimination (`script`, `style`, `noscript`, `svg`, `nav`, `footer`, `aside`, ads, cookie banners), multi-level fallback metadata extraction (title, description, canonical URL, author/byline normalization, ISO-8601 publication/modified dates, language), primary content container detection (`article` -> `main` -> class container -> `body`), ordered headings (`h1`–`h6`), hyperlink extraction with base resolution, and volume-based content quality classification (`EMPTY`, `LOW`, `MEDIUM`, `HIGH`). Strict offline execution with zero network requests and full provenance preservation.

### Explicitly Excluded (Future Phases)
* ❌ Named Entity Recognition (NER) / LLM reasoning
* ❌ Person resolution & fuzzy matching (Jaro-Winkler / Levenshtein)
* ❌ Social media APIs (Telegram, Facebook, Instagram)
* ❌ Neo4j graph databases / PostgreSQL / Vector stores

---

## 3. Architecture

```text
                    ┌───────────────────────────┐
                    │       TARGET PERSON       │
                    │                           │
                    │  name (required)          │
                    │  aliases: list[str]       │
                    │  location: str | None     │
                    │  organization: str | None │
                    │  username: str | None     │
                    │  phone: str | None        │
                    │  keywords: list[str]      │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │      QUERY GENERATOR      │
                    │   (Deterministic & Pure)  │
                    │   Priority 1: Exact name  │
                    │   Priority 2: Location    │
                    │   Priority 3: Org context │
                    │   Priority 4: Full combo  │
                    │   Priority 5: Aliases     │
                    └─────────────┬─────────────┘
                                  │ List[str] Queries
                                  ▼
                    ┌───────────────────────────┐
                    │     DISCOVERY SERVICE     │
                    │   Fault-tolerant runner   │
                    └─────────────┬─────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
          ┌───────────────────┐       ┌───────────────────┐
          │ MockSearchProvider│       │ HttpSearchProvider│
          │ (Zero-dependency) │       │ (External Search) │
          └─────────┬─────────┘       └─────────┬─────────┘
                    └─────────────┬─────────────┘
                                  │ Raw Search Results
                                  ▼
                    ┌───────────────────────────┐
                    │   NORMALIZATION & DEDUP   │
                    │   - Validate HTTP/HTTPS   │
                    │   - Extract source domain │
                    │   - Strip tracking params │
                    │   - Deduplicate by URL    │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │    DISCOVERY RESPONSE     │
                    │   Candidate URLs & source │
                    │   metadata for S.I.R.I.S. │
                    └───────────────────────────┘
```

---

## 4. Installation

### Prerequisites
* Python 3.11+
* pip

### Setup Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Environment Configuration
Copy the sample environment file:
```bash
cp .env.example .env
```

By default, `SEARCH_PROVIDER=mock` is active, allowing completely offline, deterministic testing with zero external API dependencies.

---

## 5. Running the Application

Start the local development server:

```bash
python run.py
```
*or using Uvicorn directly:*
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The interactive OpenAPI documentation will be available at:
* Swagger UI: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* ReDoc: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

---

## 6. Testing

Run the automated pytest test suite:

```bash
pytest -v tests/
```

All 119 unit and integration tests across Phases 0, 1, 2, 3, and 4 run offline without network access using deterministic fixtures and mocks.

---

## 7. API Reference

### 7.1 Health Check

```http
GET /health
```

#### Response:
```json
{
  "status": "ok"
}
```

---

### 7.2 OSINT Target Discovery

```http
POST /osint/discover
Content-Type: application/json
```

#### Request Body Example:
```json
{
  "name": "Ramesh Kumar",
  "aliases": [
    "Ramesh",
    "R. Kumar"
  ],
  "location": "Bhubaneswar",
  "organization": "ABC Ltd",
  "phone": "+919876543210",
  "username": "rkumar",
  "keywords": [
    "director",
    "tender"
  ]
}
```

#### Successful Response (`200 OK`):
```json
{
  "target": {
    "name": "Ramesh Kumar",
    "aliases": ["Ramesh", "R. Kumar"],
    "phone": "+919876543210",
    "location": "Bhubaneswar",
    "organization": "ABC Ltd",
    "username": "rkumar",
    "keywords": ["director", "tender"]
  },
  "queries": [
    "\"Ramesh Kumar\"",
    "\"Ramesh Kumar\" Bhubaneswar",
    "\"Ramesh Kumar\" \"ABC Ltd\"",
    "\"Ramesh Kumar\" Bhubaneswar \"ABC Ltd\"",
    "\"Ramesh\"",
    "\"Ramesh\" Bhubaneswar",
    "\"Ramesh\" \"ABC Ltd\"",
    "\"Ramesh\" Bhubaneswar \"ABC Ltd\"",
    "\"R. Kumar\"",
    "\"R. Kumar\" Bhubaneswar",
    "\"R. Kumar\" \"ABC Ltd\"",
    "\"R. Kumar\" Bhubaneswar \"ABC Ltd\"",
    "\"rkumar\"",
    "\"Ramesh Kumar\" \"rkumar\"",
    "\"+919876543210\"",
    "\"Ramesh Kumar\" \"+919876543210\"",
    "\"Ramesh Kumar\" director",
    "\"Ramesh Kumar\" Bhubaneswar director",
    "\"Ramesh Kumar\" tender",
    "\"Ramesh Kumar\" Bhubaneswar tender"
  ],
  "results": [
    {
      "title": "Public Record: Ramesh Kumar Profile & Activity",
      "url": "https://news.odishatoday.example.org/articles/ramesh-kumar-8a5f1e",
      "source": "news.odishatoday.example.org",
      "snippet": "Recent public reporting regarding Ramesh Kumar in community archives.",
      "published_at": "2026-09-21T10:30:00Z"
    }
  ],
  "total_results": 1,
  "warnings": []
}
```

#### Validation Error Response (`422 Unprocessable Content`):
```json
{
  "error": {
    "code": "INVALID_TARGET",
    "message": "body -> name: Value error, Target person 'name' must not be empty or blank",
    "details": [
      {
        "loc": ["body", "name"],
        "msg": "Value error, Target person 'name' must not be empty or blank",
        "type": "value_error"
      }
    ]
  }
}
```

---

### 7.3 Single URL Content Acquisition (Phase 3)

```http
POST /osint/fetch
Content-Type: application/json
```

#### Request:
```json
{
  "url": "https://example.com/article"
}
```

#### Successful Acquisition Response (`200 OK`):
```json
{
  "success": true,
  "document": {
    "requested_url": "https://example.com/article",
    "final_url": "https://example.com/article",
    "domain": "example.com",
    "status_code": 200,
    "content_type": "text/html",
    "content_length": 1420,
    "html": "<!DOCTYPE html><html><body><h1>Public Notice</h1></body></html>",
    "retrieved_at": "2026-09-22T04:10:00Z",
    "content_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  },
  "error": null,
  "metadata": null
}
```

#### Controlled Acquisition Failure (`200 OK`):
*When the remote server returns 404, 403, 429, timeout, or SSRF-blocked address:*
```json
{
  "success": false,
  "document": null,
  "metadata": {
    "requested_url": "https://example.com/missing",
    "final_url": "https://example.com/missing",
    "status_code": 404,
    "content_type": "text/html",
    "retrieved_at": "2026-09-22T04:10:00Z"
  },
  "error": {
    "code": "HTTP_NOT_FOUND",
    "message": "The remote server returned HTTP 404.",
    "retryable": false
  }
}
```

---

### 7.4 Batch Content Acquisition (Phase 3)

```http
POST /osint/fetch-batch
Content-Type: application/json
```

#### Request:
```json
{
  "urls": [
    "https://example.com/article-1",
    "https://example.com/missing"
  ]
}
```

#### Response (`200 OK`):
```json
{
  "total": 2,
  "successful": 1,
  "failed": 1,
  "results": [
    {
      "url": "https://example.com/article-1",
      "success": true,
      "document": {
        "requested_url": "https://example.com/article-1",
        "final_url": "https://example.com/article-1",
        "domain": "example.com",
        "status_code": 200,
        "content_type": "text/html",
        "content_length": 1200,
        "html": "<html>...</html>",
        "retrieved_at": "2026-09-22T04:10:00Z",
        "content_hash": "a5f8..."
      },
      "error": null,
      "metadata": null
    },
    {
      "url": "https://example.com/missing",
      "success": false,
      "document": null,
      "error": {
        "code": "HTTP_NOT_FOUND",
        "message": "The remote server returned HTTP 404.",
        "retryable": false
      },
      "metadata": {
        "requested_url": "https://example.com/missing",
        "final_url": "https://example.com/missing",
        "status_code": 404,
        "content_type": "text/html",
        "retrieved_at": "2026-09-22T04:10:00Z"
      }
    }
  ]
}
```

---

### 7.5 Web Content Extraction (Phase 4)

```http
POST /osint/extract
Content-Type: application/json
```

#### Request Body:
```json
{
  "web_document": {
    "requested_url": "https://news.example.com/article-42",
    "final_url": "https://news.example.com/article-42",
    "domain": "news.example.com",
    "status_code": 200,
    "content_type": "text/html",
    "content_length": 4520,
    "html": "<!DOCTYPE html><html><head><title>Police Probe High-Value Tender Fraud</title><meta name=\"author\" content=\"By Sarah Connor\"><meta property=\"article:published_time\" content=\"2026-09-22T08:00:00Z\"></head><body><article><h1>Police Probe High-Value Tender Fraud</h1><p>State enforcement agencies initiated proceedings today.</p><p>Multiple records were seized during dawn inspections.</p></article></body></html>",
    "retrieved_at": "2026-09-22T08:05:00Z",
    "content_hash": "b2f6c91a..."
  }
}
```

#### Successful Extraction Response (`200 OK`):
```json
{
  "success": true,
  "document": {
    "requested_url": "https://news.example.com/article-42",
    "final_url": "https://news.example.com/article-42",
    "domain": "news.example.com",
    "content_hash": "b2f6c91a...",
    "retrieved_at": "2026-09-22T08:05:00Z",
    "title": "Police Probe High-Value Tender Fraud",
    "description": null,
    "canonical_url": null,
    "author": "Sarah Connor",
    "publication_date": "2026-09-22T08:00:00Z",
    "modified_date": null,
    "language": null,
    "headings": [
      {
        "level": 1,
        "text": "Police Probe High-Value Tender Fraud"
      }
    ],
    "paragraphs": [
      "State enforcement agencies initiated proceedings today.",
      "Multiple records were seized during dawn inspections."
    ],
    "text": "State enforcement agencies initiated proceedings today.\n\nMultiple records were seized during dawn inspections.",
    "links": [],
    "content_length": 109,
    "word_count": 14,
    "character_count": 109,
    "paragraph_count": 2,
    "heading_count": 1,
    "link_count": 0,
    "extraction_method": "deterministic_html_article",
    "content_quality": "LOW",
    "warnings": []
  },
  "error": null
}
```

#### Controlled Extraction Failure (`200 OK`):
*When extracting from empty, non-HTML, or corrupted documents:*
```json
{
  "success": false,
  "document": null,
  "error": {
    "code": "EMPTY_HTML",
    "message": "WebDocument HTML payload is empty or whitespace only",
    "retryable": false,
    "details": {
      "final_url": "https://example.com/blank"
    }
  }
}
```

---

## 8. Security & Operational Controls

* **SSRF Prevention**: Strict URL scheme checks (only `http`/`https`). Blocks requests to `localhost`, `127.0.0.0/8`, `0.0.0.0/8`, RFC 1918 private ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local metadata (`169.254.0.0/16`), and equivalent IPv6 addresses.
* **Open Redirect Defense**: Each hop in an HTTP redirect chain is re-validated against SSRF policy before making subsequent requests.
* **Redirect Limits**: Chains exceeding `MAX_REDIRECTS` (default 5) abort safely with `TOO_MANY_REDIRECTS`.
* **Streaming Size Limits**: Responses larger than `MAX_RESPONSE_SIZE_MB` (default 10 MB) are aborted while reading chunks to prevent memory exhaustion attacks.
* **Controlled Concurrency**: Batch fetches use an `asyncio.Semaphore` bound by `MAX_CONCURRENT_FETCHES` (default 5).
* **Passive DOM Parsing (Phase 4)**: HTML extraction operates strictly offline with zero socket connections or outbound HTTP I/O (`BeautifulSoup` using standard `html.parser`). Script execution is completely disabled, mitigating stored XSS or remote payload triggers during extraction.
* **Raw Document Immutability**: Source `WebDocument.html` and cryptographic `content_hash` remain immutable across all extraction steps, ensuring full forensic chain-of-custody.

---

## 9. Future Phases Roadmap

* **Phase 5 — Entity Extraction (NER)**: Extract persons, organizations, locations, vehicle numbers, and statutory sections.
* **Phase 6 — Person Resolution**: Disambiguation using phonetic algorithms and string metrics (Jaro-Winkler, Levenshtein).
* **Phase 7 — Relationship Extraction**: Infer entity-to-entity linkages from co-occurrences and contextual analysis.
* **Phase 8 — Telegram Public OSINT**: Extend discovery to publicly indexed Telegram channels and broadcast feeds.
* **Phase 9 — Evidence & Provenance**: Cryptographic hashing (SHA-256) and chain-of-custody metadata stamping.
* **Phase 10 — S.I.R.I.S. Integration**: Direct ingestion into Central Intelligence FastAPI and Neo4j Knowledge Graph.
