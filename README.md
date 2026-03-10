# Revue de Presse IA

Pipeline automatise de veille technologique IA — collecte, traduction FR, publication HTML.

**URL publique** : https://bigmoletos.github.io/revue_de_presse_IA/

---

## Fonctionnement

1. Collecte RSS (The Verge, Ars Technica, VentureBeat, Simon Willison, TDS, Dev.to) + Hacker News
2. Deduplication par URL et titre
3. Traduction automatique FR via Google Translate (deep-translator, sans cle API)
4. Generation rapport HTML dark-theme avec recherche et filtre par date
5. Publication sur GitHub Pages (branche `gh-pages`)

Execution automatique : **lundi au vendredi a 7h30 (UTC+1)**

---

## Structure

```
revue_de_presse_IA/
├── scraper.py          # Collecte RSS + HN Algolia
├── mailer.py           # Generation HTML
├── config.py           # Configuration (charge .env)
├── run_ci.py           # Point d'entree CI/CD
├── pages_publisher.py  # Publication GitHub Pages (branche gh-pages)
├── notifier.py         # Notifications Windows (toast WinRT)
├── app.py              # Serveur Flask (usage local uniquement)
├── requirements.txt    # Dependances Python
├── .env.example        # Template variables d'environnement
└── .github/
    └── workflows/
        └── revue-presse-ia.yml  # GitHub Actions workflow
```

---

## Configuration GitHub

### 1. Secret GitHub Actions

Aller dans : **Settings > Secrets and variables > Actions > New repository secret**

| Nom | Valeur |
|-----|--------|
| `REVUE_GITHUB_TOKEN` | Token GitHub avec scope `repo` (pour push sur gh-pages) |

Creer le token : https://github.com/settings/tokens
- Scopes requis : `repo` (full control)

### 2. GitHub Pages

Aller dans : **Settings > Pages**

| Parametre | Valeur |
|-----------|--------|
| Source | `Deploy from a branch` |
| Branch | `gh-pages` |
| Folder | `/ (root)` |

La branche `gh-pages` est creee automatiquement au premier run du workflow.

URL resultante : `https://bigmoletos.github.io/revue_de_presse_IA/`

### 3. GitHub Actions

Workflow : `.github/workflows/revue-presse-ia.yml`

Permissions requises (deja configurees dans le workflow) :
```yaml
permissions:
  contents: write   # push sur gh-pages
  pages: write      # publication GitHub Pages
  id-token: write   # authentification OIDC
```

Declenchement :
- **Automatique** : lundi-vendredi a 06h30 UTC (= 07h30 Paris)
- **Manuel** : onglet Actions > "Revue de Presse IA" > "Run workflow"

---

## Variables d'environnement

Copier `.env.example` en `.env` et remplir :

```env
GITHUB_TOKEN=ghp_...        # Token avec scope repo (pour push gh-pages en local)
GITHUB_REPOSITORY=bigmoletos/revue_de_presse_IA
```

En CI (GitHub Actions), `GITHUB_TOKEN` est injecte via le secret `REVUE_GITHUB_TOKEN`.

---

## Installation locale

```bash
# Cloner
git clone https://github.com/bigmoletos/revue_de_presse_IA.git
cd revue_de_presse_IA

# Installer les dependances (Python 3.11+)
pip install -r requirements.txt

# Configurer
cp .env.example .env
# Editer .env avec votre GITHUB_TOKEN

# Lancer
python run_ci.py
```

Le rapport HTML est genere dans `rapports/revue_YYYY-MM-DD.html`.

---

## Lancement manuel du workflow

```bash
# Via GitHub CLI
gh workflow run revue-presse-ia.yml

# Ou depuis l'interface web
# https://github.com/bigmoletos/revue_de_presse_IA/actions
```

---

## Troubleshooting

| Probleme | Cause | Solution |
|----------|-------|----------|
| `403 Write access not granted` | Token sans scope `repo` | Regenerer le token avec scope `repo` |
| `GITHUB_TOKEN manquant` | Secret non configure | Ajouter `REVUE_GITHUB_TOKEN` dans Settings > Secrets |
| Pages non activees | GitHub Pages desactive | Settings > Pages > activer sur branche `gh-pages` |
| Aucun article collecte | Sources RSS indisponibles | Verifier la connectivite, relancer manuellement |