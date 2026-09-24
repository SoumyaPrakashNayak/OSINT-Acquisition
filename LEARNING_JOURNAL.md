# OSINT Component Engineering & Architecture Learning Journal

This journal documents key architectural decisions, design patterns, technical challenges, gotchas, and domain lessons encountered during the design and implementation of the isolated OSINT Intelligence Component for **S.I.R.I.S. (Smart Intelligence for Real-Time Investigation Support)**.

---

## 📖 Table of Contents

1. [Core Philosophical & Architectural Principles](#1-core-philosophical--architectural-principles)
2. [Milestone Logs & Phase Breakdown](#2-milestone-logs--phase-breakdown)
   - [Phase 0: Foundation & API](#phase-0-foundation--api)
   - [Phase 1: Deterministic Query Generation](#phase-1-deterministic-query-generation)
   - [Phase 2: Discovery, Abstractions & Normalization](#phase-2-discovery-abstractions--normalization)
3. [Engineering Insights & Technical Gotchas](#3-engineering-insights--technical-gotchas)
4. [Design Patterns Applied](#4-design-patterns-applied)
5. [Looking Ahead: Future Phase Roadmap](#5-looking-ahead-future-phase-roadmap)

---

## 1. Core Philosophical & Architectural Principles

### 🧠 Principle A: Candidate Results ≠ Verified Intelligence
* **The Trap:** When searching for a target like `"Ramesh Kumar" Bhubaneswar`, it is tempting to immediately classify a search result containing `"Ramesh Kumar"` as a match.
* **The Reality:** In law enforcement intelligence, identity verification belongs to an isolated downstream resolution layer. At the OSINT acquisition stage, the component must only state:
  > *"This is a candidate result from a public source."*
* **Lesson:** Keeping candidate gathering decoupled from person resolution prevents premature bias, reduces false positives, and preserves evidentiary integrity.

### 🎯 Principle B: Determinism Over Stochastic Explosion
* **The Trap:** Naively combining all known attributes (name, aliases, location, organization, phone, username, keywords) leads to exponential query explosion (e.g., $2^N$ queries), flooding search APIs and exhausting rate limits.
* **The Reality:** Structured prioritization ensures high signal-to-noise ratio:
  1. Exact quoted full name: `"{name}"`
  2. Exact name + location: `"{name}" {location}`
  3. Exact name + organization: `"{name}" "{organization}"`
  4. Fully qualified context: `"{name}" {location} "{organization}"`
  5. Alias queries (contextualized)
  6. Dedicated handle, phone, and keyword hooks.
* **Lesson:** Deterministic query ordering allows identical inputs to produce identical outputs, making tests reproducible and investigation audits legally sound.

### 🔌 Principle C: Provider Inversion (Zero Vendor Lock-In)
* **The Trap:** Hard-coding a single commercial search API (Google, Bing, or SerpAPI) makes the component brittle, costly, and dependent on third-party uptime.
* **The Reality:** The system depends on a `SearchProvider` protocol. The core pipeline is agnostic to whether results originate from an offline mock, an on-premise open-source meta-search engine like SearXNG, or commercial APIs.
* **Lesson:** Offline deterministic mocking enables 100% test coverage without consuming search credits or requiring internet access during CI/CD.

---

## 2. Milestone Logs & Phase Breakdown

### Phase 0: Foundation & API
* **Objective:** Establish the standalone FastAPI application, request-level investigation IDs, structured error handling, and `TargetPerson` validation.
* **Key Decisions:**
  - Used Pydantic v2 field validators to sanitize names, strip edge whitespace, and eliminate blank items from alias/keyword lists.
  - Required only `name` as mandatory; targets can be investigated even with sparse initial data.
  - Implemented `GET /health` with zero external dependencies to support container health probes.

### Phase 1: Deterministic Query Generation
* **Objective:** Pure, dependency-free query synthesis from `TargetPerson`.
* **Key Decisions:**
  - Implemented `QueryGenerator` with zero dependencies on FastAPI, HTTP clients, or databases.
  - Quoting semantics: multi-word names and organizations are wrapped in double quotes for exact search operator behavior, while locations and keywords remain contextual.
  - Deduplication preserves insertion order via ordered dictionary key semantics.

### Phase 2: Discovery, Abstractions & Normalization
* **Objective:** Multi-provider discovery, URL sanitization, deduplication, and fault-tolerant orchestration.
* **Key Decisions:**
  - Implemented `MockSearchProvider` with deterministic hashing and simulated error hooks for testing resilience.
  - Implemented `HttpSearchProvider` supporting SearXNG, SerpAPI, Tavily, and generic search engines using async `httpx`.
  - Implemented URL normalization: stripping tracking parameters (`utm_*`, `fbclid`, `gclid`, etc.) while retaining vital functional query arguments (`id`, `article`, `v`).
  - Added fault tolerance: if query $N$ fails due to a network glitch or timeout, the pipeline logs a warning, appends it to `response.warnings`, and returns all other successful candidate results without crashing.

### Phase 3: Web Content Acquisition
* **Objective:** Safe, asynchronous web document retrieval from candidate public URLs with zero content extraction.
* **Key Decisions:**
  - Strict Boundary: Content acquisition preserves the unparsed raw HTML markup and calculates a SHA-256 cryptographic hash for provenance. Text extraction and NER are strictly reserved for subsequent phases.
  - Three Error Categories: Clear operational separation between Category A (invalid API request -> 422), Category B (controlled fetch failure such as 404, 403, 429, timeout -> 200 with structured `AcquisitionError`), and Category C (unexpected bugs -> 500 without stack trace leaks).
  - Open Redirect & SSRF Defense: Implemented `validate_url_policy` that inspects scheme (HTTP/HTTPS only) and checks destination IPs against private, loopback, link-local, and reserved ranges using Python's `ipaddress`. Critically, every redirect hop is re-validated to prevent open-redirect SSRF bypasses.
  - Streaming Size Limits: Bounded response body reading incrementally chunk-by-chunk up to `MAX_RESPONSE_SIZE_MB` (10 MB), aborting oversized responses before exhausting server RAM.
### Phase 4: Web Content Extraction
* **Objective:** Purely passive, deterministic parsing and extraction of metadata, headings, hyperlinks, and primary article body from raw HTML documents.
* **Key Decisions:**
  - Zero Outbound I/O: Extraction is strictly inert. The parser (`BeautifulSoup` using standard `html.parser`) executes without socket/network access, preventing secondary request amplification, remote payload triggers, or tracking beacons.
  - Immutability & Provenance: The input `WebDocument` (raw HTML, cryptographic SHA-256 hash, timestamps) is preserved untouched to maintain strict evidentiary chain-of-custody for downstream law enforcement analysis.
  - Multi-Level Metadata Fallbacks: Deterministic fallback chains are established for page title (`og:title` -> `twitter:title` -> `<title>` -> `<h1>`), description (`meta[name="description"]` -> `og:description` -> `twitter:description`), and canonical URL.
  - Deterministic Primary Container Detection: Priority matching scans `<article>` first, followed by `<main>`, followed by known class containers (`article-body`, `post-content`, etc.), gracefully falling back to cleaned `<body>` if semantic wrappers are omitted.
  - Quality Metric Stratification: Implemented volume-based metrics (`word_count`, `character_count`, `heading_count`, `link_count`) and classified documents into deterministic tiers (`EMPTY`, `LOW`, `MEDIUM`, `HIGH`) to allow downstream pipelines to filter out thin or uninformative pages.

### Phase 5: Entity Extraction / Named Entity Recognition (NER)
* **Objective:** Purely passive, deterministic identification and extraction of identifiable entities mentioned within `ExtractedDocument` text without resolving identities or drawing investigative conclusions.
* **Key Decisions:**
  - Strict Architectural Boundary (Extraction ≠ Resolution): Phase 5 only answers: *"Which identifiable entities are explicitly mentioned in this content?"* It strictly forbids declaring whether an extracted person is the investigation target, suspect, or associate. Identity matching, risk scoring, and knowledge graph construction are segregated into subsequent phases.
  - Zero ML / Zero Network Offline Strategy: Avoided heavy non-standard ML runtimes that require automatic downloads or lack wheels on Python 3.14. Built a production-grade `DeterministicEntityExtractor` combining high-precision regex engines, extensive Indian and global gazetteers, honorific/contextual grammar rules, and structural corporate/institutional pattern matchers. Operates 100% offline with zero network latency and sub-second test execution.
  - Substring Offset Guarantee: Enforced `document.text[start_offset:end_offset] == entity.text` across all extracted mentions, ensuring downstream evidence highlighting and forensic cross-referencing remain perfectly aligned.
  - Conservative Normalization: Strips whitespace, standardizes casing on emails, cleans phone number punctuation while preserving international dialing prefixes (`+91`), and standardizes unambiguous ISO dates without fabricating missing years.
  - Mention Tracking vs. Deduplication: The pipeline tracks every individual entity occurrence as an `ExtractedEntity` mention, while simultaneously computing deterministic `UniqueEntity` aggregates with their specific `EntityOccurrence` spans.
  - Provenance Anchoring: Every entity mention inherits the cryptographic SHA-256 `source_document_hash` and `source_url` from Phase 4, maintaining an unbroken chain of custody.

---

## 3. Engineering Insights & Technical Gotchas

### ⚠️ Gotcha 1: Pydantic v2 `ctx` Serialization in FastAPI Exception Handlers
* **Issue:** When catching `RequestValidationError`, `exc.errors()` can return dictionaries containing a `"ctx"` key whose values are raw Python exception objects (e.g. `ValueError("Target person 'name' must not be empty")`).
* **Symptom:** `TypeError: Object of type ValueError is not JSON serializable` during JSON response serialization.
* **Solution:** Explicitly sanitize the error list before returning, casting any values in `"ctx"` to strings or using primitives.

### ⚠️ Gotcha 2: Starlette HTTP 422 Deprecation
* **Issue:** `status.HTTP_422_UNPROCESSABLE_ENTITY` triggers a `StarletteDeprecationWarning`.
* **Solution:** Migrated to `status.HTTP_422_UNPROCESSABLE_CONTENT` to maintain forward compatibility with modern ASGI standards.

### ⚠️ Gotcha 3: Credential Leakage in Exception Stack Traces & Logs
* **Issue:** Passing URLs with embedded API tokens or logging failed requests can inadvertently write law-enforcement investigation secrets to log files.
* **Solution:**
  - Implemented `SensitiveDataFilter` in standard Python logging.
  - Sanitized exception messages in `HttpSearchProvider` so that secret tokens and API keys are stripped before exceptions are raised.

### ⚠️ Gotcha 4: Synchronous vs. Asynchronous Mocking in `httpx`
* **Issue:** `response.raise_for_status()` in `httpx` is synchronous. Mocking it with `AsyncMock()` produces `RuntimeWarning: coroutine was never awaited`.
* **Solution:** Mock synchronous methods with `MagicMock()` and asynchronous methods (`client.get`, `client.post`) with `AsyncMock()`.

### ⚠️ Gotcha 5: Starlette BaseHTTPMiddleware and Global 500 Exception Handling
* **Issue:** In Starlette, `BaseHTTPMiddleware` wraps request processing. If an unhandled exception is raised in route execution, Starlette's middleware stack re-raises the exception past standard exception handlers unless trapped inside the middleware coroutine.
* **Symptom:** Unhandled internal exceptions escaped to ASGI test clients instead of returning a clean structured HTTP 500 JSON response.
* **Solution:** Wrapped `call_next(request)` inside the `correlation_id_middleware` in a `try...except Exception` block, returning a sanitized `OSINTError` JSONResponse with the `X-Investigation-ID` header.

### ⚠️ Gotcha 6: Open-Redirect SSRF Attack Vector
* **Issue:** Validating only the initial URL against SSRF rules is insufficient if a benign public URL redirects (HTTP 301/302) to `http://169.254.169.254/latest/meta-data` or `http://127.0.0.1:8000/`.
* **Solution:** Implemented manual redirect stepping in `HttpWebFetcher`, re-validating the `Location` header URL against `validate_url_policy` on every hop before making the next connection.

### ⚠️ Gotcha 7: BeautifulSoup In-Place Tag Decomposition and Stale Node References
* **Issue:** When iterating over `soup.find_all(...)` and calling `tag.decompose()` on parent widgets, subsequent iterations can encounter child tags whose parents have already been unlinked (`tag.parent is None`).
* **Solution:** Guard every node check during DOM sanitation with `if tag.parent is None: continue`, preventing redundant or erroneous operations on already-stripped subtrees.

### ⚠️ Gotcha 8: CSS Hyphenated Class Regex Boundaries
* **Issue:** Regex patterns using word boundaries like `r"\badvertisement\b"` or `r"\bbanner-ad\b"` fail to match common CSS classes like `ad-container`, `ad-box`, or `ad-wrapper` because `\b` does not treat hyphens as word characters, requiring precise composite patterns.
* **Solution:** Used targeted composite patterns like `r"\bad[-_]?(?:container|box|banner|wrapper|slot)\b"` and `r"\bads?\b"` to cleanly capture all ad wrapper conventions while avoiding false positives.

### ⚠️ Gotcha 9: Byline Normalization and Multi-Format Author Metadata
* **Issue:** News sites format bylines inconsistently: some write `"By John Doe"`, others `"Author: John Doe"`, and modern single-page applications embed authors inside JSON-LD structured schemas (`@type: NewsArticle -> author.name`).
* **Solution:** Implemented regex prefix trimming (`r"^(?:by|author\s*:?)\s+"`) and added a JSON-LD parser fallback that inspects Schema.org tags for author declarations when HTML meta tags are absent.

### ⚠️ Gotcha 10: Sentence Boundary Splitting vs. Punctuation in Abbreviations
* **Issue:** Naive sentence splitting on `.` breaks titles (`Dr. Ramesh Kumar`, `Mr. John Doe`), currency abbreviations (`Rs. 50,000`), police ranks (`DGP`, `SP`), and decimals (`10.5 percent`) into false, fragmented sentence spans.
* **Solution:** Implemented `split_sentences_with_spans` with lookback validation against a whitelist of legal, medical, and law-enforcement abbreviations, single-letter initials, and decimal digit lookaheads, preserving clean sentence context without artificial boundaries.

### ⚠️ Gotcha 11: Overlapping Entity Spans & Subsumption Precedence
* **Issue:** A string like `"Odisha Police arrested Ramesh Kumar in Bhubaneswar"` matches both `"Odisha Police"` (ORGANIZATION) and `"Odisha"` (LOCATION) on the same starting offset. Without conflict resolution, overlapping and conflicting entity tokens pollute downstream results.
* **Solution:** Implemented deterministic priority-based span overlap resolution: candidates are sorted by category specificity priority descending, span length descending, and start offset ascending. Once a span is selected, any overlapping sub-spans are deterministically discarded.

### ⚠️ Gotcha 12: Coreference and Alias Isolation
* **Issue:** In an article stating `"Sundar Pichai visited India. Later, Pichai met officials. He spoke to reporters."`, it is tempting to resolve `"Pichai"` and `"He"` to `"Sundar Pichai"`.
* **Solution:** Strictly forbade coreference resolution in Phase 5. Coreference resolution introduces statistical uncertainty and false linkages. Mentions are preserved exactly as stated in the source text; disambiguation and alias clustering are deferred to Phase 6.

---

## 4. Design Patterns Applied

| Pattern | Where Used | Benefit |
| :--- | :--- | :--- |
| **Protocol / Interface** | [app/discovery/provider.py](file:///e:/SIH2026/OSINT/app/discovery/provider.py), [app/acquisition/fetcher.py](file:///e:/SIH2026/OSINT/app/acquisition/fetcher.py), [app/extraction/extractor.py](file:///e:/SIH2026/OSINT/app/extraction/extractor.py) | Decouples discovery, acquisition, and extraction orchestration from concrete parsing engines. |
| **Result Pattern (Success / Failure Monad)** | [app/acquisition/models.py](file:///e:/SIH2026/OSINT/app/acquisition/models.py), [app/extraction/models.py](file:///e:/SIH2026/OSINT/app/extraction/models.py) | Models controlled acquisition/extraction failures (404, 403, empty HTML, unparseable DOM) as explicit data contracts rather than unhandled exceptions. |
| **Dependency Injection** | [app/api/routes.py](file:///e:/SIH2026/OSINT/app/api/routes.py) | Enables swapping providers, fetchers, and extractors (mock vs. real) via FastAPI `Depends`. |
| **Bounded Concurrency via Semaphore** | [app/acquisition/service.py](file:///e:/SIH2026/OSINT/app/acquisition/service.py) | Uses `asyncio.Semaphore` to cap concurrent network operations during batch URL processing. |
| **Scatter / Gather with Fault Tolerance** | [app/discovery/service.py](file:///e:/SIH2026/OSINT/app/discovery/service.py), [app/acquisition/service.py](file:///e:/SIH2026/OSINT/app/acquisition/service.py) | A single failing item or timeout never aborts the overall batch execution. |
| **Correlation / Request ID Middleware** | [app/main.py](file:///e:/SIH2026/OSINT/app/main.py) | Attaches `X-Investigation-ID` to all logs and response headers for forensic auditability. |
| **Incremental Streaming Reader** | [app/acquisition/fetcher.py](file:///e:/SIH2026/OSINT/app/acquisition/fetcher.py) | Enforces memory quotas during byte consumption, preventing decompression or size bomb denial-of-service. |
| **Passive DOM Sanitization** | [app/extraction/parser.py](file:///e:/SIH2026/OSINT/app/extraction/parser.py) | Strips non-content and boilerplate elements before extracting text, ensuring zero script execution or external asset loading. |
| **Priority Fallback Chain** | [app/extraction/metadata.py](file:///e:/SIH2026/OSINT/app/extraction/metadata.py), [app/extraction/parser.py](file:///e:/SIH2026/OSINT/app/extraction/parser.py) | Hierarchical resolution of titles, descriptions, and content containers from highest semantic specificity to general fallbacks. |
| **Occurrence Aggregator & Deduplicator** | [app/entity_extraction/service.py](file:///e:/SIH2026/OSINT/app/entity_extraction/service.py) | Grouping individual mention spans into unique canonical entities while preserving occurrence spans and offsets. |
| **Deterministic Provenance Anchoring** | [app/entity_extraction/extractor.py](file:///e:/SIH2026/OSINT/app/entity_extraction/extractor.py), [app/entity_extraction/service.py](file:///e:/SIH2026/OSINT/app/entity_extraction/service.py) | Preserves `source_document_hash` and `source_url` on all extracted entities for evidentiary traceability. |

---

## 5. Looking Ahead: Future Phase Roadmap

When evolving this component toward upstream integration into S.I.R.I.S., the following phases will build upon this foundation:

1. **Phase 5 — Entity Extraction (NER)**: `[COMPLETED]`
   - Purpose: Extract identifiable entities (persons, organizations, locations, dates, times, money, phones, emails, URLs) with character offsets and provenance.
2. **Phase 6 — Entity Resolution / Target Matching**: `[NEXT RECOMMENDED PHASE]`
   - Purpose: Compare extracted candidate attributes against the investigation target using Jaro-Winkler, Levenshtein, and phonetic matching (Soundex, Double Metaphone) to compute identity confidence.
3. **Phase 7 — Relationship Extraction**:
   - Purpose: Link extracted entities to build subgraphs (e.g., `(Target)-[ASSOCIATED_WITH]->(Company)`).
4. **Phase 8 — Telegram Public OSINT**:
   - Purpose: Ingest public channel broadcasts and geolocated chat leads.
5. **Phase 9 — Cryptographic Evidence Vault**:
   - Purpose: Immutable chain-of-custody verification linking original SHA-256 hashes to case files.
6. **Phase 10 — S.I.R.I.S. Core Integration**:
   - Purpose: Stream resolved entities directly into the S.I.R.I.S. Central Intelligence FastAPI engine and Neo4j Knowledge Graph.

---

*Last Updated: September 2026 | S.I.R.I.S. OSINT Engineering Team*
