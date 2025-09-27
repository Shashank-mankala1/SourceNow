Awesome choice. Here’s a complete, end-to-end plan for **CivicSense – AI Copilot Against Misinformation** that you can execute, demo, and ship.

# 1) Problem, users, scope

**Problem**
People encounter questionable claims in posts/articles/videos and have no quick, trustworthy way to (a) check them, (b) see evidence, and (c) understand *why* a claim is likely true/false/inconclusive.

**Primary users**

* Everyday readers (browser extension)
* Community moderators / journalists (web app dashboard)

**Goals (MVP)**

* Highlight claims in-page and classify: **Supported / Refuted / Unclear**
* Show **evidence with citations** (trusted sources + fact-checks)
* Generate a **brief, source-backed explanation**
* Be transparent about uncertainty and source provenance (IFCN-aligned). ([ifcncodeofprinciples.poynter.org][1])

**Non-goals (MVP)**

* Broad stance on *opinions* / satire (focus on factual claims)
* Full social network integration (start with on-page analysis via extension)

---

# 2) Architecture at a glance

**Client (browser extension + web app)**

* Claim highlighter: detects candidate claims on any page
* Tooltip panel: verdict + confidence + top 3 sources
* “Why?” tab: short explanation, links
* “Disagree?” button: collect feedback

**API layer (FastAPI)**

* `/analyze` → orchestrates pipeline
* `/feedback` → stores corrections/rationales

**Pipeline (server)**

1. **Claim detection** (NLP): extract check-worthy sentences
2. **Entity/linking**: normalize names, dates, numbers
3. **Evidence retrieval** (RAG):

   * **Fact-check APIs** (Google Fact Check Tools → ClaimReview) ([Google for Developers][2])
   * High-quality sources (Wikipedia, gov/edu)
4. **Verification model**: classify (Supported / Refuted / NEI) using retrieval + verifier (FEVER-style) ([arXiv][3])
5. **Explanation generator**: LLM turns evidence into 3–5 sentence rationale with inline citations
6. **Safety & transparency**: show confidence, source badges (IFCN signatories, major outlets) ([Reuters][4])

**Storage**

* Vector DB (e.g., Weaviate/FAISS) for retrieved passages
* Postgres for telemetry/feedback
* Object store for cached pages/transcripts

---

# 3) Tech stack

* **Language/Runtime:** Python 3.11, Node/TS for extension
* **NLP/LLM:** Open-source LLM (Llama 3.x) or API; sentence-transformers for embeddings
* **Claim detection:** fine-tuned DeBERTa/Longformer (sequence classification)
* **Retriever:** BM25 + dense hybrid over curated indexes (Wikipedia dump + news/Gov)
* **Verifier:** FEVER-style pipeline (retrieve → select evidence → stance) ([arXiv][3])
* **Fact-check integration:** **Google Fact Check Tools API** (surfacing **ClaimReview** data) ([Google for Developers][2])
* **Schema/interop:** **schema.org/ClaimReview** for standardized outputs ([Schema.org][5])
* **Datasets (training/eval):** **FEVER**, **LIAR** (+ MultiFC optional) ([fever.ai][6])
* **Backend:** FastAPI, Celery (async), Redis (queues)
* **DB:** Postgres, FAISS/Weaviate
* **Frontend:** Browser Extension (MV3, React/TS), Web app (Next.js)
* **Infra:** Docker, Terraform, Cloud (GCP/AWS)

---

# 4) Data & sources (trust first)

**Tier A (highest trust):** IFCN signatories (Reuters Fact Check, WaPo Fact Checker, etc.) via ClaimReview or direct sites ([Reuters][4])
**Tier B:** Wikipedia + cited references
**Tier C:** Government/NGO (.gov/.int), academic (.edu)
**Presentation:** show tier badges; prefer Tier A when available.

---

# 5) Core pipeline design (detailed)

1. **Claim detection**

   * Heuristics + ML: detect “check-worthy” patterns (numbers, superlatives, biomedical/geo entities).
   * Train on LIAR/FEVER claims; output spans with confidence. ([arXiv][7])

2. **Entity resolution**

   * Use spaCy + custom rules for dates, quantities, named entities; normalize (e.g., “3M”→3,000,000; “last year”→YYYY).

3. **Evidence retrieval**

   * **Step 1:** Query **Google Fact Check Tools API** with the normalized claim → get existing fact checks (verdict + publisher). ([Google for Developers][2])
   * **Step 2:** If none, run hybrid retrieval over curated corpora; keep top-k passages + metadata.
   * **Step 3:** Rank by source trust + recency + lexical match.

4. **Verification (stance classification)**

   * FEVER-style: concatenate claim + candidate evidence; predict Supported/Refuted/NEI; keep minimal sufficient evidence set. ([arXiv][3])

5. **Explanation generation**

   * Prompt LLM with: *claim, evidence quotes, sources, confidence, caveats*.
   * Require **inline citations** (\[1], \[2]) and **verbatim quotes ≤20 words** per source to reduce hallucinations.

6. **Output formatting**

   * Return **ClaimReview-like JSON** (verdict, date, url, evidence). This makes CivicSense interop-friendly and future-proof. ([Schema.org][5])

---

# 6) Product surfaces

**A) Browser extension (killer demo)**

* Click “Check this” → highlights candidate claim(s) → verdict chip + confidence
* “Why?” panel with 3 concise bullets + citations
* “Read the source” → open fact-check or Wikipedia/reuters link
* “Report issue” → sends feedback (stores misfires for retraining)

**B) Web dashboard (for moderators/journalists)**

* Bulk URL / file upload (article, transcript, PDF)
* Batch results, filter by verdict/type/confidence
* Export **ClaimReview** markup to embed in your own article (nice bonus) ([Google for Developers][8])

---

# 7) Evaluation & metrics

**Offline (benchmarks)**

* **FEVER score** (label + evidence correctness)
* **Precision\@k** of citations
* **Rationales quality**: human rating (1–5) on helpfulness/clarity
* **Hallucination rate**: percentage of claims with unsupported statements

**Online (product)**

* Time-to-verdict latency (p95 < 2.5s with cache)
* User actions: clicks on sources, “helpful” votes, corrections submitted
* Coverage: % pages with ≥1 claim detected

---

# 8) Privacy, safety, ethics

* Prioritize trustworthy sources and display **publisher + date** for every citation.
* Adhere to **IFCN principles**: nonpartisanship, fairness, transparency, corrections. ([ifcncodeofprinciples.poynter.org][1])
* Clear **limitations** label on each verdict; avoid adjudicating opinions.
* Respect site TOS; process locally when possible; cache responsibly.

---

# 9) Timeline (6 weeks to impressive demo)

**Week 1 — Foundations**

* Set repo, CI, FastAPI skeleton, extension boilerplate
* Import FEVER + LIAR; build simple claim detector; baseline BM25 retriever ([fever.ai][6])

**Week 2 — Evidence & Fact-Checks**

* Stand up vector DB; hybrid retrieval
* Integrate **Google Fact Check Tools API**; map publishers + ratings (Pinocchios, Truth/O-Meter → normalized scale) ([Google for Developers][2])

**Week 3 — Verifier & Explanations**

* Train a FEVER-style stance classifier; add minimal-evidence selection
* LLM explanation templates with strict citation rules

**Week 4 — Extension + UI**

* On-page highlighting; verdict chips; “Why?” panel
* Feedback capture + analytics

**Week 5 — Quality & Trust**

* Ranking by trust tiers; add recency decay
* Guardrails: quote-length limit, citation presence checks
* Offline eval: FEVER score, P\@k, hallucination rate

**Week 6 — Polish & Demo**

* Caching, latency tuning, error states
* “Export ClaimReview JSON” in dashboard (publishers can embed) ([Google for Developers][8])
* Record a 90-sec product video

---

# 10) Deliverables

* **Browser extension** (Chrome MV3) + **FastAPI** service (Dockerized)
* **Verification pipeline** (retriever, verifier, explainer) with tests
* **ClaimReview JSON exporter** and minimal docs ([Schema.org][5])
* **Eval report** (metrics, ablations, error analysis)
* **Demo script & video**

---

# 11) Stretch goals (post-MVP)

* **YouTube/TikTok**: auto-transcribe and fact-check key spoken claims (Whisper + transcript RAG)
* **Multilingual**: add cross-lingual retrieval; localize UI
* **Crowd signals**: show when multiple IFCN signatories have checked a claim (consensus) ([Reuters][4])
* **Publisher mode**: one-click generate **ClaimReview markup** for your own fact checks ([Google for Developers][8])

---

# 12) Risks & mitigations

* **Sparse fact-check coverage** → robust general retrieval + verifier, and show “Unclear” vs overconfident calls.
* **Hallucinations** → hard require citations; block unsupported statements; cap quote length.
* **Latency** → cache page text, prefetch Wikipedia, compress models.
* **Content policy/TOS** → analyze page DOM locally; use official APIs.

---

If this plan looks close to your vision, I’ll turn it into a **task-by-task backlog** (issues), pick exact models, craft prompts, and outline the **demo script**. Want me to proceed with that?

[1]: https://ifcncodeofprinciples.poynter.org/the-commitments?utm_source=chatgpt.com "The commitments of the Code of Principles - Poynter Institute"
[2]: https://developers.google.com/fact-check/tools/api/?utm_source=chatgpt.com "Fact Check Tools API | Google for Developers"
[3]: https://arxiv.org/abs/1803.05355?utm_source=chatgpt.com "FEVER: a large-scale dataset for Fact Extraction and VERification"
[4]: https://www.reuters.com/fact-check/about/?utm_source=chatgpt.com "About Reuters Fact Check"
[5]: https://schema.org/ClaimReview?utm_source=chatgpt.com "ClaimReview - Schema.org Type"
[6]: https://fever.ai/dataset/fever.html?utm_source=chatgpt.com "FEVER Dataset"
[7]: https://arxiv.org/abs/1705.00648?utm_source=chatgpt.com "\"Liar, Liar Pants on Fire\": A New Benchmark Dataset for Fake News Detection"
[8]: https://developers.google.com/search/docs/appearance/structured-data/factcheck?utm_source=chatgpt.com "Fact Check (ClaimReview) Markup for Search - Google Developers"
