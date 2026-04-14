"""
Collecte d'actualites IA + Hardware sans API payante.
Sources : flux RSS + HN Algolia (pas de cle requise).
Traduction FR 100% gratuite : MyMemory API (CI + local) + Ollama (local fallback).
"""
import os
import re
import time
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
from urllib.parse import quote_plus, quote

# Traduction individuelle désactivée — on fait du batch après collecte
def _translate(text: str) -> str:
    return text


def _clean_html(text: str) -> str:
    """Supprime les balises HTML et décode les entités pour obtenir du texte brut."""
    if not text:
        return ""
    # Supprimer les balises HTML
    text = re.sub(r"<[^>]+>", " ", text)
    # Décoder les entités HTML (&amp; &lt; &#39; etc.)
    text = unescape(text)
    # Normaliser les espaces
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ── Config traduction gratuite ────────────────────────────────────────────
_OLLAMA_URL   = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
_OLLAMA_MODEL = os.environ.get("OLLAMA_TRANSLATE_MODEL", "mistral:latest")
# MyMemory : email optionnel pour passer de 5000 à 10000 mots/jour
_MYMEMORY_EMAIL = os.environ.get("MYMEMORY_EMAIL", "")


def _is_likely_french(text: str) -> bool:
    """Détecte si un texte est probablement déjà en français (heuristique simple)."""
    if not text or len(text) < 20:
        return False
    t = text.lower()
    fr_markers = [" le ", " la ", " les ", " des ", " une ", " est ", " dans ",
                  " pour ", " avec ", " sur ", " qui ", " que ", " pas ",
                  " sont ", " cette ", " mais ", " aussi ", " plus ", " très ",
                  " être ", " faire ", " peut ", " tout ", " comme "]
    hits = sum(1 for m in fr_markers if m in t)
    return hits >= 3


def _translate_one_mymemory(text: str) -> str:
    """Traduit un texte via MyMemory (gratuit, sans clé, 5000 mots/jour)."""
    if not text or len(text.strip()) < 5:
        return text
    try:
        params = {"q": text[:500], "langpair": "en|fr"}
        if _MYMEMORY_EMAIL:
            params["de"] = _MYMEMORY_EMAIL
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params=params,
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("responseStatus", 0)
        translated = data.get("responseData", {}).get("translatedText", "")

        # Status 429 = rate limit, 403 = quota dépassé
        if status in (429, 403):
            print(f"  [MYMEMORY] Rate limit atteint (status={status})")
            return text

        # MyMemory renvoie le texte original si la traduction échoue
        if translated and translated.upper() != text.upper():
            return translated
        # Vérifier si c'est un message d'erreur MyMemory
        if "MYMEMORY WARNING" in (translated or "").upper():
            print(f"  [MYMEMORY] Quota warning: {translated[:80]}")
            return text
    except Exception as e:
        print(f"  [MYMEMORY] Erreur: {e}")
    return text


def _translate_via_google(texts: list[str]) -> list[str] | None:
    """
    Traduit via Google Translate (deep-translator, sans clé, sans quota strict).
    Batch de 5000 chars max par requête.
    """
    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        return None

    results = list(texts)
    indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 5]
    if not indices:
        return results

    try:
        translator = GoogleTranslator(source="en", target="fr")
        ok = 0
        for i in indices:
            translated = translator.translate(texts[i][:500])
            if translated and translated != texts[i]:
                results[i] = translated
                ok += 1
        if ok > 0:
            return results
    except Exception as e:
        print(f"  [GOOGLE] Erreur: {e}")
    return None


def _translate_via_libretranslate(texts: list[str]) -> list[str] | None:
    """
    Traduit via LibreTranslate (instance publique gratuite, sans clé).
    Plusieurs instances publiques en fallback.
    """
    instances = [
        "https://libretranslate.com",
        "https://translate.argosopentech.com",
        "https://translate.terraprint.co",
    ]
    results = list(texts)
    indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 5]
    if not indices:
        return results

    for base_url in instances:
        try:
            ok = 0
            for i in indices:
                resp = requests.post(
                    f"{base_url}/translate",
                    json={"q": texts[i][:500], "source": "en", "target": "fr", "format": "text"},
                    timeout=10,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code == 200:
                    translated = resp.json().get("translatedText", "")
                    if translated and translated != texts[i]:
                        results[i] = translated
                        ok += 1
                elif resp.status_code in (429, 403):
                    break  # rate limit sur cette instance
                time.sleep(0.1)
            if ok > 0:
                print(f"  [LIBRETRANSLATE] OK via {base_url} ({ok}/{len(indices)} textes)")
                return results
        except Exception as e:
            print(f"  [LIBRETRANSLATE] {base_url} indisponible: {e}")
            continue
    return None


def _translate_via_mymemory(texts: list[str]) -> list[str] | None:
    """
    Traduit une liste via MyMemory séquentiellement avec délai fixe.
    Séquentiel pour éviter le rate-limit (5000 mots/jour, ~1 req/s conseillé).
    """
    results = list(texts)
    indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 5]
    if not indices:
        return results

    ok = 0
    for pos, i in enumerate(indices):
        if pos > 0:
            time.sleep(0.3)  # délai fixe entre requêtes
        translated = _translate_one_mymemory(texts[i])
        results[i] = translated
        if translated != texts[i]:
            ok += 1

    # Retourner même si seulement quelques traductions ont réussi
    return results if ok > 0 else None


def _translate_via_ollama(texts: list[str]) -> list[str] | None:
    """Traduit via Ollama local (mistral:latest) — fallback hors CI."""
    numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(texts))
    prompt = (
        f"Translate the following {len(texts)} texts to French. "
        "Keep proper nouns, brand names, and technical terms (AI, LLM, GPU, API) unchanged. "
        "Reply ONLY with a JSON array of translated strings, same order, no markdown.\n\n"
        f"{numbered}"
    )
    try:
        resp = requests.post(
            f"{_OLLAMA_URL}/api/generate",
            json={"model": _OLLAMA_MODEL, "prompt": prompt, "stream": False,
                  "options": {"temperature": 0.1, "num_predict": 4096}},
            timeout=120,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "").strip()
        # Extraire le JSON array
        start, end = raw.find("["), raw.rfind("]")
        if start != -1 and end != -1:
            import json
            result = json.loads(raw[start:end+1])
            if isinstance(result, list) and len(result) == len(texts):
                return result
    except Exception as e:
        print(f"  [TRANSLATE] Ollama erreur: {e}")
    return None


def translate_batch(texts: list[str]) -> list[str]:
    """
    Traduit une liste EN→FR. Gratuit, sans clé.
    Priorité : CTranslate2 GPU local → MyMemory (CI + local) → Ollama local.
    """
    indices = [i for i, t in enumerate(texts) if t and len(t.strip()) > 5 and not _is_likely_french(t)]
    if not indices:
        return texts  # Tout est déjà en français ou vide

    to_translate = [texts[i][:400] for i in indices]

    # 1. CTranslate2 local (GPU NVIDIA — ultra rapide, hors CI)
    try:
        from translator_local import translate_local, is_available
        if is_available():
            result = translate_local(to_translate)
            if result:
                print(f"  [TRANSLATE] OK via CTranslate2 GPU ({len(to_translate)} textes)")
                out = list(texts)
                for pos, idx in enumerate(indices):
                    out[idx] = result[pos] if result[pos] else texts[idx]
                return out
    except ImportError:
        pass

    # 2. Google Translate (deep-translator, sans clé — CI + local)
    # 3. LibreTranslate (instances publiques — sans quota)
    # 4. MyMemory (CI + local fallback — gratuit, sans clé)
    # 5. Ollama local (fallback final)
    for name, fn in [("Google",         _translate_via_google),
                     ("LibreTranslate", _translate_via_libretranslate),
                     ("MyMemory",       _translate_via_mymemory),
                     ("Ollama",         _translate_via_ollama)]:
        result = fn(to_translate)
        if result:
            print(f"  [TRANSLATE] OK via {name} ({len(to_translate)} textes)")
            out = list(texts)
            for pos, idx in enumerate(indices):
                out[idx] = result[pos] if result[pos] else texts[idx]
            return out

    print("  [TRANSLATE] Tous les backends ont échoué — textes non traduits")
    return texts


def translate_articles(articles: list[dict]) -> list[dict]:
    """
    Traduit titres et résumés en batch.
    Intercale titres et résumés pour répartir le quota MyMemory équitablement.
    100% gratuit — CTranslate2 GPU local → MyMemory en CI → Ollama local.
    """
    if not articles:
        return articles

    BATCH = 20

    # Intercaler titre/résumé pour que le quota soit partagé
    # Format: [(index_article, "title"|"summary", texte), ...]
    all_texts = []
    for i, a in enumerate(articles):
        all_texts.append((i, "title", a.get("title", "")))
        all_texts.append((i, "summary", a.get("summary", "")))

    # Traduire par batch
    translated = {}
    for start in range(0, len(all_texts), BATCH):
        batch = all_texts[start:start + BATCH]
        texts_only = [t[2] for t in batch]
        result = translate_batch(texts_only)
        for (idx, field, _orig), trad in zip(batch, result):
            translated[(idx, field)] = trad

    # Réassigner
    for i, art in enumerate(articles):
        art["title"]   = translated.get((i, "title"),   art.get("title", ""))
        art["summary"] = translated.get((i, "summary"), art.get("summary", ""))

    n_titles = sum(1 for i in range(len(articles)) if translated.get((i, "title"), "") != articles[i].get("title", ""))
    print(f"  [TRANSLATE] Terminé — {len(articles)} articles traités")
    return articles

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
    # Reddit — subreddits IA (filtrés par keywords)
    ("Reddit — MachineLearning", "https://www.reddit.com/r/MachineLearning/.rss"),
    ("Reddit — LocalLLaMA",      "https://www.reddit.com/r/LocalLLaMA/.rss"),
    ("Reddit — ArtificialIntel", "https://www.reddit.com/r/artificial/.rss"),
    ("Reddit — ChatGPT",         "https://www.reddit.com/r/ChatGPT/.rss"),
    ("Reddit — Singularity",     "https://www.reddit.com/r/singularity/.rss"),
    ("Reddit — vibecoding",      "https://www.reddit.com/r/vibecoding/.rss"),
    ("Reddit — ClaudeAI",        "https://www.reddit.com/r/ClaudeAI/.rss"),
    ("Reddit — OpenAI",          "https://www.reddit.com/r/OpenAI/.rss"),
    ("Reddit — Gemini",          "https://www.reddit.com/r/Gemini/.rss"),
    ("Reddit — CursorAI",        "https://www.reddit.com/r/cursor/.rss"),
    ("Reddit — GithubCopilot",   "https://www.reddit.com/r/GithubCopilot/.rss"),
    ("Reddit — AIAssistants",    "https://www.reddit.com/r/AIAssistants/.rss"),
    ("Reddit — LLMDevs",         "https://www.reddit.com/r/LLMDevs/.rss"),
    ("Reddit — Ollama",          "https://www.reddit.com/r/ollama/.rss"),
]

# ── Flux RSS non filtrés (tout passe — sources 100% IA/tech) ─────────────
RSS_FEEDS_UNFILTERED = [
    # Blogs FR tech/IA
    ("Korben",                  "https://korben.info/feed"),
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
        title = _clean_html((item.findtext("title") or "").strip())
        link  = (item.findtext("link")  or "").strip()
        desc  = _clean_html((item.findtext("description") or "").strip())
        pub   = _normalize_date(item.findtext("pubDate") or "")
        if not filtered or _is_relevant(title + " " + desc):
            items.append({"title": title, "link": link,
                          "summary": desc[:400], "date": pub, "source": name})

    for entry in root.findall("atom:entry", ns):
        title   = _clean_html((entry.findtext("atom:title", namespaces=ns) or "").strip())
        link_el = entry.find("atom:link", ns)
        link    = link_el.get("href", "") if link_el is not None else ""
        # atom:summary en priorité, atom:content en fallback (Reddit)
        summary = _clean_html((entry.findtext("atom:summary", namespaces=ns) or "").strip())
        if not summary:
            summary = _clean_html((entry.findtext("atom:content", namespaces=ns) or "").strip())
        pub     = _normalize_date(entry.findtext("atom:updated", namespaces=ns) or "")
        if not filtered or _is_relevant(title + " " + summary):
            items.append({"title": title, "link": link,
                          "summary": summary[:400], "date": pub, "source": name})

    items.sort(key=lambda x: _parse_date(x["date"]), reverse=True)
    return items[:max_items]


def fetch_rss(name: str, url: str, max_items: int = 5, filtered: bool = True) -> list[dict]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        return _parse_feed(root, name, filtered=filtered, max_items=max_items)
    except Exception as e:
        print(f"  [RSS] Erreur {name}: {e}")
        return []


def fetch_hn_algolia(query: str, max_items: int = 8) -> list[dict]:
    try:
        url = f"https://hn.algolia.com/api/v1/search_by_date?query={quote_plus(query)}&tags=story&hitsPerPage={max_items}"
        resp = requests.get(url, headers=HEADERS, timeout=8)
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
        results = []
        for h in hits:
            title = _clean_html((h.get("title") or "").strip())
            link  = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID','')}"
            if title:
                results.append({
                    "title": title,
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

    # Paralléliser toutes les requêtes RSS + HN
    print("  → Collecte parallèle (RSS + HN)...")
    tasks = []
    for name, url in RSS_FEEDS_FILTERED:
        tasks.append(("rss_filtered", name, url))
    for name, url in RSS_FEEDS_UNFILTERED:
        tasks.append(("rss_unfiltered", name, url))
    for q in hn_queries:
        tasks.append(("hn", q, None))

    def _run_task(task):
        kind, a, b = task
        if kind == "rss_filtered":
            arts = fetch_rss(a, b, max_items=5, filtered=True)
            print(f"     {a}: {len(arts)} article(s)")
            return arts
        elif kind == "rss_unfiltered":
            arts = fetch_rss(a, b, max_items=10, filtered=False)
            print(f"     {a}: {len(arts)} article(s)")
            return arts
        else:  # hn
            arts = fetch_hn_algolia(a, max_items=5)
            print(f"     HN '{a}': {len(arts)} article(s)")
            return arts

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(_run_task, t): t for t in tasks}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result())
            except Exception as e:
                print(f"  [TASK] Erreur: {e}")

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

    # Traduction batch FR gratuite via MyMemory (après déduplication)
    unique = translate_articles(unique)

    return unique