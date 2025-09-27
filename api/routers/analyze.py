from fastapi import APIRouter, HTTPException
from typing import List, Tuple
from api.core.store import STORE
from api.models.schemas import AnalyzeRequest, StatusResponse, ResultsResponse, ClaimResult, Timestamp
import re
import requests
from typing import Optional
import nltk
import os
from api.services.factchecker import search_fact_checks, flatten_claimreviews

TIER_WEIGHT = {"A": 3, "B": 2, "C": 1}

def _build_citations_for_claim(claim_text: str) -> list[dict]:
    citations: list[dict] = []

    # Tier A: Fact checks
    api_key = os.getenv("GOOGLE_FACTCHECK_API_KEY", "")
    fc_claims = search_fact_checks(claim_text, api_key)
    citations.extend(flatten_claimreviews(fc_claims))

    # Tier B/C: Wikipedia (your existing retrieval uses _extract_query + _rank_titles)
    citations.extend(_citation_from_wiki(claim_text))  # keep your current function

    # Dedup by URL, prefer higher tier
    best_by_url: dict[str, dict] = {}
    TIER_WEIGHT = {"A": 3, "B": 2, "C": 1}
    for c in citations:
        url = (c.get("url") or "").strip()
        if not url:
            continue
        prev = best_by_url.get(url)
        if not prev or TIER_WEIGHT[c["tier"]] > TIER_WEIGHT[prev["tier"]]:
            best_by_url[url] = c
    citations = list(best_by_url.values())

    # --- NEW: Sort Tier-A by recency and publisher preference ---
    PREF_PUBS = {"AP", "Associated Press", "Reuters", "PolitiFact", "Full Fact", "AFP", "Science Feedback", "Snopes"}

    def sort_key(c):
        rd = (c.get("metadata") or {}).get("reviewDate") or ""
        pref = 1 if c.get("publisher") in PREF_PUBS else 0
        return (c["tier"], rd, pref)

    tierA = [c for c in citations if c["tier"] == "A"]
    tierBplus = [c for c in citations if c["tier"] != "A"]
    tierA.sort(key=sort_key, reverse=True)
    citations = tierA + tierBplus

    return citations



# download small models on first run (cached afterward)
for pkg in ["punkt", "averaged_perceptron_tagger", "maxent_ne_chunker", "words"]:
    try:
        nltk.data.find(f"tokenizers/{pkg}") if "punkt" in pkg else nltk.data.find(f"corpora/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)

WIKI_SEARCH_API = "https://en.wikipedia.org/w/api.php"
WIKI_HEADERS = {"User-Agent": "SourceNow/0.1 (contact: you@example.com)"}

from typing import Optional, List

def _rank_titles(query: str, titles: List[str]) -> Optional[str]:
    if not titles:
        return None
    q = _clean_leading_article(query).lower()

    def score(title: str):
        t = title.lower()

        exact   = 1 if t == q else 0
        starts  = 1 if t.startswith(q) else 0
        contain = sum(1 for tok in re.split(r"\W+", q) if len(tok) >= 3 and tok in t)

        penalty = 0
        if t.startswith("list of"):
            penalty -= 3
        if "(disambiguation)" in t:
            penalty -= 3
        if t.startswith("source of"):
            penalty -= 3                     # <-- fixes Amazon case
        if re.search(r"\bin\b\s+[A-Z]", title) and not re.search(r"\bin\b\s+[A-Z]", query, flags=re.I):
            penalty -= 2                     # <-- de-prioritize country-specific
        length_penalty = -min(len(title), 80) / 200.0  # slightly prefer shorter

        return (exact, starts, contain, penalty, -length_penalty)

    return sorted(titles, key=score, reverse=True)[0]


def _wiki_page_url(title: str) -> str:
    return f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

def _wiki_search_title(query: str) -> Optional[str]:
    """
    Ask Wikipedia for up to 5 results (with proper headers) and pick the best match.
    """
    try:
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 5,
            "format": "json",
        }
        r = requests.get(WIKI_SEARCH_API, params=params, headers=WIKI_HEADERS, timeout=8)  # <-- headers added
        r.raise_for_status()
        data = r.json()
        hits = [h.get("title","") for h in data.get("query", {}).get("search", []) if h.get("title")]
        return _rank_titles(query, hits)
    except Exception as e:
        print(f"[wiki] search failed for query='{query}': {e}")
        return None


ARTICLES = {"the", "a", "an"}

def _clean_leading_article(s: str) -> str:
    parts = s.strip().split(" ", 1)
    if parts and parts[0].lower() in ARTICLES and len(parts) > 1:
        return parts[1]
    return s.strip()

def _extract_query(sent: str) -> str:
    s = sent.strip()

    # Canonical patterns first (handles your COVID sentence)
    if re.search(r"\bCOVID-19\b", s, flags=re.I) and re.search(r"\bpandemic\b", s, flags=re.I):
        return "COVID-19 pandemic"

    # Exact phrases if present (cleaned to remove leading articles)
    for phrase in ["Amazon River", "Mount Everest", "Eiffel Tower", "Albert Einstein"]:
        if re.search(re.escape(phrase), s, flags=re.I):
            return _clean_leading_article(phrase)

    # NLTK NE chunks / proper nouns (if models are available)
    try:
        import nltk
        tokens = nltk.word_tokenize(s)
        pos = nltk.pos_tag(tokens)
        tree = nltk.ne_chunk(pos, binary=False)
        for subtree in tree:
            if hasattr(subtree, "label") and subtree.label() in {"PERSON","ORGANIZATION","GPE","LOCATION","FACILITY","EVENT"}:
                ent = " ".join(tok for tok, _ in subtree.leaves())
                if ent and ent[0].isupper():
                    return _clean_leading_article(ent)
        proper = []
        for w, t in pos:
            if t in {"NNP","NNPS"} and w and w[0].isupper():
                proper.append(w)
            elif proper:
                break
        if proper:
            return _clean_leading_article(" ".join(proper)[:80])
    except Exception:
        pass

    # Regex fallback: 1–4 Capitalized tokens, then strip leading article
    m = re.search(r"[A-Z][A-Za-z0-9\-]*(?:\s+[A-Z][A-Za-z0-9\-]*){0,3}", s)
    if m:
        return _clean_leading_article(m.group(0))

    return _clean_leading_article(s[:80])



def _citation_from_wiki(sent: str):
    query = _extract_query(sent)
    print(f"[wiki] claim='{sent}' | query='{query}'")  # debug to verify we’re not sending full sentences
    title = _wiki_search_title(query)
    if title:
        print(f"[wiki] matched title='{title}'")        # debug
        return {
            "title": title,
            "publisher": "Wikipedia",
            "url": _wiki_page_url(title),
            "published_at": None,
            "tier": "B",
        }
    # Graceful fallback: give a search link instead of []
    from requests.utils import quote
    return {
        "title": f"Search: {query}",
        "publisher": "Wikipedia (search)",
        "url": f"https://en.wikipedia.org/w/index.php?search={quote(query)}",
        "published_at": None,
        "tier": "C",
    }

router = APIRouter(prefix="", tags=["analyze"])


@router.post("/analyze")
def analyze(req: AnalyzeRequest):
    if req.ingest_id not in STORE.ingests:
        raise HTTPException(status_code=404, detail="ingest_id not found")
    job_id = STORE.new_job(req.ingest_id)
    # For the toy version we run synchronously and return results immediately
    job = STORE.jobs[job_id]
    job.stage = "claims"; job.progress = 50


    text = STORE.ingests[req.ingest_id].text
    claims = _detect_claims(text)
    job.stage = "done"; job.progress = 100


    results = {
        "source": {"type": "text", "url": None, "title": None, "published_at": None},
        "claims": []
    }

    for i, sent in enumerate(claims):
        citation = _build_citations_for_claim(sent)  # new
        results["claims"].append(
            ClaimResult(
                id=f"c_{i:04d}",
                claim=sent,
                verdict="Unclear",
                confidence=0.50,
                timestamps=[],
                citations=[citation] if citation else [],
                why="Prototype: claims detected by heuristic; retrieval (Wikipedia) attached; verification not yet applied."
            ).dict()
        )
    results = []
    for i, claim in enumerate(claims):
        claim_text = claim["text"] if isinstance(claim, dict) else str(claim)

        citations = _build_citations_for_claim(claim_text)  # <-- NEW

        results.append({
            "id": f"c_{i:04d}",
            "claim": claim_text,
            "verdict": "Unclear",                  # verifier comes later
            "confidence": 0.5,                     # your current placeholder
            "timestamps": [],                      # if you don’t do timestamps yet
            "citations": citations,                # <-- now includes Tier-A first
            "why": "Prototype: heuristic detection; Tier-A fact-checks (if found), then Wikipedia."
        })

    job.results = results
    return {"job_id": job_id}

@router.get("/status", response_model=StatusResponse)
def status(job_id: str):
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    return {"stage": job.stage, "progress": job.progress, "message": job.message}


@router.get("/results", response_model=ResultsResponse)
def results(job_id: str):
    job = STORE.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job_id not found")
    if job.stage != "done" or not job.results:
        raise HTTPException(status_code=202, detail="job not complete yet")
    return job.results



# --- utilities ---
_SUPERLATIVES = r"(?:largest|smallest|first|only|record|lowest|highest|never|always)"
_NUM_PATTERN = r"\b\$?\d+(?:[\.,]\d+)?(?:%|\s*(?:million|billion|trillion|k|m|bn|tn))?\b"


def _split_sentences(text: str) -> List[str]:
# naive splitter; we will swap for a real segmenter later
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]

def _is_check_worthy(sent: str) -> bool:
    return bool(re.search(_NUM_PATTERN, sent, flags=re.I) or re.search(_SUPERLATIVES, sent, flags=re.I))

def _detect_claims(text: str) -> List[str]:
    sents = _split_sentences(text)
    return [s for s in sents if _is_check_worthy(s)]