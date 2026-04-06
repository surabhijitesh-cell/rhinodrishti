"""
Elite Web Scraper — BS4 + httpx scraper for sites without proper RSS feeds.
Used for grassroots/regional outlets and security research portals.
"""
import httpx
import logging
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import uuid

logger = logging.getLogger(__name__)

# Sites to scrape (no usable RSS feed)
SCRAPE_TARGETS = [
    {
        "name": "SATP",
        "url": "https://www.satp.org/terrorism-assessment/india-northeast",
        "category": "security_research",
        "region": "NER",
        "selectors": {"articles": "div.assessment-content a, div.news-item a, table.news-table a"},
        "priority": "high",
    },
    {
        "name": "Ukhrul Times",
        "url": "https://ukhrultimes.com/",
        "category": "regional",
        "region": "NER",
        "selectors": {"articles": "h2.entry-title a, h3.entry-title a, article a[rel='bookmark']"},
        "priority": "high",
    },
    {
        "name": "Frontier Myanmar",
        "url": "https://www.frontiermyanmar.net/en/",
        "category": "cross_border",
        "region": "Myanmar",
        "selectors": {"articles": "h2 a, h3 a, .post-title a, article a"},
        "priority": "high",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def scrape_site(target: dict) -> list:
    """Scrape a single site for article links and titles."""
    articles = []
    url = target["url"]
    name = target["name"]
    
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            selector = target["selectors"]["articles"]
            links = soup.select(selector)
            
            seen_urls = set()
            for link in links[:20]:
                href = link.get("href", "")
                text = link.get_text(strip=True)
                
                if not href or not text or len(text) < 15:
                    continue
                
                # Normalize URL
                if href.startswith("/"):
                    from urllib.parse import urljoin
                    href = urljoin(url, href)
                
                if href in seen_urls or not href.startswith("http"):
                    continue
                seen_urls.add(href)
                
                articles.append({
                    "id": str(uuid.uuid4()),
                    "title": text[:300],
                    "source": name,
                    "source_url": href,
                    "region": target.get("region", "NER"),
                    "category": target.get("category", "regional"),
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "raw_content": "",
                    "scrape_source": True,
                })
            
            logger.info(f"Scraped {len(articles)} articles from {name}")
    except Exception as e:
        logger.warning(f"Scrape failed for {name}: {e}")
    
    return articles


async def scrape_article_content(url: str) -> str:
    """Fetch and extract main text content from an article URL."""
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=HEADERS)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, "html.parser")
            
            # Remove script, style, nav elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()
            
            # Try common content selectors
            content = ""
            for selector in ["article", ".entry-content", ".post-content", ".article-body", "main", ".content"]:
                el = soup.select_one(selector)
                if el:
                    content = el.get_text(separator=" ", strip=True)
                    break
            
            if not content:
                # Fallback: largest text block
                paragraphs = soup.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
            
            # Clean up
            content = re.sub(r'\s+', ' ', content).strip()
            return content[:5000]
    except Exception as e:
        logger.warning(f"Content scrape failed for {url}: {e}")
        return ""


async def scrape_all_targets() -> list:
    """Scrape all configured targets."""
    all_articles = []
    for target in SCRAPE_TARGETS:
        articles = await scrape_site(target)
        all_articles.extend(articles)
    
    logger.info(f"Total scraped from {len(SCRAPE_TARGETS)} sites: {len(all_articles)} articles")
    return all_articles
