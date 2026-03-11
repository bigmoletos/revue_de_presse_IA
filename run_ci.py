"""
Point d'entrée CI/CD — GitHub Actions.
Sans Flask, sans APScheduler, sans dépendances Windows.
Collecte → HTML → GitHub Pages (branche gh-pages).
"""
import os
import sys
from pathlib import Path
from datetime import date

# Charger le .env local si présent (dev local), sinon utiliser les vars CI
_env = Path(__file__).parent / ".env"
if _env.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env, override=True)
    except ImportError:
        pass

from scraper import collect_news
from mailer import build_html, send_email
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
    today = date.today().strftime("%Y-%m-%d")

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
    email_ok = send_email(articles)
    if email_ok:
        print("Email envoyé")
    else:
        print("[WARN] Email non envoyé (SMTP indisponible ou config incomplète)")


if __name__ == "__main__":
    main()
