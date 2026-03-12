"""
Collecte d'actualites IA + Hardware sans API payante.
Sources : flux RSS + HN Algolia (pas de cle requise).
"""
import requests
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from urllib.parse import quote_plus

try:
    from deep_translator import GoogleTranslator
    def _translate(text: str) -> str:
        if not text or len(text) < 10:
            return text
        try:
            result = GoogleTranslator(source="auto", target="fr").translate(text[:500])
            return result if result else text
        except Exception:
            return text
    _test = GoogleTranslator(source="auto", target="fr").translate("test")
    print("  [TRANSLATE] Google Translate actif")
except Exception:
    print("  [TRANSLATE] Google Translate indisponible — textes en anglais")
    def _translate(text: str) -> str:
        return text

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RevuePresse/1.0)"}

# ── Flux RSS filtrés (keywords requis) ───────────────────────────────────
RSS_FEEDS_FILTERED = [
    # IA & Dev
    ("The Verge — AI",        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica — AI",     "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat — AI",      "https://venturebeat.com/category/ai/feed/"),
    ("Simon Willison",        "https://simonwillison.net/atom/everything/"),
    ("Dev.to — AI",           "https://dev.to/feed/tag/ai"),
    ("The Verge — Tech",      "https://www.theverge.com/rss/tech/index.xml"),
    # Hardware & GPU
    ("Tom's Hardware",        "https://www.tomshardware.com/feeds/all"),
    # Constructeurs IA
    ("NVIDIA Blog",           "https://blogs.nvidia.com/feed/"),
    ("Google AI Blog",        "https://blog.research.google/feeds/posts/default"),
    ("OpenAI Blog",           "https://openai.com/blog/rss/"),
    ("Anthropic News",        "https://www.anthropic.com/news/rss"),
    ("Mistral AI Blog",       "https://mistral.ai/news/rss"),
]

# ── Flux RSS non filtrés (tout passe — sources 100% IA/tech) ─────────────
RSS_FEEDS_UNFILTERED = [
    # Lancements produits IA — Product Hunt top AI du jour
    ("Product Hunt — AI",     "https://www.producthunt.com/feed?category=artificial-intelligence"),
    # TechCrunch IA
    ("TechCrunch — AI",       "https://techcrunch.com/category/artificial-intelligence/feed/"),
    # The AI Times / newsletters
    ("AI News",               "https://www.artificialintelligence-news.com/feed/"),
    # Startups & funding
    ("TechCrunch — Startups", "https://techcrunch.com/category/startups/feed/"),
    # Blogs spécialisés vibe coding / dev tools
    ("Towards Data Science",  "https://towardsdatascience.com/feed"),
]

# ── Mots-clés pour les flux filtrés ──────────────────────────────────────
AI_KEYWORDS = [
    # Outils de coding IA
    "vibe cod", "ai cod", "llm", "copilot", "cursor", "kiro", "windsurf",
    "claude", "gemini", "gpt", "codestral", "agentic", "code generation",
    "ai agent", "large language", "enterprise ai", "mistral", "anthropic",
    "openai", "deepseek", "qwen", "llama", "codeium", "tabnine", "replit",
    "devin", "swe-agent", "aide", "continue", "cline", "bolt", "lovable",
    # Audio / multimodal IA
    "text to speech", "tts", "voice cloning", "audio ai", "speech synthesis",
    "fish audio", "elevenlabs", "suno", "udio", "stable audio",
    # Agents & frameworks
    "langchain", "langgraph", "autogen", "crewai", "dspy", "smolagents",
    "mcp", "model context protocol", "function calling",
    # Modèles & infra
    "transformer", "diffusion model", "fine-tun", "rag", "retrieval",
    "embedding", "vector", "inference", "quantiz",
    # Startups & funding
    "seed round", "series a", "raises", "lève", "funding", "startup ai",
    "ami labs", "lecun", "yann",
]

HARDWARE_KEYWORDS = [
    "nvidia", "amd", "intel", "gpu", "dgx", "spark dgx", "workstation",
    "geforce", "radeon", "rtx", "h100", "h200", "b200", "blackwell",
    "hopper", "mi300", "ryzen ai", "npu", "ai pc", "ai workstation",
    "groq", "tpu", "inference chip", "data center", "hpc",
]

ALL_KEYWORDS = AI_KEYWORDS + HARDWARE_KEYWORDS


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _parse_feed(root, name: str, filtered: bool, max_items: int) -> list[dict]:
    """Parse un flux RSS ou Atom, avec ou sans filtre keyword."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        pub   = item.findtext("pubDate") or ""
        if not filtered or _is_relevant(title + " " + desc):
            items.append({"title": _translate(title), "link": link,
                          "summary": _translate(desc[:300]), "date": pub, "source": name})

    for entry in root.findall("atom:entry", ns):
        title   = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link    = link_el.get("href", "") if link_el is not None else ""
        summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
        pub     = entry.findtext("atom:updated", namespaces=ns) or ""
        if not filtered or _is_relevant(title + " " + summary):
            items.append({"title": _translate(title), "link": link,
                          "summary": _translate(summary[:300]), "date": pub, "source": name})

    items.sort(key=lambda x: _parse_date(x["date"]), reverse=True)
    return items[:max_items]


def fetch_rss(name: str, url: str, max_items: int = 5, filtered: bool = True) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        return _parse_feed(root, name, filtered=filtered, max_items=max_items)
    except Exception as e:
        print(f"  [RSS] Erreur {name}: {e}")
        return []


def fetch_hn_algolia(query: str, max_items: int = 8) -> list[dict]:
    try:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={quote_plus(query)}&tags=story&hitsPerPage={max_items}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        results = []
        for h in hits:
            title = (h.get("title") or "").strip()
            link  = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID','')}"
            if title:
                results.append({
                    "title": _translate(title),
                    "link": link,
                    "summary": "",
                    "date": h.get("created_at", ""),
                    "source": "Hacker News",
                })
        return results
    except Exception as e:
        print(f"  [HN Algolia] Erreur '{query}': {e}")
        return []


def collect_news() -> list[dict]:
    all_articles = []

    # 1. Flux filtrés (sources généralistes — on garde seulement ce qui est pertinent)
    print("  → Collecte RSS filtrée...")
    for name, url in RSS_FEEDS_FILTERED:
        articles = fetch_rss(name, url, filtered=True)
        print(f"     {name}: {len(articles)} article(s)")
        all_articles.extend(articles)

    # 2. Flux non filtrés (sources 100% IA/tech — tout passe)
    print("  → Collecte RSS non filtrée (sources IA)...")
    for name, url in RSS_FEEDS_UNFILTERED:
        articles = fetch_rss(name, url, max_items=10, filtered=False)
        print(f"     {name}: {len(articles)} article(s)")
        all_articles.extend(articles)

    # 3. Hacker News — requêtes élargies
    hn_queries = [
        "vibe coding", "AI coding assistant", "LLM code generation",
        "NVIDIA GPU AI", "AI startup launch", "new AI tool",
        "fish audio", "voice AI", "AI agent framework",
        "GPT-5", "Claude 4", "Gemini 2",
    ]
    print("  → Hacker News (Algolia)...")
    for q in hn_queries:
        results = fetch_hn_algolia(q, max_items=5)
        print(f"     '{q}': {len(results)} article(s)")
        all_articles.extend(results)

    # Dédupliquer
    seen_urls, seen_titles, unique = set(), set(), []
    for art in all_articles:
        url = art.get("link", "").strip()
        raw_title = art.get("title", "").lower().strip()
        title_key = "".join(c for c in raw_title if c.isalnum() or c.isspace())[:60].strip()
        if url and url in seen_urls:
            continue
        if title_key and title_key in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_key:
            seen_titles.add(title_key)
        unique.append(art)

    print(f"  → Total: {len(unique)} articles uniques")
    return unique