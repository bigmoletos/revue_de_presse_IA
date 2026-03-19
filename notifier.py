"""
Notification Windows (toast WinRT) + sauvegarde HTML locale.
Utilise PowerShell WinRT directement — aucune dépendance Python externe.
"""
import os
import subprocess
from pathlib import Path
from datetime import datetime, date, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    _TZ_PARIS = ZoneInfo("Europe/Paris")
except ImportError:
    _TZ_PARIS = timezone(timedelta(hours=1))

def _today_paris() -> date:
    return datetime.now(_TZ_PARIS).date()


def save_html_report(articles: list[dict]) -> Path:
    """Sauvegarde la revue en HTML dans ~/dev/revue_presse_ia/rapports/."""
    from mailer import build_html
    today = _today_paris().strftime("%Y-%m-%d")
    out_dir = Path(os.environ["USERPROFILE"]) / "dev" / "revue_presse_ia" / "rapports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"revue_{today}.html"
    out_file.write_text(build_html(articles), encoding="utf-8")
    return out_file


def _toast_ps(title: str, message: str) -> str:
    """Génère le script PowerShell pour afficher un toast WinRT."""
    # Échapper les apostrophes pour PowerShell
    t = title.replace("'", "`'")
    m = message.replace("'", "`'")
    return f"""
$ErrorActionPreference = 'SilentlyContinue'
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime]
$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template)
$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{t}')) | Out-Null
$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{m}')) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Revue Presse IA').Show($toast)
Start-Sleep -Seconds 1
"""


def notify_toast(title: str, message: str):
    """Affiche un toast Windows natif via PowerShell WinRT."""
    try:
        ps_script = _toast_ps(title, message)
        result = subprocess.run(
            ["pwsh", "-ExecutionPolicy", "Bypass", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            print("[NOTIFIER] Toast affiché")
        else:
            print(f"[NOTIFIER] Toast pwsh erreur: {result.stderr[:200]}")
    except Exception as e:
        print(f"[NOTIFIER] Toast échec: {e}")


def deliver(articles: list[dict]) -> bool:
    """Sauvegarde HTML + Gist + toast + ouverture navigateur."""
    try:
        html_path = save_html_report(articles)
        html_content = html_path.read_text(encoding="utf-8")
        today = _today_paris().strftime("%d/%m/%Y")

        # Publication Gist (optionnelle — silencieuse si pas de token)
        from gist_publisher import publish_gist
        gist_url = publish_gist(html_content, len(articles))

        msg = f"{len(articles)} articles collectés."
        if gist_url:
            msg += f" Publié sur Gist."

        notify_toast(
            title=f"Revue IA — {today}",
            message=msg,
        )
        os.startfile(str(html_path))
        print(f"[NOTIFIER] Rapport: {html_path}")
        if gist_url:
            print(f"[NOTIFIER] Gist: {gist_url}")
        return True
    except Exception as e:
        print(f"[NOTIFIER] Erreur: {e}")
        return False
