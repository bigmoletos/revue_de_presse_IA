"""
Generation HTML de la revue de presse + envoi email (SMTP).
Fallback silencieux si SMTP indisponible (reseau HPS).
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import date

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_TO

THEMES = {
    "Assistants et Agents IA": ["agent", "copilot", "cursor", "kiro", "windsurf", "agentic", "assistant"],
    "Modeles et LLM":          ["llm", "gpt", "claude", "gemini", "codestral", "mistral", "model"],
    "Vibe Coding":             ["vibe cod", "vibe-cod", "vibecod"],
    "Generation de code":      ["code generation", "code gen", "ai cod", "coding ai"],
    "Entreprise et Industrie": ["enterprise", "large project", "production", "deploy"],
    "Autres":                  [],
}


def _assign_theme(article):
    text = (article.get("title", "") + " " + article.get("summary", "")).lower()
    for theme, keywords in THEMES.items():
        if theme == "Autres":
            continue
        if any(kw in text for kw in keywords):
            return theme
    return "Autres"


def build_html(articles):
    today_label = date.today().strftime("%d/%m/%Y")
    for art in articles:
        art["_theme"] = _assign_theme(art)

    raw_dates = sorted(
        {art.get("date", "")[:10] for art in articles if art.get("date", "")[:10]},
        reverse=True,
    )
    date_options = "\n".join(
        f'<option value="{d}">{d}</option>' for d in raw_dates
    )

    grouped = {t: [] for t in THEMES}
    for art in articles:
        grouped[art["_theme"]].append(art)

    nav_links = "\n".join(
        f'<a href="#{t.replace(" ", "-")}" class="nav-link">{t} ({len(grouped[t])})</a>'
        for t in THEMES if grouped[t]
    )

    sections_html = ""
    for theme, arts in grouped.items():
        if not arts:
            continue
        anchor = theme.replace(" ", "-")
        cards = ""
        for art in arts:
            title    = art.get("title", "Sans titre")
            link     = art.get("link", "#")
            summary  = art.get("summary", "")
            source   = art.get("source", "")
            art_date = art.get("date", "")[:10]
            summary_html = f"<p class='card-summary'>{summary}</p>" if summary else ""
            date_html    = f"<span class='art-date'>{art_date}</span>" if art_date else ""
            cards += f"""
        <div class="card" data-date="{art_date}" data-text="{title.lower()} {summary.lower()}">
          <div class="card-header">
            <a href="{link}" target="_blank" rel="noopener" class="card-title">{title}</a>
          </div>
          {summary_html}
          <div class="card-meta">
            <span class="source">{source}</span>
            {date_html}
            <a href="{link}" target="_blank" rel="noopener" class="read-link">Lire l article</a>
          </div>
        </div>"""
        sections_html += f"""
      <section id="{anchor}" class="theme-section">
        <h2 class="theme-title">{theme}</h2>
        {cards}
      </section>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revue IA - {today_label}</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--accent:#7c6af7;--text:#e2e8f0;--muted:#8892a4;--green:#4ade80;--card-bg:#1e2130}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:100;background:var(--surface);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:16px;flex-wrap:wrap}}
header h1{{font-size:1.1rem;color:var(--accent);white-space:nowrap}}
#count{{font-size:.85rem;color:var(--muted)}}
#search{{flex:1;min-width:180px;padding:6px 12px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.9rem}}
#dateFilter{{padding:6px 10px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.9rem}}
nav{{background:var(--surface);border-bottom:1px solid var(--border);padding:8px 24px;display:flex;gap:12px;flex-wrap:wrap}}
.nav-link{{color:var(--muted);text-decoration:none;font-size:.82rem;padding:3px 8px;border-radius:4px;border:1px solid var(--border)}}
.nav-link:hover{{color:var(--accent);border-color:var(--accent)}}
main{{max-width:960px;margin:0 auto;padding:24px 16px}}
.theme-section{{margin-bottom:40px}}
.theme-title{{font-size:1rem;font-weight:600;color:var(--accent);border-left:3px solid var(--accent);padding-left:10px;margin-bottom:16px}}
.card{{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;padding:14px 16px;margin-bottom:12px}}
.card:hover{{border-color:var(--accent)}}
.card-title{{color:var(--text);text-decoration:none;font-size:.95rem;font-weight:500;line-height:1.4}}
.card-title:hover{{color:var(--accent)}}
.card-summary{{color:var(--muted);font-size:.85rem;margin-top:8px;line-height:1.5}}
.card-meta{{display:flex;align-items:center;gap:12px;margin-top:10px;font-size:.78rem;flex-wrap:wrap}}
.source{{color:var(--green)}}.art-date{{color:var(--muted)}}
.read-link{{color:var(--accent);text-decoration:none;margin-left:auto}}
.read-link:hover{{text-decoration:underline}}
.hidden{{display:none!important}}
.no-results{{color:var(--muted);text-align:center;padding:40px;font-size:.9rem}}
</style>
</head>
<body>
<header>
  <h1>Revue IA - {today_label}</h1>
  <span id="count">{len(articles)} articles</span>
  <input id="search" type="search" placeholder="Rechercher..." oninput="applyFilters()"/>
  <select id="dateFilter" onchange="applyFilters()">
    <option value="">Toutes les dates</option>
    {date_options}
  </select>
</header>
<nav>{nav_links}</nav>
<main id="main">
  {sections_html}
  <p id="noResults" class="no-results hidden">Aucun article ne correspond.</p>
</main>
<script>
function applyFilters(){{
  var q=document.getElementById('search').value.toLowerCase().trim();
  var d=document.getElementById('dateFilter').value;
  var cards=document.querySelectorAll('.card');
  var visible=0;
  cards.forEach(function(card){{
    var match=(!q||card.dataset.text.includes(q))&&(!d||card.dataset.date===d);
    card.classList.toggle('hidden',!match);
    if(match)visible++;
  }});
  document.querySelectorAll('.theme-section').forEach(function(sec){{
    sec.classList.toggle('hidden',sec.querySelectorAll('.card:not(.hidden)').length===0);
  }});
  document.getElementById('count').textContent=visible+' article'+(visible>1?'s':'');
  document.getElementById('noResults').classList.toggle('hidden',visible>0);
}}
</script>
</body>
</html>"""


def send_email(articles):
    """Envoie la revue par email SMTP. Retourne False si SMTP indisponible."""
    if not all([SMTP_USER, SMTP_PASSWORD, MAIL_TO]):
        print("[MAILER] Config SMTP incomplete - skip email")
        return False
    try:
        html = build_html(articles)
        today_label = date.today().strftime("%d/%m/%Y")
        subject = f"Revue IA - {today_label} ({len(articles)} articles)"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = MAIL_TO
        msg.attach(MIMEText(html, "html", "utf-8"))
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, MAIL_TO.split(","), msg.as_string())
        print(f"[MAILER] Email envoye a {MAIL_TO}")
        return True
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        print(f"[MAILER] SMTP indisponible ({e}) - fallback rapport HTML")
        return False
    except Exception as e:
        print(f"[MAILER] Erreur inattendue: {e}")
        return False
