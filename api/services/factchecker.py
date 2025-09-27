# api/services/factcheck.py
from typing import List, Dict, Any
import requests

ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

def search_fact_checks(query: str, api_key: str, lang: str = "en", page_size: int = 5) -> List[Dict[str, Any]]:
    if not api_key:
        return []
    params = {"query": query, "languageCode": lang, "pageSize": page_size, "key": api_key}
    try:
        r = requests.get(ENDPOINT, params=params, timeout=8)
        r.raise_for_status()
        return r.json().get("claims", []) or []
    except Exception:
        return []

def flatten_claimreviews(fc_claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for c in fc_claims:
        for cr in (c.get("claimReview") or []):
            publisher = (cr.get("publisher") or {}).get("name") or "Fact-checker"
            url = cr.get("url")
            title = cr.get("title") or c.get("text") or "Fact-check"
            rating = (cr.get("textualRating") or "").strip()
            if url:
                out.append({
                    "title": title,
                    "url": url,
                    "publisher": publisher,
                    "tier": "A",  # Tier-A outranks Wikipedia
                    "metadata": {"rating": rating, "claimReviewed": c.get("text"),  "reviewDate": cr.get("reviewDate")}
                })
    return out
