"""
Collecte d'actualités IA sans API payante.
Sources : flux RSS + DuckDuckGo HTML search (pas de clé requise).
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
    # Test rapide au chargement
    _test = GoogleTranslator(source="auto", target="fr").translate("test")
    print("  [TRANSLATE] Google Translate actif")
except Exception:
    print("  [TRANSLATE] Google Translate indisponible — textes en anglais")
    def _translate(text: str) -> str:
        return text

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RevuePresse/1.0)"}

# ── Flux RSS gratuits ────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("The Verge — AI",        "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("Ars Technica — AI",     "https://feeds.arstechnica.com/arstechnica/technology-lab"),
    ("VentureBeat — AI",      "https://venturebeat.com/category/ai/feed/"),
    ("Simon Willison",        "https://simonwillison.net/atom/everything/"),
    # Blogs spécialisés
    ("Towards Data Science",  "https://towardsdatascience.com/feed"),
    ("Dev.to — AI",            "https://dev.to/feed/tag/ai"),
]

# ── Mots-clés pour filtrer les articles pertinents ───────────────────────────
KEYWORDS = [
    "vibe cod", "ai cod", "llm", "copilot", "cursor", "kiro", "windsurf",
    "claude", "gemini", "gpt", "codestral", "agentic", "code generation",
    "ai agent", "large project", "enterprise ai",
]


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in KEYWORDS)


def _parse_date(date_str: str) -> datetime:
    """Tente de parser une date RSS/Atom, retourne epoch si échec."""
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def fetch_rss(name: str, url: str, max_items: int = 5) -> list[dict]:
    """Récupère et filtre les articles d'un flux RSS/Atom."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        items = []

        # Format RSS
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            desc  = (item.findtext("description") or "").strip()
            pub   = item.findtext("pubDate") or ""
            if _is_relevant(title + " " + desc):
                items.append({"title": _translate(title), "link": link, "summary": _translate(desc[:300]), "date": pub, "source": name})

        # Format Atom
        for entry in root.findall("atom:entry", ns):
            title   = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            link_el = entry.find("atom:link", ns)
            link    = link_el.get("href", "") if link_el is not None else ""
            summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
            pub     = entry.findtext("atom:updated", namespaces=ns) or ""
            if _is_relevant(title + " " + summary):
                items.append({"title": _translate(title), "link": link, "summary": _translate(summary[:300]), "date": pub, "source": name})

        # Trier par date décroissante et limiter
        items.sort(key=lambda x: _parse_date(x["date"]), reverse=True)
        return items[:max_items]

    except Exception as e:
        print(f"  [RSS] Erreur {name}: {e}")
        return []


def fetch_hn_algolia(query: str, max_items: int = 8) -> list[dict]:
    """Recherche HN via l'API Algolia — gratuite, stable, pas de clé."""
    try:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={quote_plus(query)}&tags=story&hitsPerPage={max_items}"
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        results = []
        for h in hits:
            title = (h.get("title") or "").strip()
            link  = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID','')}"
            if title and _is_relevant(title):
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
    """Collecte RSS + HN Algolia, retourne une liste d'articles dédupliqués."""
    all_articles = []

    # 1. Flux RSS
    print("  → Collecte RSS...")
    for name, url in RSS_FEEDS:
        articles = fetch_rss(name, url)
        print(f"     {name}: {len(articles)} article(s)")
        all_articles.extend(articles)

    # 2. Hacker News via Algolia (stable, sans clé)
    hn_queries = ["vibe coding", "AI coding assistant", "LLM code generation"]
    print("  → Hacker News (Algolia)...")
    for q in hn_queries:
        results = fetch_hn_algolia(q)
        print(f"     '{q}': {len(results)} article(s)")
        all_articles.extend(results)

    # Dédupliquer par URL d'abord, puis par titre normalisé
    seen_urls, seen_titles, unique = set(), set(), []
    for art in all_articles:
        url = art.get("link", "").strip()
        # Normaliser le titre : minuscules, sans ponctuation, premiers 60 chars
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
