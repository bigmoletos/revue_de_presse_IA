"""
Point d'entrée CI/CD — GitHub Actions.
Sans Flask, sans APScheduler, sans dépendances Windows.
Collecte → HTML → GitHub Pages (branche gh-pages).
"""
import os
import sys
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

# Fuseau Paris — datetime.now(TZ_PARIS).date() est toujours correct (heure d'été incluse)
try:
    from zoneinfo import ZoneInfo
    TZ_PARIS = ZoneInfo("Europe/Paris")
except ImportError:
    TZ_PARIS = timezone(timedelta(hours=1))

def _today_paris() -> date:
    return datetime.now(TZ_PARIS).date()

# Charger le .env local si présent (dev local), sinon utiliser les vars CI
_env = Path(__file__).parent / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=True)
    except ImportError:
        pass

from scraper import collect_news
from mailer import build_html, send_email, SMTPAuthError
from pages_publisher import publish_to_pages


def main():
    print("=== Revue de Presse IA ===")

    # 1. Collecte
    articles = collect_news()
    print(f"Articles collectés: {len(articles)}")
    if not articles:
        print("Aucun article — arrêt.")
        sys.exit(1)

    # 2. Génération HTML
    html = build_html(articles)
    today = _today_paris().strftime("%Y-%m-%d")

    # 3. Sauvegarde locale (optionnelle en CI)
    out_dir = Path(__file__).parent / "rapports"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"revue_{today}.html"
    out_file.write_text(html, encoding="utf-8")
    print(f"Rapport local: {out_file}")

    # 4. Publication GitHub Pages
    pages_url = publish_to_pages(html, len(articles))
    if pages_url:
        print(f"Pages: {pages_url}")
        # GitHub Actions — écrire dans le summary
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write(f"## Revue IA — {today}\n\n")
                f.write(f"- **{len(articles)} articles** collectés\n")
                f.write(f"- **Rapport**: [{pages_url}]({pages_url})\n")
    else:
        print("[WARN] GitHub Pages non publié — GITHUB_TOKEN manquant ou erreur")
        sys.exit(1)

    # 5. Envoi email
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    try:
        email_ok = send_email(articles, pages_url=pages_url or "")
        if email_ok:
            print("Email envoyé")
        else:
            print("[WARN] Email non envoyé (SMTP non configuré ou indisponible)")
    except SMTPAuthError as e:
        print(f"[ERREUR] Authentification SMTP refusée par Gmail: {e}")
        print("Le mot de passe d'application Gmail (secret SMTP_PASSWORD) est "
              "invalide ou expiré. Regenere-le sur "
              "https://myaccount.google.com/apppasswords puis mets a jour le "
              "secret sur "
              "https://github.com/bigmoletos/revue_de_presse_IA/settings/secrets/actions")
        if summary:
            with open(summary, "a", encoding="utf-8") as f:
                f.write("## Echec envoi email\n\n")
                f.write(
                    "L'authentification SMTP Gmail a echoue. Le mot de passe "
                    "d'application est probablement invalide ou expire.\n\n"
                )
                f.write(
                    "- Regenerer : "
                    "[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)\n"
                )
                f.write(
                    "- Mettre a jour le secret `SMTP_PASSWORD` : "
                    "[Secrets Actions](https://github.com/bigmoletos/revue_de_presse_IA/settings/secrets/actions)\n"
                )
        # Le rapport Pages a bien été publié — seul l'email a échoué.
        # On fait échouer le job pour que ce soit visible (au lieu d'un succès silencieux).
        sys.exit(2)


if __name__ == "__main__":
    main()
