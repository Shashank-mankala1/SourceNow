# CivicSense – AI Copilot Against Misinformation

A complete, execution-ready plan: backlog (issues), architecture, API contracts, prompts, evaluation, and demo script. This will be our living build spec.

---
## 0) Guiding Principles
- **Trust first**: every verdict shows sources, dates, and confidence.
- **Explainability**: concise, cited rationales. No claims without evidence.
- **ToS-safe**: official platform APIs only; otherwise request direct upload.
- **Latency-aware**: progressive refinement (fast preview → high-quality re-run on demand).

---
## 1) User Stories (MVP)
1. *As a reader*, I paste a link or upload a file and get claim-by-claim verdicts with citations in <10s for short articles.
2. *As a moderator*, I upload a batch of URLs/files and export results as JSON/CSV with ClaimReview-style fields.
3. *As a journalist*, I can click a claim to jump to the exact timestamp in a video and see the supporting/contradicting sources.
4. *As any user*, I can mark a result as unhelpful and submit a suggested correction for retraining.

**Acceptance Criteria (MVP):**
- Supported inputs: text, PDF, image, video file, YouTube URL, Instagram public URL, direct .mp4 URL.
- Outputs include: verdict (Supported/Refuted/Unclear), confidence (0–1), 1–3 citations (title, publisher, date, URL), 3–5 sentence rationale, and for video claims: timestamps.
- End-to-end p95 latency ≤ 2.5s for text-only pages (with warm cache), ≤ 30s for a 2–3 min video.

---
## 2) High-Level Architecture
- **Client**: Browser Extension (Chrome MV3, React/TS) + Web App (Next.js + API routes as proxy)
- **API**: FastAPI service with Celery/Redis for async jobs
- **Pipelines**:
  - **Ingestion**: adapters normalize media (text, image, video, links) → unified representation
  - **Analysis**: claim detection → retrieval → verification → explanation
- **Storage**: Postgres (jobs, feedback), Vector DB (FAISS/Weaviate), S3/GCS (temporary media, frames)
- **Models**:
  - Whisper (ASR), Tesseract or PaddleOCR (OCR)
  - Claim Detector (DeBERTa/Longformer fine-tune)
  - Retriever (BM25 + dense embeddings)
  - Verifier (FEVER-style stance classifier)
  - LLM explainer (open weights or API)

**Data Flow:**
Client → `/ingest` → adapter (YouTube/Instagram/Text/Image/Video) → normalized doc → `/analyze` → pipeline → `/results`.

---
## 3) Repository Structure
```
CivicSense/
  README.md
  Makefile
  docker-compose.yml
  infra/ (IaC placeholders)
  api/
    app.py (FastAPI entry)
    routers/
      ingest.py
      analyze.py
      results.py
      feedback.py
    services/
      adapters/
        base.py
        text_adapter.py
        pdf_adapter.py
        image_adapter.py
        video_adapter.py
        youtube_adapter.py
        instagram_adapter.py
        generic_video_url_adapter.py
      asr/
        whisper_runner.py
      ocr/
        ocr_runner.py
      scene/
        scene_detect.py
      unify/
        builder.py  # merges transcript+OCR+captions
      claims/
        detector.py
      retrieve/
        retriever.py
      verify/
        verifier.py
      explain/
        explainer.py
      rank/
        ranker.py
    models/
      checkpoints/ (gitignored)
      configs/
        detector.yaml
        retriever.yaml
        verifier.yaml
      prompts/
        explanation_prompt.md
        safety_rules.md
    db/
      schema.sql
      migrations/
  web/
    extension/ (Chrome MV3 + React/TS)
    app/ (Next.js web dashboard)
  tests/
    unit/
    integration/
    e2e/
  scripts/
    download_wikipedia.sh
    prepare_fever.sh
    finetune_detector.py
    train_verifier.py
    eval_pipeline.py
```

---
## 4) API Contracts
### `POST /ingest`
**Body**: multipart file upload *or* JSON `{ "url": string, "typeHint": "youtube|instagram|video|image|text|auto" }`
**Resp**: `{ "ingest_id": string }`

### `POST /analyze`
**Body**: `{ "ingest_id": string, "mode": "fast|quality" }`
**Resp**: `{ "job_id": string }`

### `GET /status?job_id=...`
**Resp**: `{ "stage": "ingest|transcribe|ocr|claims|retrieve|verify|explain|done|error", "progress": 0-100, "message": string|null }`

### `GET /results?job_id=...`
**Resp**:
```
{
  "source": {"type": "video|image|text", "url": "...", "title": "...", "published_at": "..."},
  "claims": [
    {
      "id": "c_0001",
      "claim": "The deficit fell by $1.7T last year.",
      "verdict": "Supported|Refuted|Unclear",
      "confidence": 0.82,
      "timestamps": [{"start": 12.3, "end": 16.9}],
      "citations": [
        {"title": "...", "publisher": "...", "url": "...", "published_at": "2024-09-10", "tier": "A|B|C"}
      ],
      "why": "3–5 sentence rationale with [1][2] inline references"
    }
  ]
}
```

### `POST /feedback`
**Body**: `{ "job_id": "...", "claim_id": "...", "correct_verdict": "...", "notes": "..." }`
**Resp**: `{ "ok": true }`

---
## 5) Ingestion Adapters (Design + Stubs)

### `BaseAdapter`
- `detect(request) -> bool`
- `process(request) -> NormalizedPayload`
- Emits:
```
NormalizedPayload = {
  "type": "video|image|text",
  "text": "...",
  "segments": [{"start": float, "end": float, "text": "..."}],
  "frames": [{"ts": float, "uri": "s3://.../f.jpg", "ocr": "..."}],
  "meta": {"source": "youtube|instagram|upload|url", "url": "...", "title": "...", "published_at": "..."}
}
```

### Text/PDF/Image/VideoFile
- **Text**: pass-through; for PDF use PyMuPDF; for DOCX use mammoth.
- **Image**: run OCR; optional captioning; add `frames=[{ts:0, uri:..., ocr:...}]`.
- **VideoFile**: ffmpeg normalize (360p proxy), Whisper ASR, keyframe sampling (1 fps baseline), frame OCR.

### YouTube
- Use YouTube Data API for captions/metadata. If no captions, prompt for upload. Store title, channel, published date.

### Instagram (public)
- Use Meta Graph API where permitted; otherwise request direct upload. Capture caption/alt text when available.

### GenericVideoURL
- If direct `.mp4` etc., treat as VideoFile; otherwise request upload.

---
## 6) Analysis Pipeline

### Claim Detection
- Sentence segmentation, heuristic pre-filter (numbers, superlatives, NER).
- Model: DeBERTa/Longformer fine-tuned on FEVER/LIAR for check-worthiness.
- Output spans with confidence and (for video) timestamps.

### Retrieval (Hybrid)
- Tiered sources:
  - Tier A: fact-check publishers (IFCN), via ClaimReview / official APIs
  - Tier B: Wikipedia (+ referenced sources)
  - Tier C: gov/edu/NGO
- Algorithm: BM25 (Elasticsearch/Lucene) + dense embeddings (sentence-transformers). Rank by trust, recency, lexical match.

### Verification (Stance)
- FEVER-style verifier model (claim + top-k evidence → Supported/Refuted/NEI). Keep minimal sufficient evidence.

### Explanation Generation
- LLM prompt template (see §7). Hard-require citations; reject outputs lacking references. Limit verbatim quotes ≤20 words/source.

### Ranking + Finalization
- Rank by model confidence × source trust × recency decay; pick top 1–3 citations.

---
## 7) Prompt Templates (Initial)
**System:**
"""
You are an evidence-grounded assistant. For each claim, read the retrieved sources and produce:
- A verdict: Supported, Refuted, or Unclear.
- A 3–5 sentence explanation that quotes key phrases (≤20 words each) and includes [1], [2] inline citations.
Rules: do not invent facts; if evidence conflicts or is insufficient, say Unclear; always show caution on preliminary data; prefer Tier A sources.
"""

**User (example):**
```
CLAIM: "The deficit fell by $1.7T last year."
SOURCES:
[1] Title, Publisher, Date, URL, EXCERPT: "..."
[2] Title, Publisher, Date, URL, EXCERPT: "..."
OUTPUT FORMAT (JSON):
{
  "verdict": "Supported|Refuted|Unclear",
  "confidence": 0.xx,
  "why": "... with [1][2] ..."
}
```

**Guardrails:**
- If no sources: return `Unclear` and advise what evidence would be needed.
- If sources disagree: articulate the disagreement and choose Unclear unless one is clearly stronger (explain why).

---
## 8) Datasets & Preparation
- **FEVER**: claims + evidence for verifier.
- **LIAR**: political claims for claim detection.
- **MultiFC (optional)**: multi-domain fact-checks.
- Wikipedia dump for retrieval index; news/gov/edu crawl with robots-respectful tooling.

Scripts:
- `scripts/prepare_fever.sh` – download/split/train/dev/test
- `scripts/download_wikipedia.sh` – fetch + index
- `scripts/finetune_detector.py` – claim detector fine-tune
- `scripts/train_verifier.py` – stance model training

---
## 9) Evaluation Plan
**Offline**
- FEVER score (label + evidence correctness) on held-out.
- Precision@k (citations correct & relevant) by human raters.
- Rationale helpfulness (Likert 1–5), hallucination rate (<2% target).

**Online**
- p95 latency per media type, coverage (% items with at least one detected claim), click-through to sources, feedback rate.

Error Analysis Checklist:
- Mis-detected numerical claims; ambiguous timeframes; outdated sources outranking recency; confounded negations.

---
## 10) Security, Privacy, Compliance
- Store only derived text/frames by default; opt-in to keep originals.
- Signed URLs with short TTL for previews.
- Hash-identify identical URLs to avoid reprocessing.
- Respect platform ToS; no scraping of gated/private content.

---
## 11) Backlog (Issue List)
**Sprint 0 – Setup**
- [ ] Repo, CI/CD, pre-commit hooks, black/isort/mypy
- [ ] FastAPI skeleton + health endpoints
- [ ] Postgres schema + migrations (jobs, claims, citations, feedback)
- [ ] Redis/Celery worker scaffold
- [ ] S3/GCS client utility

**Sprint 1 – Ingestion Adapters**
- [ ] TextAdapter (paste, .txt)
- [ ] PDFAdapter (PyMuPDF)
- [ ] ImageAdapter (OCR + optional caption)
- [ ] VideoFileAdapter (ffmpeg proxy, Whisper, frames, OCR)
- [ ] YouTubeAdapter (captions+meta via official API)
- [ ] InstagramAdapter (Meta Graph API; fallback prompt to upload)
- [ ] GenericVideoURLAdapter
- [ ] Unified payload builder

**Sprint 2 – Claims & Retrieval**
- [ ] Sentence segmentation + heuristic prefilter
- [ ] ClaimDetector (baseline; FEVER/LIAR fine-tune later)
- [ ] Elasticsearch BM25 index + sentence-transformers embeddings
- [ ] ClaimReview/Fact-check API integration (normalize publishers)
- [ ] Ranker (trust × recency × match)

**Sprint 3 – Verification & Explanation**
- [ ] Verifier model (FEVER baseline)
- [ ] Explainer with strict citation validation
- [ ] Finalizer (pick top citations, assemble output)

**Sprint 4 – Frontend (Extension & Web)**
- [ ] Upload & URL input UI
- [ ] Results list with verdict chips and citations
- [ ] Video player with claim markers + seek
- [ ] Export JSON/CSV + shareable HTML report
- [ ] Feedback UI (correct verdict, notes)

**Sprint 5 – Quality & Eval**
- [ ] Caching, warm indexes, parallelization
- [ ] Offline eval scripts (FEVER, P@k)
- [ ] Telemetry dashboards (latency, coverage)
- [ ] Error states & retries

**Sprint 6 – Polish & Demo**
- [ ] Guided tour in UI
- [ ] One-click ClaimReview JSON export
- [ ] 90-sec demo video script & recording

---
## 12) Environment & Tooling
- Python 3.11, Poetry/uv for deps
- Node 20, pnpm for web
- Docker for all services; compose for local dev
- Make targets:
```
make dev-up        # start stack
make api-test      # run API tests
make index-wiki    # build retrieval index
make train-det     # train claim detector
make train-ver     # train verifier
make eval          # offline eval suite
```

---
## 13) Demo Script (90s)
1. Paste a news URL → "Analyze" → detection highlights 2–3 claims.
2. Click a claim → verdict chip + concise rationale with 2 citations.
3. Upload a 60s video → markers on timeline → jump to moment; see verdict and sources.
4. Export JSON (ClaimReview-style) → show how a newsroom could embed the result.

---
## 14) Risks & Mitigations
- **Sparse fact-check coverage** → robust general retrieval + NEI (Unclear) fallback.
- **Hallucinations** → hard require citations; quote-length caps; output validator.
- **Latency** → proxy video, adaptive frame sampling, caching, async pipeline.
- **Platform API limits** → exponential backoff; queue; request direct uploads on quota exhaustion.

---
## 15) Next Steps (You + Me)
1. Confirm this spec (add/remove items).
2. I’ll generate initial code stubs for adapters, pipeline services, and API routers.
3. We run `make dev-up` and push the hello-world ingestion → claim detection path.

