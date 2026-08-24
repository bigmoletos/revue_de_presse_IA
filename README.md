# Revue de Presse IA

Pipeline automatisé de veille technologique IA — collecte RSS + Hacker News, publication GitHub Pages, envoi email quotidien.

**URL publique** : https://bigmoletos.github.io/revue_evenement_IA/

---

## Fonctionnement

1. Collecte parallèle (ThreadPoolExecutor x10) de 22 flux RSS + 20 requêtes Hacker News Algolia
2. Déduplication par URL et titre normalisé
3. Classification thématique automatique par mots-clés sémantiques (`detect_theme`)
4. Génération rapport HTML dark-theme interactif (recherche, filtre date, filtre GPU, articles collapsés)
5. Publication sur GitHub Pages (branche `gh-pages`)
6. Envoi email SMTP — **articles de la veille uniquement**, HTML compatible Outlook/Gmail

Exécution automatique : **lundi au vendredi à 06h30 UTC (= 07h30 Paris)**

---

## Sources couvertes

### Flux RSS filtrés (keywords requis)
The Verge AI, Ars Technica, VentureBeat AI, Simon Willison, Dev.to AI, The Verge Tech, Tom's Hardware, NVIDIA Blog, Google AI Blog, OpenAI Blog, Anthropic News, Mistral AI Blog

### Flux RSS non filtrés (100% IA/tech — tout passe)
Product Hunt AI, TechCrunch AI, AI News, TechCrunch Startups, Towards Data Science, Hugging Face Blog, The Batch (DeepLearning.ai), Dev.to LLM/Cursor/Agents

### Hacker News (Algolia)
Requêtes ciblées : vibe coding, cursor AI, open source LLM, AI agents, MCP, n8n, NVIDIA GPU, AI startup launches...

---

## Thèmes de classification

| Thème | Mots-clés couverts |
|-------|--------------------|
| Vibe Coding | IDE (Cursor, Kiro, VSCode), code generation, large codebase, cursorrules, memory bank |
| Assistants et Agents IA | AI agents, LangChain, n8n, MCP, agentic workflow, automation |
| Audio et Voix IA | TTS, voice cloning, speech recognition, audio generation |
| Modèles et LLM | Open source LLM, GGUF, LoRA, fine-tuning, model releases, Ollama |
| GPU et Hardware | NVIDIA, AMD, H100, Blackwell, AI chip, data center |
| Startups et Financement | Funding rounds, product launches, new AI tools |
| Entreprise et Industrie | MLOps, AI deployment, governance, security |

---

## Structure

```
revue_de_presse_IA/
├── scraper.py           # Collecte RSS + HN Algolia (parallèle, timeout 8s)
├── mailer.py            # HTML page complète (Pages) + HTML email (veille)
├── config.py            # Configuration (charge .env ou variables CI)
├── run_ci.py            # Point d'entrée CI/CD
├── pages_publisher.py   # Publication GitHub Pages (branche gh-pages)
├── notifier.py          # Notifications Windows (toast WinRT, usage local)
├── app.py               # Serveur Flask (usage local uniquement)
├── requirements.txt     # Dépendances Python
├── .env.example         # Template variables d'environnement
└── .github/
    └── workflows/
        └── revue-presse-ia.yml  # GitHub Actions (timeout 20 min)
```

---

## Configuration GitHub

### Secrets GitHub Actions

Aller dans : **Settings > Secrets and variables > Actions > New repository secret**

| Secret | Description |
|--------|-------------|
| `REVUE_GITHUB_TOKEN` | Token GitHub scope `repo` (push gh-pages) |
| `SMTP_USER` | Adresse Gmail expéditrice |
| `SMTP_PASSWORD` | Mot de passe d'application Gmail (pas le mdp principal) |
| `MAIL_TO` | Destinataire(s) — virgule ou point-virgule pour plusieurs adresses |

Exemple `MAIL_TO` multi-destinataires :
```
adresse1@gmail.com,adresse2@example.com
```

> Pour Gmail : activer la validation en 2 étapes puis générer un **mot de passe d'application** sur https://myaccount.google.com/apppasswords

### GitHub Pages

Aller dans : **Settings > Pages**

| Paramètre | Valeur |
|-----------|--------|
| Source | `Deploy from a branch` |
| Branch | `gh-pages` |
| Folder | `/ (root)` |

---

## Email quotidien

Le mail est envoyé chaque matin après la collecte. Il contient :

- **Articles de la veille uniquement** (filtre sur date J-1)
- Fallback sur les 20 plus récents si aucun article daté d'hier
- Groupés par thème avec compteur
- Titre court (3 mots) + source + date + résumé 200 chars
- Bouton "Voir tous les articles sur GitHub Pages" en haut
- HTML compatible Outlook, Gmail, Apple Mail (table-based, sans JS)

---

## Variables d'environnement locales

Copier `.env.example` en `.env` :

```env
GITHUB_TOKEN=ghp_...
GITHUB_REPOSITORY=bigmoletos/revue_de_presse_IA

# Email (optionnel en local)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=moncompte@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
MAIL_TO=dest1@gmail.com,dest2@example.com
```

> En CI, la traduction (`deep_translator`) est automatiquement désactivée (variable `CI=true`) pour éviter les timeouts.

---

## Installation locale

```bash
git clone https://github.com/bigmoletos/revue_de_presse_IA.git
cd revue_de_presse_IA
pip install -r requirements.txt
cp .env.example .env
# Éditer .env
python run_ci.py
```

---

## Lancement manuel du workflow

Voir la section [Redéploiement manuel](#redéploiement-manuel) ci-dessous pour la procédure détaillée.

> Le cron ne se déclenche pas si le workflow n'a jamais été lancé manuellement — faire un premier `workflow_dispatch`.

---

## Maintenance : renouveler le mot de passe SMTP Gmail

Quand tu changes ton mot de passe Google ou que les mails ne partent plus, il faut régénérer un **mot de passe d'application** Gmail et mettre à jour le secret GitHub.

### Etape 1 — Générer un nouveau mot de passe d'application Gmail

1. Connecte-toi au compte Gmail utilisé pour l'envoi (celui dans `SMTP_USER`)
2. Va sur : https://myaccount.google.com/apppasswords
3. Si demandé, active d'abord la validation en 2 étapes : https://myaccount.google.com/signinoptions/two-step-verification
4. Crée un nouveau mot de passe d'application (nom : "Revue IA" ou autre)
5. Copie le mot de passe généré (16 caractères, format `xxxx xxxx xxxx xxxx`)

### Etape 2 — Mettre à jour le secret dans GitHub

1. Va sur : https://github.com/bigmoletos/revue_evenement_IA/settings/secrets/actions
2. Clique sur `SMTP_PASSWORD` puis "Update"
3. Colle le nouveau mot de passe d'application (sans espaces)
4. Enregistre

### Etape 3 — Tester l'envoi

Lance manuellement le workflow pour vérifier que l'email repart :

1. Va sur : https://github.com/bigmoletos/revue_evenement_IA/actions/workflows/revue-presse-ia.yml
2. Clique "Run workflow"
3. **Branche : `main`** (toujours main, jamais gh-pages)
4. Clique "Run workflow"
5. Une fois terminé, vérifie ta boite mail

> `gh-pages` est la branche de publication du site statique (HTML généré). Le code et le workflow sont sur `main`.

---

## Redéploiement manuel

### Relancer le workflow (collecte + email + Pages)

- **Depuis GitHub** : https://github.com/bigmoletos/revue_evenement_IA/actions/workflows/revue-presse-ia.yml → "Run workflow" → Branche `main`
- **Depuis le terminal** :
  ```bash
  gh workflow run revue-presse-ia.yml --ref main
  ```

### Quelle branche choisir ?

| Branche | Rôle | Quand l'utiliser |
|---------|------|------------------|
| `main` | Code source, workflow, scripts Python | Toujours pour "Run workflow" |
| `gh-pages` | HTML statique généré (publication Pages) | Jamais manuellement — géré automatiquement par le script |

> Le workflow sur `main` génère le HTML et le pousse automatiquement sur `gh-pages`. Tu n'as jamais besoin de toucher à `gh-pages` directement.

---

## URLs utiles

| Quoi | URL |
|------|-----|
| Site Pages (résultat) | https://bigmoletos.github.io/revue_evenement_IA/ |
| Workflow Actions | https://github.com/bigmoletos/revue_evenement_IA/actions/workflows/revue-presse-ia.yml |
| Secrets GitHub | https://github.com/bigmoletos/revue_evenement_IA/settings/secrets/actions |
| Settings Pages | https://github.com/bigmoletos/revue_evenement_IA/settings/pages |
| Mot de passe app Gmail | https://myaccount.google.com/apppasswords |
| Validation 2 étapes Google | https://myaccount.google.com/signinoptions/two-step-verification |

---

## Troubleshooting

| Problème | Cause | Solution |
|----------|-------|----------|
| `403 Write access not granted` | Token sans scope `repo` | Régénérer avec scope `repo` |
| `GITHUB_TOKEN manquant` | Secret non configuré | Ajouter `REVUE_GITHUB_TOKEN` dans Settings > Secrets |
| Pages non activées | GitHub Pages désactivé | Settings > Pages > activer sur `gh-pages` |
| Timeout CI > 20 min | Trop de sources lentes | Réduire `RSS_FEEDS_FILTERED` ou augmenter `timeout-minutes` |
| Email non reçu | App Password expirée | Régénérer (voir section "Maintenance" ci-dessus) |
| Email non reçu | Secrets SMTP manquants | Vérifier `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO` dans [Secrets](https://github.com/bigmoletos/revue_evenement_IA/settings/secrets/actions) |
| Mail vide (0 articles) | Aucun article daté d'hier | Normal le lundi — fallback sur les 20 plus récents |
| Warning Node.js 20 déprécié | Workflow Pages interne GitHub | Aucune action — GitHub mettra à jour automatiquement |
