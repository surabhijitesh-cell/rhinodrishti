"""
Twitter/X Scraper for Defense Accounts
Fetches recent tweets from Indian military and government defense accounts
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Dict
import uuid

logger = logging.getLogger(__name__)

# Defense accounts to monitor
DEFENSE_ACCOUNTS = [
    "adgpi",           # ADG PI - Indian Army
    "IAF_MCC",         # Indian Air Force
    "indiannavy",      # Indian Navy
    "easterncomd",     # Eastern Command
    "DefenceMinIndia", # Ministry of Defence
    "MEAIndia",        # Ministry of External Affairs
    "HMOIndia",        # Home Ministry
    "BSF_India",       # Border Security Force
    "official_dgar",   # Assam Rifles
    "ABORAITBP",       # ITBP
]

ACCOUNT_NAMES = {
    "adgpi": "ADG PI - Indian Army",
    "IAF_MCC": "Indian Air Force",
    "indiannavy": "Indian Navy",
    "easterncomd": "Eastern Command - Indian Army",
    "DefenceMinIndia": "Ministry of Defence",
    "MEAIndia": "Ministry of External Affairs",
    "HMOIndia": "Home Ministry",
    "PMOIndia": "Prime Minister's Office",
    "BSF_India": "Border Security Force",
    "crpf_india": "CRPF",
    "official_dgar": "Assam Rifles",
    "ITBP_official": "ITBP",
}


def scrape_tweets_sync(username: str, max_tweets: int = 5) -> List[Dict]:
    """Synchronously scrape tweets from a Twitter account using ntscraper"""
    tweets = []
    
    try:
        from ntscraper import Nitter
        
        # Try multiple Nitter instances (public instances that mirror Twitter)
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.privacydev.net",
            "https://nitter.poast.org",
            "https://nitter.1d4.us",
        ]
        
        scraper = None
        for instance in nitter_instances:
            try:
                scraper = Nitter(instance=instance)
                break
            except Exception:
                continue
        
        if not scraper:
            logger.warning(f"Could not connect to any Nitter instance for @{username}")
            return tweets
        
        # Get tweets
        try:
            results = scraper.get_tweets(username, mode='user', number=max_tweets)
            
            if results and 'tweets' in results:
                for tweet_data in results['tweets'][:max_tweets]:
                    tweet = {
                        "id": str(uuid.uuid4()),
                        "handle": f"@{username}",
                        "account_name": ACCOUNT_NAMES.get(username, username),
                        "tweet_text": tweet_data.get('text', ''),
                        "tweet_url": f"https://twitter.com/{username}/status/{tweet_data.get('link', '').split('/')[-1]}" if tweet_data.get('link') else "",
                        "posted_at": tweet_data.get('date', datetime.now(timezone.utc).isoformat()),
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "category": "defense" if username in ["adgpi", "IAF_MCC", "indiannavy", "easterncomd"] else "government",
                        "likes": tweet_data.get('stats', {}).get('likes', 0),
                        "retweets": tweet_data.get('stats', {}).get('retweets', 0),
                        "is_relevant": True
                    }
                    tweets.append(tweet)
                    
            logger.info(f"Scraped {len(tweets)} tweets from @{username}")
            
        except Exception as e:
            logger.warning(f"Failed to scrape tweets from @{username}: {e}")
            
    except ImportError:
        logger.error("ntscraper not installed")
    except Exception as e:
        logger.error(f"Twitter scraping error for @{username}: {e}")
    
    return tweets


async def fetch_all_defense_tweets(db, max_per_account: int = 5) -> int:
    """Fetch tweets from all defense accounts and store in database"""
    tweets_col = db.twitter_feeds
    total_new = 0
    
    logger.info(f"Starting Twitter scrape for {len(DEFENSE_ACCOUNTS)} accounts...")
    
    for username in DEFENSE_ACCOUNTS:
        try:
            # Run sync scraper in thread pool
            tweets = await asyncio.to_thread(scrape_tweets_sync, username, max_per_account)
            
            for tweet in tweets:
                # Check if tweet already exists (by URL or text)
                existing = await tweets_col.find_one({
                    "$or": [
                        {"tweet_url": tweet["tweet_url"]},
                        {"tweet_text": tweet["tweet_text"], "handle": tweet["handle"]}
                    ]
                })
                
                if not existing:
                    await tweets_col.insert_one(tweet)
                    total_new += 1
            
            # Small delay between accounts to avoid rate limiting
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.error(f"Error fetching tweets from @{username}: {e}")
            continue
    
    logger.info(f"Twitter scrape complete: {total_new} new tweets added")
    return total_new


async def get_recent_tweets(db, limit: int = 20) -> List[Dict]:
    """Get recent tweets from database"""
    tweets_col = db.twitter_feeds
    tweets = await tweets_col.find(
        {}, 
        {"_id": 0}
    ).sort("fetched_at", -1).limit(limit).to_list(limit)
    return tweets


# Alternative: Direct HTTP scraping without ntscraper
async def scrape_via_http(username: str) -> List[Dict]:
    """Alternative scraping method using direct HTTP requests"""
    import aiohttp
    
    tweets = []
    nitter_instances = [
        f"https://nitter.net/{username}",
        f"https://nitter.privacydev.net/{username}",
    ]
    
    for url in nitter_instances:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        html = await response.text()
                        # Parse HTML for tweets
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        tweet_containers = soup.find_all('div', class_='timeline-item')
                        
                        for container in tweet_containers[:5]:
                            tweet_content = container.find('div', class_='tweet-content')
                            if tweet_content:
                                tweet = {
                                    "id": str(uuid.uuid4()),
                                    "handle": f"@{username}",
                                    "account_name": ACCOUNT_NAMES.get(username, username),
                                    "tweet_text": tweet_content.get_text(strip=True),
                                    "tweet_url": f"https://twitter.com/{username}",
                                    "posted_at": datetime.now(timezone.utc).isoformat(),
                                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                                    "category": "defense",
                                    "is_relevant": True
                                }
                                tweets.append(tweet)
                        
                        if tweets:
                            break
                            
        except Exception as e:
            logger.warning(f"HTTP scrape failed for {url}: {e}")
            continue
    
    return tweets
