#!/usr/bin/env python3
import os
import time
import pickle
import httpx
from datetime import datetime
from urllib.parse import quote
from typing import Dict, Optional
from bs4 import BeautifulSoup
from faker import Faker

faker = Faker()

# Cache directory
CACHE_DIR = "search_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

def generate_headers() -> Dict[str, str]:
    """Generate random headers for HTTP requests."""
    return {
        "User-Agent": faker.user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "en-US,en;q=0.9,id-ID;q=0.8",
        "X-Forwarded-For": faker.ipv4_public(),
        "Connection": "keep-alive"
    }

def get_cache_key(query: str) -> str:
    """Generate a unique cache key for the query."""
    return str(hash(query))

def load_from_cache(cache_key: str) -> Optional[Dict]:
    """Load cached search results if available and not expired (24 hours)."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    try:
        if os.path.exists(cache_file):
            with open(cache_file, "rb") as f:
                cached = pickle.load(f)
            fetched_at = cached["searchParameters"].get("fetched_at")
            if isinstance(fetched_at, str):
                fetched_at = datetime.fromisoformat(fetched_at)
            if (datetime.now() - fetched_at).total_seconds() < 24 * 3600:
                return cached
    except Exception:
        pass
    return None

def save_to_cache(cache_key: str, data: Dict) -> None:
    """Save search results to cache."""
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.pkl")
    try:
        data["searchParameters"]["fetched_at"] = data["searchParameters"]["fetched_at"].isoformat()
        with open(cache_file, "wb") as f:
            pickle.dump(data, f)
    except Exception:
        pass

def clean_text(text: str) -> str:
    """Clean and normalize text by removing extra spaces."""
    return ' '.join(text.strip().split()) if text else ""

def fetch_search_page(url: str, headers: Dict[str, str]) -> httpx.Response:
    """Fetch search page with basic error handling."""
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            response = client.get(url)
            response.raise_for_status()
            return response
    except httpx.HTTPError as e:
        raise

def brave_search(query: str, limit: int = 10, filter_domain: Optional[str] = None) -> Dict:
    """Perform a search using Brave search engine in Serper-like format."""
    cache_key = get_cache_key(query)
    if cached_result := load_from_cache(cache_key):
        return cached_result

    headers = generate_headers()
    encoded_query = quote(query)
    url = f"https://search.brave.com/search?q={encoded_query}"
    start = time.time()

    try:
        response = fetch_search_page(url, headers)
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "searchParameters": {
                "query": query,
                "engine": "brave",
                "gl": "id",
                "hl": "id-id",
                "type": "search",
                "fetched_at": datetime.now().isoformat(),
                "latency_ms": int((time.time() - start) * 1000)
            },
            "organic_results": [],
            "debug": {
                "user_agent": headers["User-Agent"],
                "ip": headers["X-Forwarded-For"],
                "result_count": 0
            }
        }

    organic_results = []
    for item in soup.find_all("div", class_=["snippet", "news-snippet", "video-snippet", "card"]):
        if len(organic_results) >= limit:
            break

        a_tag = item.find("a", href=True)
        if not a_tag or not a_tag['href'].startswith(("http://", "https://")):
            continue

        result_url = a_tag['href']
        if filter_domain and filter_domain not in result_url:
            continue

        title_elem = item.find("div", class_=["title", "snippet-title"]) or a_tag
        title = clean_text(title_elem.get_text(strip=True)) if title_elem else ""
        snippet_elem = item.find("div", class_=["snippet-content", "description", "snippet-description"])
        snippet = clean_text(snippet_elem.get_text(strip=True)) if snippet_elem else clean_text(item.get_text(separator=' ', strip=True))

        # Extract date from element with class 'age' or similar
        date_elem = item.find("span", class_=["age", "date", "time", "snippet-age"])
        date = clean_text(date_elem.get_text(strip=True)) if date_elem else None

        if len(snippet) < 30 or len(title) < 5:
            continue

        result = {
            "position": len(organic_results) + 1,
            "title": title,
            "link": result_url,
            "snippet": snippet,
            "domain": result_url.split("/")[2]
        }
        if date:
            result["date"] = date

        organic_results.append(result)

    result_data = {
        "status": "success",
        "searchParameters": {
            "query": query,
            "engine": "brave",
            "gl": "id",
            "hl": "id-id",
            "type": "search",
            "fetched_at": datetime.now(),
            "latency_ms": int((time.time() - start) * 1000)
        },
        "organic_results": organic_results,
        "debug": {
            "user_agent": headers["User-Agent"],
            "ip": headers["X-Forwarded-For"],
            "result_count": len(organic_results)
        }
    }

    save_to_cache(cache_key, result_data)
    return result_data
