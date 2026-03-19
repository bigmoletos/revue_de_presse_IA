"""
Publication de la revue de presse sur GitHub Gist.
Crée un nouveau Gist chaque jour, ou met à jour le Gist existant du jour.
Nécessite GITHUB_TOKEN dans .env (token avec scope 'gist').
"""
import json
import os
import requests
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

from config import GITHUB_TOKEN, GIST_PUBLIC

try:
    from zoneinfo import ZoneInfo
    _TZ_PARIS = ZoneInfo("Europe/Paris")
except ImportError:
    _TZ_PARIS = timezone(timedelta(hours=1))

def _today_paris() -> date:
    return datetime.now(_TZ_PARIS).date()

_GIST_ID_FILE = Path(os.environ.get("USERPROFILE", os.environ.get("HOME", "/tmp"))) / "dev" / "revue_presse_ia" / ".gist_ids.json"
_API = "https://api.github.com"


def _load_gist_ids() -> dict:
    if _GIST_ID_FILE.exists():
        try:
            return json.loads(_GIST_ID_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_gist_ids(ids: dict):
    _GIST_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GIST_ID_FILE.write_text(json.dumps(ids, indent=2), encoding="utf-8")


def publish_gist(html_content: str, article_count: int) -> str | None:
    """
    Publie le rapport HTML sur GitHub Gist.
    Retourne l'URL du Gist, ou None si échec / token absent.
    """
    if not GITHUB_TOKEN:
        print("[GIST] GITHUB_TOKEN non défini — skip publication")
        return None

    today = _today_paris().strftime("%Y-%m-%d")
    filename = f"revue_ia_{today}.html"
    description = f"Revue IA — {today} ({article_count} articles)"

    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    gist_ids = _load_gist_ids()
    existing_id = gist_ids.get(today)

    try:
        payload = {
            "description": description,
            "public": GIST_PUBLIC,
            "files": {filename: {"content": html_content}},
        }

        if existing_id:
            # Mise à jour du Gist existant
            resp = requests.patch(
                f"{_API}/gists/{existing_id}",
                headers=headers,
                json=payload,
                timeout=15,
            )
        else:
            # Création d'un nouveau Gist
            resp = requests.post(
                f"{_API}/gists",
                headers=headers,
                json=payload,
                timeout=15,
            )

        resp.raise_for_status()
        data = resp.json()
        gist_id   = data.get("id", "")
        raw_url   = next(iter(data.get("files", {}).values()), {}).get("raw_url", "")
        # URL de preview HTML rendu (htmlpreview.github.io)
        preview_url = f"https://htmlpreview.github.io/?{raw_url.split('?')[0]}" if raw_url else data.get("html_url", "")

        # Sauvegarder l'ID pour les mises à jour du jour
        gist_ids[today] = gist_id
        _save_gist_ids(gist_ids)

        action = "mis à jour" if existing_id else "créé"
        print(f"[GIST] Gist {action}: {preview_url}")
        return preview_url

    except requests.HTTPError as e:
        print(f"[GIST] Erreur HTTP {e.response.status_code}: {e.response.text[:200]}")
        return None
    except Exception as e:
        print(f"[GIST] Erreur: {e}")
        return None
