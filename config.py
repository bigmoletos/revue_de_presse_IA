"""Configuration — chargée depuis les variables d'environnement ou .env local."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=True)
except ImportError:
    pass  # En CI, les vars viennent directement des secrets GitHub

# Email
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_TO       = os.getenv("MAIL_TO", "")   # destinataire(s), séparés par virgule

# GitHub Gist
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")
GIST_PUBLIC     = os.getenv("GIST_PUBLIC", "false").lower() == "true"

# Planification
CRON_HOUR   = int(os.getenv("CRON_HOUR", "7"))
CRON_MINUTE = int(os.getenv("CRON_MINUTE", "30"))
