import feedparser
import logging
import asyncio
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# ============================================================
# RSS SOURCES - Comprehensive list for NER intelligence monitoring
# ============================================================

RSS_SOURCES = [
    # ---- REGIONAL NER SOURCES (Grassroots - HIGH PRIORITY, 60min polling) ----
    {"name": "NE Now", "url": "https://nenow.in/feed", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "The Sentinel Assam", "url": "https://sentinelassam.com/feed", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "The Assam Tribune", "url": "https://assamtribune.com/feed", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "Assam Times", "url": "https://assamtimes.org/rss.xml", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "EastMojo", "url": "https://www.eastmojo.com/feed/", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "North East Live", "url": "https://northeastlivetv.com/feed/", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "Nagaland Post", "url": "https://www.nagalandpost.com/feed/", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "The Shillong Times", "url": "https://theshillongtimes.com/feed/", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "Imphal Free Press", "url": "https://www.ifp.co.in/feed", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "The Morung Express", "url": "https://morungexpress.com/feed", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "The Sangai Express", "url": "https://www.thesangaiexpress.com/Encyc/rss.aspx", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "Eastern Mirror", "url": "https://easternmirrornagaland.com/feed/", "category": "regional", "language": "en", "region": "NER", "priority": "grassroots"},
    {"name": "Indian Express - North East", "url": "https://indianexpress.com/section/north-east-india/feed/", "category": "national", "language": "en", "region": "NER", "priority": "grassroots"},

    # ---- CROSS-BORDER (Grassroots - HIGH PRIORITY, 60min polling) ----
    {"name": "Myanmar Now", "url": "https://myanmar-now.org/en/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},
    {"name": "The Irrawaddy", "url": "https://www.irrawaddy.com/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},
    {"name": "Frontier Myanmar", "url": "https://frontiermyanmar.net/en/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},
    {"name": "Dhaka Tribune", "url": "https://www.dhakatribune.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "grassroots"},
    {"name": "The Daily Star BD", "url": "https://www.thedailystar.net/frontpage/rss.xml", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "grassroots"},

    # ---- NATIONAL SOURCES (Standard - 30min polling) ----
    {"name": "The Hindu - National", "url": "https://www.thehindu.com/news/national/feeder/default.rss", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Hindu - International", "url": "https://www.thehindu.com/news/international/feeder/default.rss", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "NDTV India News", "url": "https://feeds.feedburner.com/ndtvnews-india-news", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Times of India", "url": "https://timesofindia.indiatimes.com/rssfeeds/296589292.cms", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "News18 India", "url": "https://www.news18.com/rss/india.xml", "category": "national", "language": "en", "region": "India", "priority": "standard"},

    # ---- GOVERNMENT (Established - 12hr polling) ----
    {"name": "PIB Press Releases", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3", "category": "government", "language": "en", "region": "India", "priority": "established"},
    {"name": "PIB Defence", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3&DId=2", "category": "government", "language": "en", "region": "India", "priority": "established"},
    {"name": "MHA India", "url": "https://www.mha.gov.in/en/rss-feed", "category": "government", "language": "en", "region": "India", "priority": "established"},

    # ---- INTERNATIONAL (Standard - 30min polling) ----
    {"name": "BBC Asia/India", "url": "http://feeds.bbci.co.uk/news/world/asia/india/rss.xml", "category": "international", "language": "en", "region": "International", "priority": "standard"},
    {"name": "Al Jazeera", "url": "https://www.aljazeera.com/xml/rss/all.xml", "category": "international", "language": "en", "region": "International", "priority": "standard"},
    {"name": "Reuters World", "url": "https://www.reutersagency.com/feed/?best-topics=political-general&post_type=best", "category": "international", "language": "en", "region": "International", "priority": "standard"},
    {"name": "Global Times", "url": "https://www.globaltimes.cn/rss/outbrain.xml", "category": "international", "language": "en", "region": "International", "priority": "standard"},
    {"name": "SCMP Asia", "url": "https://www.scmp.com/rss/91/feed", "category": "international", "language": "en", "region": "International", "priority": "standard"},

    # ---- BANGLADESH (Standard) ----
    {"name": "Prothom Alo (Bangla)", "url": "https://www.prothomalo.com/feed/", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Prothom Alo (English)", "url": "https://en.prothomalo.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Kaler Kantho (Bangla)", "url": "https://www.kalerkantho.com/rss.xml", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Jugantor (Bangla)", "url": "https://www.jugantor.com/feed/rss.xml", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},

    # ---- MYANMAR (Standard) ----
    {"name": "Mizzima News", "url": "https://www.mizzima.com/rss.xml", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "standard"},

    # ---- EXPANDED BANGLADESH SOURCES ----
    {"name": "BDNews24", "url": "https://bdnews24.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "grassroots"},
    {"name": "New Age BD", "url": "https://www.newagebd.net/rss", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "The Daily Observer BD", "url": "https://www.observerbd.com/rss.php", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "The Business Standard BD", "url": "https://www.tbsnews.net/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Bangladesh Post", "url": "https://bangladeshpost.net/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Bangla Tribune", "url": "https://www.banglatribune.com/rss.xml", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Samakal BD", "url": "https://samakal.com/feed", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Daily Ittefaq", "url": "https://www.ittefaq.com.bd/feed", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},

    # ---- EXPANDED MYANMAR SOURCES ----
    {"name": "DVB (Democratic Voice of Burma)", "url": "https://english.dvb.no/feed/", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},
    {"name": "Shan Herald", "url": "https://english.shannews.org/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "standard"},
    {"name": "Khit Thit Media", "url": "https://khitthit.com/feed/", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "standard"},
    {"name": "BNI (Burma News International)", "url": "https://www.bnionline.net/en/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "standard"},
    {"name": "Myanmar Peace Monitor", "url": "https://www.mmpeacemonitor.org/feed/", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "standard"},
    {"name": "Narinjara News (Rakhine)", "url": "https://www.narinjara.com/feed/", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},
    {"name": "Chin World", "url": "https://www.chinworld.co/feed/", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "grassroots"},

    # ---- USER-REFERENCED SOURCES (HIGH QUALITY) ----
    {"name": "Dhaka Tribune", "url": "https://www.dhakatribune.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "elite"},
    {"name": "BSS News BD", "url": "https://www.bssnews.net/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "elite"},
    {"name": "Daily Star BD", "url": "https://www.thedailystar.net/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "elite"},
    {"name": "Daily Sun BD", "url": "https://www.daily-sun.com/feed", "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Ekhon TV", "url": "https://ekhon.tv/feed", "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},

    # ---- BANGLADESH (NER-IMPACT GAP-FILL) ----
    # Outlets added to plug coverage gaps for events with NER spillover:
    # wire-agency breaking news (UNB), economic stability (Financial Express),
    # Indo-BD diplomacy (The Independent), outside-POV reporting (BBC Bangla),
    # opposition-lens (Naya Diganta) and Islamist-scene (Daily Inqilab) for
    # tracking political volatility that can affect the BD-NER border belt.
    {"name": "UNB (United News BD)",     "url": "https://unb.com.bd/rss/category/bangladesh.xml",        "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "elite"},
    {"name": "BBC Bangla",               "url": "https://feeds.bbci.co.uk/bengali/rss.xml",               "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "elite"},
    {"name": "Financial Express BD",     "url": "https://thefinancialexpress.com.bd/rss.xml",             "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "The Independent BD",       "url": "https://www.theindependentbd.com/rss.xml",               "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Risingbd",                 "url": "https://www.risingbd.com/feed",                          "category": "bangladesh", "language": "en", "region": "Bangladesh", "priority": "standard"},
    {"name": "Dhaka Post",               "url": "https://www.dhakapost.com/feed",                         "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Naya Diganta (Bangla)",    "url": "https://www.dailynayadiganta.com/feed",                  "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Daily Inqilab (Bangla)",   "url": "https://www.dailyinqilab.com/rss.xml",                   "category": "bangladesh", "language": "bn", "region": "Bangladesh", "priority": "standard"},
    {"name": "Irrawaddy", "url": "https://www.irrawaddy.com/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "elite"},
    {"name": "Mizzima English", "url": "https://eng.mizzima.com/feed", "category": "myanmar", "language": "en", "region": "Myanmar", "priority": "elite"},
    {"name": "DVB Burmese", "url": "https://burmese.dvb.no/feed/", "category": "myanmar", "language": "my", "region": "Myanmar", "priority": "grassroots"},
    {"name": "ANI News", "url": "https://aninews.in/feed/", "category": "national", "language": "en", "region": "India", "priority": "elite"},

    # ---- EXPANDED NATIONAL INDIAN SOURCES ----
    {"name": "India Today", "url": "https://www.indiatoday.in/rss/home", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Hindustan Times", "url": "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Deccan Herald", "url": "https://www.deccanherald.com/rss/national.xml", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Wire", "url": "https://thewire.in/feed", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Scroll.in", "url": "https://scroll.in/rss/feed", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Print", "url": "https://theprint.in/feed/", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Quint", "url": "https://www.thequint.com/quintlab/rss-feeds/rss-news", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Mint - Defence", "url": "https://www.livemint.com/rss/news", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Economic Times - Defence", "url": "https://economictimes.indiatimes.com/news/defence/rssfeeds/68740888.cms", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Firstpost", "url": "https://www.firstpost.com/rss/india.xml", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Indian Express - India", "url": "https://indianexpress.com/section/india/feed/", "category": "national", "language": "en", "region": "India", "priority": "standard"},
    {"name": "The Tribune India", "url": "https://www.tribuneindia.com/rss/feed?catId=2", "category": "national", "language": "en", "region": "India", "priority": "standard"},

    # ---- GOVERNMENT: PIB NE REGIONAL OFFICES ----
    {"name": "PIB Imphal", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=12", "category": "government", "language": "en", "region": "Manipur", "priority": "elite"},
    {"name": "PIB Kohima", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=16", "category": "government", "language": "en", "region": "Nagaland", "priority": "elite"},
    {"name": "PIB Agartala", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=32", "category": "government", "language": "en", "region": "Tripura", "priority": "elite"},
    {"name": "PIB Itanagar", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=18", "category": "government", "language": "en", "region": "Arunachal Pradesh", "priority": "elite"},
    {"name": "PIB Shillong", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=17", "category": "government", "language": "en", "region": "Meghalaya", "priority": "elite"},
    {"name": "PIB Aizawl", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=13", "category": "government", "language": "en", "region": "Mizoram", "priority": "elite"},
    {"name": "PIB Gangtok", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=14", "category": "government", "language": "en", "region": "Sikkim", "priority": "standard"},
    {"name": "PIB Delhi National", "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1", "category": "government", "language": "en", "region": "India", "priority": "elite"},
    {"name": "PIB Media Invitations", "url": "https://pib.gov.in/RssMain.aspx?ModId=10&Lang=1&Regid=1", "category": "government", "language": "en", "region": "India", "priority": "standard"},

    # ---- GOVERNMENT: KEY MINISTRIES & AGENCIES ----
    {"name": "MEA Press Releases", "url": "https://mea.gov.in/rss/press-releases.xml", "category": "government", "language": "en", "region": "India", "priority": "elite"},
    {"name": "NIA RSS", "url": "https://nia.gov.in/rss-feed.htm", "category": "government", "language": "en", "region": "India", "priority": "elite"},
    {"name": "Ministry of DoNER", "url": "https://doner.gov.in/rss-feed", "category": "government", "language": "en", "region": "India", "priority": "standard"},
    {"name": "NDMA Alerts", "url": "https://ndma.gov.in/rss.xml", "category": "government", "language": "en", "region": "India", "priority": "standard"},
    {"name": "Open Gov Data India", "url": "https://data.gov.in/feed", "category": "government", "language": "en", "region": "India", "priority": "standard"},

    # ---- GOVERNMENT: NE STATE DIPR ----
    {"name": "Manipur DIPR", "url": "https://manipur.gov.in/rss-feed/", "category": "government", "language": "en", "region": "Manipur", "priority": "elite"},
    {"name": "Assam CM Office", "url": "https://cm.assam.gov.in/rss-feed/", "category": "government", "language": "en", "region": "Assam", "priority": "elite"},
    {"name": "Nagaland DIPR", "url": "https://dipr.nagaland.gov.in/feed/", "category": "government", "language": "en", "region": "Nagaland", "priority": "standard"},
]

def get_sources_by_priority(priority: str) -> list:
    """Get RSS sources filtered by priority tier, including custom DB feeds."""
    import asyncio
    all_sources = list(RSS_SOURCES)
    try:
        from shared import db
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an async context — use the sync helper
            return [s for s in all_sources if s.get("priority") == priority]
        else:
            custom = loop.run_until_complete(db.custom_rss_feeds.find({"active": True}, {"_id": 0}).to_list(200))
            all_sources.extend(custom)
    except Exception:
        pass
    return [s for s in all_sources if s.get("priority") == priority]


async def get_all_sources_async() -> list:
    """Get all RSS sources including custom feeds from DB."""
    from shared import db
    all_sources = list(RSS_SOURCES)
    try:
        custom = await db.custom_rss_feeds.find({"active": True}, {"_id": 0}).to_list(200)
        all_sources.extend(custom)
    except Exception:
        pass
    return all_sources


# ============================================================
# NER + Border Keywords (English, Bengali, Assamese transliterated)
# ============================================================

NER_KEYWORDS_EN = [
    # NER States & Cities
    "assam", "meghalaya", "mizoram", "manipur", "arunachal", "tripura",
    "nagaland", "sikkim", "northeast india", "north east india", "north-east",
    "guwahati", "shillong", "imphal", "itanagar", "agartala", "aizawl",
    "dimapur", "kohima", "tinsukia", "dibrugarh", "jorhat", "silchar",
    "tezpur", "bongaigaon", "kokrajhar", "barpeta", "goalpara", "lumding",
    "churachandpur", "ukhrul", "champhai", "moreh", "dawki", "tawang",
    "changlang", "tirap", "dhalai", "jaintia",

    # Security Terms
    "insurgent", "insurgency", "militant", "militancy", "separatist",
    "ulfa", "nscn", "ndfb", "klo", "hnlc", "nlft", "attf", "bnlf",
    "bodo", "meitei", "kuki", "naga", "chin", "rohingya",
    "ied", "ambush", "encounter", "ceasefire", "peace accord",
    "extortion", "kidnapping", "abduction",

    # Cross-border
    "myanmar", "bangladesh", "border", "bsf", "assam rifles",
    "cross-border", "infiltration", "illegal entry",
    "mcmahon line", "lac", "line of actual control",

    # Threat Categories
    "drug", "narcotics", "heroin", "methamphetamine", "opium", "poppy",
    "smuggling", "trafficking", "contraband",
    "arms", "weapons", "ammunition", "firearms",
    "immigration", "immigrant", "refugee", "deportation",
    "ethnic", "communal", "riot", "violence", "curfew", "tension",
    "cyber", "hack", "data breach",
    "infrastructure", "strategic", "military base", "airfield",
    "drone", "surveillance",

    # Bangladesh specific
    "dhaka", "chittagong", "sylhet", "rajshahi", "rohingya camp",
    "jamaat", "awami league", "bnp", "hasina", "yunus",
    "padma", "teesta", "brahmaputra",
    "bangladesh navy", "bangladesh army", "border guard bangladesh",
    "st martin", "bay of bengal", "chittagong port",

    # Myanmar specific
    "naypyidaw", "yangon", "mandalay", "rakhine", "chin state",
    "shan state", "kachin", "sagaing",
    "tatmadaw", "junta", "coup", "arakan army",
    "ethnic armed", "resistance", "pdf", "nug",
    "min aung hlaing", "suu kyi",

    # Foreign Power Influence (HIGH PRIORITY keywords)
    "china", "chinese", "beijing", "belt and road", "bri",
    "pakistan", "pakistani", "islamabad", "isi",
    "united states", "usa", "american", "washington",
    "chinese investment", "chinese loan", "chinese military",
    "pakistan influence", "pakistan support",
    "us aid", "us military", "quad", "indo-pacific",
    "deep sea port", "sonadia", "hambantota",
    "chinese base", "military cooperation",
]

# Bengali/Assamese transliterated keywords for local language sources
NER_KEYWORDS_LOCAL = [
    # Bengali (transliterated from Bangla newspapers)
    "সীমান্ত", "অনুপ্রবেশ", "মাদক", "চোরাচালান",
    "সন্ত্রাসী", "জঙ্গি", "রোহিঙ্গা", "শরণার্থী",
    "ত্রিপুরা", "মেঘালয়", "মিজোরাম", "মণিপুর", "অসম", "অরুণাচল",
    "বাংলাদেশ", "মিয়ানমার",
    "সংঘর্ষ", "দাঙ্গা", "হত্যা", "গ্রেপ্তার",
    "বিএসএফ",

    # Assamese transliterated
    "সীমা", "উগ্ৰপন্থী", "আলফা", "মাদক দ্ৰব্য",
    "অসম", "গুৱাহাটী", "তিনিচুকীয়া", "ডিব্ৰুগড়",
]

# Combine all keywords
ALL_KEYWORDS = NER_KEYWORDS_EN + NER_KEYWORDS_LOCAL

executor = ThreadPoolExecutor(max_workers=6)


def parse_feed(source: dict) -> list:
    """Parse a single RSS feed (blocking operation)"""
    try:
        feed = feedparser.parse(source["url"])
        articles = []

        for entry in feed.entries[:25]:
            title = entry.get("title", "")
            description = entry.get("description", "") or entry.get("summary", "")
            link = entry.get("link", "")

            # Parse published date
            published = entry.get("published_parsed") or entry.get("updated_parsed")
            if published:
                try:
                    pub_dt = datetime(*published[:6], tzinfo=timezone.utc)
                    published_at = pub_dt.isoformat()
                except (ValueError, TypeError):
                    published_at = datetime.now(timezone.utc).isoformat()
            else:
                published_at = datetime.now(timezone.utc).isoformat()

            articles.append({
                "title": title,
                "source": source["name"],
                "source_url": link,
                "published_at": published_at,
                "raw_content": description[:5000],
                "description": description[:2000],
                "language": source.get("language", "en"),
                "category": source.get("category", "general"),
                "region": source.get("region", "Unknown"),
            })

        logger.info(f"Parsed {len(articles)} articles from {source['name']}")
        return articles

    except Exception as e:
        logger.error(f"Failed to parse {source['name']} ({source['url']}): {e}")
        return []


def is_ner_relevant(article: dict, dynamic_keyword_weights: list = None) -> bool:
    """Check if article is relevant to NER intelligence monitoring.
    
    Uses dynamic keywords if available, falls back to static list.
    For Bangladesh/Myanmar-specific feeds, all content is considered relevant.
    For Indian national/international feeds, keyword matching is applied.
    """
    region = article.get("region", "")
    category = article.get("category", "")

    # All content from Bangladesh and Myanmar feeds is relevant
    if category in ("bangladesh", "myanmar") or region in ("Bangladesh", "Myanmar"):
        return True

    # All content from NER regional feeds is relevant
    if category == "regional" or region == "NER":
        return True

    # For national/international sources, apply keyword filtering
    text = f"{article.get('title', '')} {article.get('raw_content', '')}".lower()
    
    # Use dynamic keywords if available (weighted matching)
    if dynamic_keyword_weights:
        from keyword_engine import score_article_against_keywords
        score = score_article_against_keywords(article, dynamic_keyword_weights)
        if score > 5:
            return True
    
    # Fallback to static keywords
    return any(kw in text for kw in ALL_KEYWORDS)


async def fetch_all_feeds(progress_callback=None, sources=None, dynamic_keyword_weights=None) -> list:
    """Fetch and filter articles from RSS sources.
    If sources is provided, only those sources are fetched.
    If dynamic_keyword_weights is provided, uses them for relevance matching."""
    loop = asyncio.get_event_loop()
    all_articles = []
    if sources:
        active_sources = sources
    else:
        active_sources = await get_all_sources_async()

    source_summary = {}
    for i, source in enumerate(active_sources):
        source_name = source["name"]
        if progress_callback:
            await progress_callback(i, len(active_sources), source_name)
        
        try:
            result = await loop.run_in_executor(executor, parse_feed, source)
        except Exception as e:
            logger.error(f"Feed fetch error for {source_name}: {e}")
            source_summary[source_name] = {"fetched": 0, "relevant": 0, "error": str(e)}
            continue
        
        relevant = [a for a in result if is_ner_relevant(a, dynamic_keyword_weights)]
        all_articles.extend(relevant)
        source_summary[source_name] = {"fetched": len(result), "relevant": len(relevant)}

    if progress_callback:
        await progress_callback(len(active_sources), len(active_sources), "Complete")

    logger.info("=== RSS Fetch Summary ===")
    for name, stats in source_summary.items():
        if "error" in stats:
            logger.info(f"  {name}: ERROR - {stats['error'][:80]}")
        else:
            logger.info(f"  {name}: {stats['fetched']} fetched, {stats['relevant']} relevant")
    logger.info(f"Total relevant articles: {len(all_articles)}")

    return all_articles
