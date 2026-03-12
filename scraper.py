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
    ("Product Hunt — AI",       "https://www.producthunt.com/feed?category=artificial-intelligence"),
    # TechCrunch IA
    ("TechCrunch — AI",         "https://techcrunch.com/category/artificial-intelligence/feed/"),
    # The AI Times / newsletters
    ("AI News",                 "https://www.artificialintelligence-news.com/feed/"),
    # Startups & funding
    ("TechCrunch — Startups",   "https://techcrunch.com/category/startups/feed/"),
    # Blogs spécialisés vibe coding / dev tools
    ("Towards Data Science",    "https://towardsdatascience.com/feed"),
    # Open source LLM & Hugging Face
    ("Hugging Face Blog",       "https://huggingface.co/blog/feed.xml"),
    # LLM news agrégateur
    ("The Batch — DeepLearning","https://www.deeplearning.ai/the-batch/feed/"),
    # Dev tools & IDE
    ("Dev.to — LLM",            "https://dev.to/feed/tag/llm"),
    ("Dev.to — Cursor",         "https://dev.to/feed/tag/cursor"),
    ("Dev.to — Agents",         "https://dev.to/feed/tag/aiagents"),
]

# ── Mots-clés thématiques (concepts, pas noms de produits) ───────────────

# Thème : Vibe coding / génération de code IA
KEYWORDS_CODING = [
    "vibe cod", "ai cod", "code generation", "code gen", "coding assistant",
    "ai developer", "developer tool", "devtool", "ide plugin", "code completion",
    "pair programming", "automated coding", "ai programming",
    "code review ai", "test generation", "ai testing", "code refactor",
    # Qualité sur gros projets
    "large codebase", "monorepo", "legacy code", "technical debt",
    "code quality", "architecture ai", "refactoring ai", "context window code",
    "long context", "multi-file", "project-wide", "codebase understanding",
    # IDE spécifiques
    "cursor tip", "cursor trick", "cursor feature", "cursor update", "cursor ai",
    "kiro feature", "kiro update", "kiro tip",
    "vscode ai", "vscode extension", "vscode copilot", "vscode tip",
    "windsurf feature", "windsurf update",
    "github copilot", "copilot workspace", "copilot feature",
    # Astuces vibe coding
    "prompt engineering code", "system prompt", "rules for ai",
    ".cursorrules", "cursor rules", "ai rules", "context file",
    "memory bank", "project context", "ai workflow", "coding workflow",
]

# Thème : Agents IA / automatisation / pipelines
KEYWORDS_AGENTS = [
    "ai agent", "agentic", "autonomous agent", "multi-agent", "workflow automation",
    "ai assistant", "ai copilot", "ai workflow", "task automation", "ai orchestrat",
    "function calling", "tool use", "model context", "mcp", "computer use",
    "browser automation", "rpa ai",
    # Pipelines & frameworks
    "langchain", "langgraph", "autogen", "crewai", "dspy", "smolagents",
    "n8n", "make.com", "zapier ai", "pipeline ai", "automation pipeline",
    "ci/cd ai", "devops ai", "ai pipeline", "data pipeline ai",
    # Patterns d'automatisation
    "agentic workflow", "agent loop", "tool calling", "function calling",
    "structured output", "json mode", "constrained generation",
]

# Thème : Modèles de langage (LLM) — surtout open source
KEYWORDS_LLM = [
    "llm", "large language model", "foundation model", "language model",
    "transformer", "fine-tun", "rag", "retrieval augmented", "embedding",
    "benchmark", "evals", "context window", "multimodal", "vision model",
    "reasoning model", "chain of thought", "prompt engineer",
    # Open source en priorité
    "open source model", "open weight", "open llm", "hugging face",
    "ollama model", "local llm", "self-hosted", "on-premise ai",
    "mistral", "llama", "qwen", "deepseek", "phi-", "gemma", "falcon",
    "mixtral", "command r", "yi-", "internlm", "codellama",
    "model release", "new model", "model launch", "weights released",
    # Techniques d'amélioration
    "quantiz", "gguf", "ggml", "lora", "qlora", "peft",
    "context length", "long context", "128k", "200k", "1m token",
    "inference speed", "token per second", "latency model",
]

# Thème : Audio / voix / multimédia IA
KEYWORDS_AUDIO = [
    "text to speech", "tts", "voice cloning", "voice synthesis", "speech synthesis",
    "audio generation", "audio ai", "voice ai", "speech recognition", "asr",
    "music generation", "sound generation", "voice model", "audio model",
    "real-time voice", "voice conversion",
]

# Thème : Startups IA / financement
KEYWORDS_STARTUP = [
    "raises", "funding", "seed round", "series a", "series b", "million",
    "billion", "valuation", "venture", "invest", "launch", "lève", "milliard",
    "annonce", "nouveau", "new ai", "ai startup", "founded", "backed by",
    "product launch", "new tool", "new feature", "just launched", "just released",
]

# Thème : GPU / hardware IA
KEYWORDS_HARDWARE = [
    "nvidia", "amd", "intel", "gpu", "dgx", "geforce", "radeon", "rtx",
    "h100", "h200", "b200", "blackwell", "hopper", "mi300", "groq", "tpu",
    "npu", "ai chip", "ai pc", "ai workstation", "data center", "hpc",
    "inference hardware", "training cluster",
]

# Thème : Entreprise / production IA
KEYWORDS_ENTERPRISE = [
    "enterprise ai", "production ai", "ai deployment", "ai platform",
    "ai infrastructure", "mlops", "ai ops", "model serving", "ai governance",
    "responsible ai", "ai security", "ai compliance", "ai integration",
]

ALL_KEYWORDS = (
    KEYWORDS_CODING + KEYWORDS_AGENTS + KEYWORDS_LLM +
    KEYWORDS_AUDIO + KEYWORDS_STARTUP + KEYWORDS_HARDWARE + KEYWORDS_ENTERPRISE
)


def _is_relevant(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in ALL_KEYWORDS)


def detect_theme(text: str) -> str:
    """Détecte le thème principal d'un article par ses mots-clés sémantiques."""
    t = text.lower()
    if any(kw in t for kw in KEYWORDS_AUDIO):
        return "Audio et Voix IA"
    if any(kw in t for kw in KEYWORDS_CODING):
        return "Vibe Coding"
    if any(kw in t for kw in KEYWORDS_AGENTS):
        return "Assistants et Agents IA"
    if any(kw in t for kw in KEYWORDS_LLM):
        return "Modeles et LLM"
    if any(kw in t for kw in KEYWORDS_HARDWARE):
        return "GPU et Hardware"
    if any(kw in t for kw in KEYWORDS_STARTUP):
        return "Startups et Financement"
    if any(kw in t for kw in KEYWORDS_ENTERPRISE):
        return "Entreprise et Industrie"
    return "Autres"


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except Exception:
            pass
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _normalize_date(date_str: str) -> str:
    """Normalise n'importe quel format de date RSS/Atom en YYYY-MM-DD."""
    dt = _parse_date(date_str)
    if dt.year == 1970:
        return ""
    return dt.strftime("%Y-%m-%d")


def _parse_feed(root, name: str, filtered: bool, max_items: int) -> list[dict]:
    """Parse un flux RSS ou Atom, avec ou sans filtre keyword."""
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []

    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link  = (item.findtext("link")  or "").strip()
        desc  = (item.findtext("description") or "").strip()
        pub   = _normalize_date(item.findtext("pubDate") or "")
        if not filtered or _is_relevant(title + " " + desc):
            items.append({"title": _translate(title), "link": link,
                          "summary": _translate(desc[:300]), "date": pub, "source": name})

    for entry in root.findall("atom:entry", ns):
        title   = (entry.findtext("atom:title", namespaces=ns) or "").strip()
        link_el = entry.find("atom:link", ns)
        link    = link_el.get("href", "") if link_el is not None else ""
        summary = (entry.findtext("atom:summary", namespaces=ns) or "").strip()
        pub     = _normalize_date(entry.findtext("atom:updated", namespaces=ns) or "")
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
                    "date": _normalize_date(h.get("created_at", "")),
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

    # 3. Hacker News — requêtes ciblées sur les vrais sujets d'intérêt
    hn_queries = [
        # Vibe coding & IDE
        "vibe coding tips", "cursor AI tips", "vscode AI extension",
        "AI coding large project", "cursorrules", "AI code quality",
        # LLM open source
        "open source LLM release", "new open weight model", "local LLM",
        "ollama new model", "huggingface model release",
        # Agents & pipelines
        "AI agent workflow", "LLM pipeline automation", "MCP model context protocol",
        "agentic coding", "n8n AI", "AI automation workflow",
        # Hardware
        "NVIDIA GPU AI", "new AI chip",
        # Startups & launches
        "AI startup launch", "new AI tool developer",
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