import requests
from bs4 import BeautifulSoup
import argparse
import json
from urllib.parse import urlparse
from rich import print

def clean_text(text):
    return ' '.join(text.strip().split())

def scrape_manual(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }

    res = requests.get(url, headers=headers, timeout=15)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")

    article = soup.find("article")
    if not article:
        article = soup.find("main")
    if not article:
        article = soup.body  # fallback

    title = soup.title.string.strip() if soup.title else "(no title)"
    paragraphs = article.find_all(["p", "h2", "h3"])
    content = "\n".join(clean_text(p.get_text()) for p in paragraphs if p.get_text().strip())

    return {
        "title": title,
        "content": content,
        "source": url,
        "domain": urlparse(url).netloc
    }

