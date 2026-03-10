"""
Revue de presse IA quotidienne — Flask + APScheduler
Déclenche chaque matin une collecte Perplexity et envoie un email.
"""
from flask import Flask, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import atexit
import logging
from datetime import datetime

from config import CRON_HOUR, CRON_MINUTE
from scraper import collect_news
from mailer import send_email
from notifier import deliver

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

app = Flask(__name__)


def run_daily_digest():
    """Tâche planifiée : collecte + email (fallback: rapport HTML local)."""
    log.info("=== Démarrage revue de presse IA ===")
    try:
        articles = collect_news()
        log.info(f"{len(articles)} sujets collectés")
        ok = send_email(articles)
        if ok:
            log.info("Email envoyé")
        else:
            log.info("SMTP indisponible — ouverture rapport HTML local")
            deliver(articles)
    except Exception as e:
        log.error(f"Erreur revue de presse: {e}")


# ── Scheduler ──────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler(timezone="Europe/Paris")
scheduler.add_job(
    run_daily_digest,
    trigger=CronTrigger(hour=CRON_HOUR, minute=CRON_MINUTE),
    id="daily_digest",
    replace_existing=True,
)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())
log.info(f"Scheduler démarré — déclenchement quotidien à {CRON_HOUR:02d}h{CRON_MINUTE:02d}")


# ── Routes ──────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


@app.route("/run", methods=["POST"])
def trigger_now():
    """Déclenche la revue manuellement (test / rattrapage)."""
    log.info("Déclenchement manuel via /run")
    run_daily_digest()
    return jsonify({"status": "done"})


@app.route("/next")
def next_run():
    """Affiche la prochaine exécution planifiée."""
    job = scheduler.get_job("daily_digest")
    next_fire = str(job.next_run_time) if job else "N/A"
    return jsonify({"next_run": next_fire})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
