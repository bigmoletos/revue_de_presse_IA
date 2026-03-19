"""
Generation HTML de la revue de presse + envoi email (SMTP).
Fallback silencieux si SMTP indisponible (reseau HPS).
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, date, timedelta, timezone

from config import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, MAIL_TO
from scraper import detect_theme

# Fuseau Paris (UTC+1 hiver / UTC+2 été) — datetime.now(TZ_PARIS) est toujours correct
try:
    from zoneinfo import ZoneInfo
    TZ_PARIS = ZoneInfo("Europe/Paris")
except ImportError:
    # Python < 3.9 fallback : offset fixe UTC+1 (acceptable pour un cron matin)
    TZ_PARIS = timezone(timedelta(hours=1))

def _today_paris() -> date:
    """Date du jour à Paris (pas UTC) — évite le décalage heure d'été."""
    return datetime.now(TZ_PARIS).date()

# Ordre d'affichage des thèmes
THEME_ORDER = [
    "Vibe Coding",
    "Assistants et Agents IA",
    "Audio et Voix IA",
    "Modeles et LLM",
    "GPU et Hardware",
    "Startups et Financement",
    "Entreprise et Industrie",
    "Autres",
]


def _assign_theme(article):
    text = (article.get("title", "") + " " + article.get("summary", "")).lower()
    return detect_theme(text)


def _short_title(title: str) -> str:
    """Extrait 3 mots significatifs du titre comme label court."""
    stop = {"the","a","an","of","in","on","at","to","for","and","or","is","are",
            "with","by","from","as","its","it","this","that","how","why","what",
            "new","le","la","les","un","une","des","du","de","en","et","ou","au"}
    words = [w for w in title.split() if w.lower().strip(".,:-") not in stop and len(w) > 2]
    return " ".join(words[:3]) if words else title[:30]


def build_html(articles, pages_url: str = ""):
    today_label = _today_paris().strftime("%d/%m/%Y")
    for art in articles:
        art["_theme"] = _assign_theme(art)
        art["_slug"]  = _short_title(art.get("title", ""))

    raw_dates = sorted(
        {art.get("date", "") for art in articles if art.get("date", "")},
        reverse=True,
    )
    date_options = "\n".join(
        f'<option value="{d}">{d}</option>' for d in raw_dates
    )

    grouped = {t: [] for t in THEME_ORDER}
    for art in articles:
        theme = art["_theme"]
        if theme not in grouped:
            grouped[theme] = []
        grouped[theme].append(art)

    # Nav thèmes
    nav_links = "\n".join(
        f'<a href="#{t.replace(" ", "-")}" class="nav-link">{t} <span class="badge">{len(grouped[t])}</span></a>'
        for t in THEME_ORDER if grouped.get(t)
    )

    # Filtre GPU rapide
    gpu_btn = '<button class="gpu-btn" onclick="filterGPU()">🖥 GPU / NVIDIA</button>'

    pages_link = f'<a href="{pages_url}" target="_blank" class="pages-link">📄 Voir sur GitHub Pages</a>' if pages_url else ""

    sections_html = ""
    for theme in THEME_ORDER:
        arts = grouped.get(theme, [])
        if not arts:
            continue
        anchor = theme.replace(" ", "-")
        cards = ""
        for art in arts:
            title    = art.get("title", "Sans titre")
            slug     = art.get("_slug", title[:30])
            link     = art.get("link", "#")
            summary  = art.get("summary", "")
            source   = art.get("source", "")
            art_date = art.get("date", "")
            summary_html = f"<p class='card-summary'>{summary}</p>" if summary else ""
            date_html    = f"<span class='art-date'>{art_date}</span>" if art_date else ""
            # Article collapsé par défaut avec slug comme label visible
            cards += f"""
        <details class="card" data-date="{art_date}" data-text="{title.lower()} {summary.lower()}" data-theme="{theme}">
          <summary class="card-summary-toggle">
            <span class="card-slug">{slug}</span>
            <span class="card-meta-inline">
              <span class="source">{source}</span>
              {date_html}
            </span>
          </summary>
          <div class="card-body">
            <a href="{link}" target="_blank" rel="noopener" class="card-title">{title}</a>
            {summary_html}
            <div class="card-meta">
              <a href="{link}" target="_blank" rel="noopener" class="read-link">→ Lire l'article</a>
            </div>
          </div>
        </details>"""

        sections_html += f"""
      <section id="{anchor}" class="theme-section">
        <h2 class="theme-title">{theme} <span class="theme-count">{len(arts)}</span></h2>
        {cards}
      </section>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Revue IA - {today_label}</title>
<style>
:root{{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--accent:#7c6af7;--text:#e2e8f0;--muted:#8892a4;--green:#4ade80;--card-bg:#1e2130;--gpu:#f59e0b}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif}}
header{{position:sticky;top:0;z-index:100;background:var(--surface);border-bottom:1px solid var(--border);padding:10px 24px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}}
header h1{{font-size:1.05rem;color:var(--accent);white-space:nowrap}}
#count{{font-size:.82rem;color:var(--muted)}}
#search{{flex:1;min-width:160px;padding:5px 10px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.88rem}}
#dateFilter{{padding:5px 8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text);font-size:.88rem}}
.gpu-btn{{padding:5px 10px;background:transparent;border:1px solid var(--gpu);border-radius:6px;color:var(--gpu);font-size:.82rem;cursor:pointer}}
.gpu-btn:hover,.gpu-btn.active{{background:var(--gpu);color:#000}}
.pages-link{{font-size:.82rem;color:var(--accent);text-decoration:none;white-space:nowrap}}
.pages-link:hover{{text-decoration:underline}}
nav{{background:var(--surface);border-bottom:1px solid var(--border);padding:7px 24px;display:flex;gap:10px;flex-wrap:wrap}}
.nav-link{{color:var(--muted);text-decoration:none;font-size:.8rem;padding:3px 8px;border-radius:4px;border:1px solid var(--border)}}
.nav-link:hover{{color:var(--accent);border-color:var(--accent)}}
.badge{{background:var(--border);border-radius:10px;padding:1px 6px;font-size:.75rem}}
main{{max-width:960px;margin:0 auto;padding:20px 16px}}
.theme-section{{margin-bottom:36px}}
.theme-title{{font-size:.95rem;font-weight:600;color:var(--accent);border-left:3px solid var(--accent);padding-left:10px;margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.theme-count{{background:var(--border);border-radius:10px;padding:1px 7px;font-size:.75rem;color:var(--muted)}}
details.card{{background:var(--card-bg);border:1px solid var(--border);border-radius:8px;margin-bottom:8px;overflow:hidden}}
details.card:hover{{border-color:var(--accent)}}
details.card[open]{{border-color:var(--accent)}}
summary.card-summary-toggle{{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;cursor:pointer;list-style:none;gap:12px}}
summary.card-summary-toggle::-webkit-details-marker{{display:none}}
summary.card-summary-toggle::before{{content:'▶';font-size:.65rem;color:var(--muted);flex-shrink:0;transition:transform .2s}}
details[open] summary.card-summary-toggle::before{{transform:rotate(90deg)}}
.card-slug{{font-size:.9rem;font-weight:500;color:var(--text);flex:1}}
.card-meta-inline{{display:flex;align-items:center;gap:10px;font-size:.75rem;flex-shrink:0}}
.source{{color:var(--green)}}.art-date{{color:var(--muted)}}
.card-body{{padding:0 14px 12px 14px;border-top:1px solid var(--border)}}
.card-title{{display:block;color:var(--accent);text-decoration:none;font-size:.88rem;margin-top:10px;line-height:1.4}}
.card-title:hover{{text-decoration:underline}}
.card-summary{{color:var(--muted);font-size:.83rem;margin-top:7px;line-height:1.5}}
.card-meta{{margin-top:8px}}
.read-link{{color:var(--accent);text-decoration:none;font-size:.8rem}}
.read-link:hover{{text-decoration:underline}}
.hidden{{display:none!important}}
.no-results{{color:var(--muted);text-align:center;padding:40px;font-size:.9rem}}
</style>
</head>
<body>
<header>
  <h1>📰 Revue IA — {today_label}</h1>
  <span id="count">{len(articles)} articles</span>
  <input id="search" type="search" placeholder="Rechercher..." oninput="applyFilters()"/>
  <select id="dateFilter" onchange="applyFilters()">
    <option value="">Toutes les dates</option>
    {date_options}
  </select>
  {gpu_btn}
  {pages_link}
</header>
<nav>{nav_links}</nav>
<main id="main">
  {sections_html}
  <p id="noResults" class="no-results hidden">Aucun article ne correspond.</p>
</main>
<script>
var gpuActive=false;
function filterGPU(){{
  gpuActive=!gpuActive;
  document.querySelector('.gpu-btn').classList.toggle('active',gpuActive);
  applyFilters();
}}
function applyFilters(){{
  var q=document.getElementById('search').value.toLowerCase().trim();
  var d=document.getElementById('dateFilter').value;
  var cards=document.querySelectorAll('details.card');
  var visible=0;
  cards.forEach(function(card){{
    var matchText=!q||(card.dataset.text||'').includes(q);
    var matchDate=!d||card.dataset.date===d;
    var matchGpu=!gpuActive||(card.dataset.theme||'').includes('GPU');
    var show=matchText&&matchDate&&matchGpu;
    card.classList.toggle('hidden',!show);
    if(show)visible++;
  }});
  document.querySelectorAll('.theme-section').forEach(function(sec){{
    sec.classList.toggle('hidden',sec.querySelectorAll('details.card:not(.hidden)').length===0);
  }});
  document.getElementById('count').textContent=visible+' article'+(visible>1?'s':'');
  document.getElementById('noResults').classList.toggle('hidden',visible>0);
}}
</script>
</body>
</html>"""


def build_email_html(articles, pages_url: str = "") -> tuple[str, int]:
    """
    Génère un HTML simple compatible email (Outlook, Gmail).
    Filtre sur les articles de la veille uniquement.
    Retourne (html, nb_articles).
    """
    yesterday = (_today_paris() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_str  = _today_paris().strftime("%Y-%m-%d")

    # Garde veille + aujourd'hui (le cron tourne tôt le matin)
    recent = [
        a for a in articles
        if a.get("date", "") in (yesterday, today_str)
    ]
    # Fallback : si rien de récent, on prend les 20 plus récents
    if not recent:
        sorted_all = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
        recent = sorted_all[:20]

    for art in recent:
        art["_theme"] = _assign_theme(art)

    grouped = {t: [] for t in THEME_ORDER}
    for art in recent:
        theme = art["_theme"]
        if theme not in grouped:
            grouped[theme] = []
        grouped[theme].append(art)

    today_label = _today_paris().strftime("%d/%m/%Y")
    pages_btn = (
        f'<tr><td align="center" style="padding:16px 0 8px;">'
        f'<a href="{pages_url}" style="background:#7c6af7;color:#fff;padding:10px 24px;'
        f'border-radius:6px;text-decoration:none;font-size:14px;font-weight:600;">'
        f'📄 Voir tous les articles sur GitHub Pages</a></td></tr>'
    ) if pages_url else ""

    sections = ""
    for theme in THEME_ORDER:
        arts = grouped.get(theme, [])
        if not arts:
            continue
        rows = ""
        for art in arts:
            title   = art.get("title", "Sans titre")
            link    = art.get("link", "#")
            summary = art.get("summary", "")
            source  = art.get("source", "")
            art_date = art.get("date", "")
            slug    = _short_title(title)
            summary_row = (
                f'<tr><td style="padding:0 16px 10px;color:#8892a4;font-size:13px;line-height:1.5;">'
                f'{summary[:200]}{"…" if len(summary) > 200 else ""}</td></tr>'
            ) if summary else ""
            rows += f"""
        <tr>
          <td style="padding:10px 16px 0;">
            <a href="{link}" style="color:#7c6af7;font-size:15px;font-weight:600;text-decoration:none;">{slug}</a>
            <span style="color:#8892a4;font-size:12px;margin-left:8px;">{source} · {art_date}</span>
          </td>
        </tr>
        {summary_row}
        <tr><td style="padding:2px 16px 8px;">
          <a href="{link}" style="color:#4ade80;font-size:12px;text-decoration:none;">→ Lire l'article</a>
        </td></tr>
        <tr><td style="border-bottom:1px solid #2a2d3a;"></td></tr>"""

        sections += f"""
      <tr><td style="padding:20px 16px 6px;">
        <span style="color:#7c6af7;font-size:13px;font-weight:700;text-transform:uppercase;
          letter-spacing:.05em;border-left:3px solid #7c6af7;padding-left:8px;">
          {theme} ({len(arts)})
        </span>
      </td></tr>
      {rows}"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f1117;font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1117;">
  <tr><td align="center" style="padding:20px 10px;">
    <table width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;
      background:#1a1d27;border-radius:10px;border:1px solid #2a2d3a;">

      <!-- Header -->
      <tr><td style="padding:24px 24px 16px;border-bottom:1px solid #2a2d3a;">
        <span style="font-size:22px;font-weight:700;color:#e2e8f0;">📰 Revue IA</span>
        <span style="font-size:14px;color:#8892a4;margin-left:12px;">{today_label}</span>
        <br><span style="font-size:13px;color:#8892a4;margin-top:4px;display:block;">
          {len(recent)} nouveautés de la veille
        </span>
      </td></tr>

      <!-- Lien Pages -->
      {pages_btn}

      <!-- Articles par thème -->
      {sections}

      <!-- Footer -->
      <tr><td style="padding:20px 24px;border-top:1px solid #2a2d3a;text-align:center;">
        <span style="color:#8892a4;font-size:12px;">
          Revue IA automatique · Généré le {today_label}
          {f' · <a href="{pages_url}" style="color:#7c6af7;">Archive complète</a>' if pages_url else ''}
        </span>
      </td></tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""
    return html, len(recent)


def send_email(articles, pages_url: str = ""):
    """Envoie la revue par email SMTP. Retourne False si SMTP indisponible.
    MAIL_TO accepte plusieurs adresses séparées par virgule ou point-virgule.
    Envoie uniquement les articles de la veille avec un HTML compatible email.
    """
    if not all([SMTP_USER, SMTP_PASSWORD, MAIL_TO]):
        print("[MAILER] Config SMTP incomplete - skip email")
        return False

    recipients = [r.strip() for r in MAIL_TO.replace(";", ",").split(",") if r.strip()]
    if not recipients:
        print("[MAILER] Aucun destinataire valide - skip email")
        return False

    try:
        html, nb = build_email_html(articles, pages_url=pages_url)
        today_label = _today_paris().strftime("%d/%m/%Y")
        subject = f"Revue IA - {today_label} ({nb} nouveautés)"
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = SMTP_USER
        msg["To"]      = ", ".join(recipients)
        msg.attach(MIMEText(html, "html", "utf-8"))
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, recipients, msg.as_string())
        print(f"[MAILER] Email envoye a {', '.join(recipients)} ({nb} articles)")
        return True
    except (smtplib.SMTPException, OSError, TimeoutError) as e:
        print(f"[MAILER] SMTP indisponible ({e}) - fallback rapport HTML")
        return False
    except Exception as e:
        print(f"[MAILER] Erreur inattendue: {e}")
        return False
