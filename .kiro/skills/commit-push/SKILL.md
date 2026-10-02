---
name: commit-push
description: Committer les modifications que l'agent vient de faire et les pousser sur le remote. À utiliser quand l'utilisateur demande de committer, de sauvegarder les changements dans git, ou de pousser le travail en cours vers le dépôt distant.
---

## Objectif

Committer les modifications récemment apportées par l'agent, puis les pousser sur le remote, uniquement lorsque c'est autorisé (voir règles ci-dessous).

## Déroulé

1. Lancer `git status` (et `git diff` si besoin) pour identifier les fichiers modifiés par l'agent pendant la session en cours.
2. Stager uniquement les fichiers pertinents à la tâche effectuée, avec `git add <fichier1> <fichier2> ...`. Ne pas utiliser `git add .` ou `git add -A` s'il y a des changements non liés dans le repo.
3. Avant de stager, repérer les fichiers susceptibles de contenir des secrets (`.env`, `.env copy`, credentials, tokens, clés). Les exclure du commit et le signaler à l'utilisateur.
4. Rédiger un message de commit clair et concis résumant le changement (à l'impératif, en une ligne si possible).
5. Committer avec `git commit -m "<message>"`. Ne jamais utiliser `--amend`, sauf demande explicite.
6. Déterminer la branche courante avec `git branch --show-current`.
7. Vérifier si le push est autorisé :
   - Si la branche courante est `main` ou `master` : **ne pas pousser**. Demander confirmation explicite à l'utilisateur avant toute action sur cette branche.
   - Si une branche de travail dédiée existe déjà et suit un remote (`git status` indique "Your branch is up to date/ahead of 'origin/...'") : le push est autorisé, pousser avec `git push`.
   - Si la branche courante n'a pas encore de remote associé : créer le suivi avec `git push -u origin <nom-de-branche>`.
   - Si le push échoue (ex: historique divergent, remote rejeté) : ne pas forcer (`--force`). Rapporter l'erreur à l'utilisateur et demander comment procéder.

## Règles de sécurité

- Ne jamais pousser directement sur `main`/`master` sans autorisation explicite de l'utilisateur.
- Ne jamais utiliser `git push --force`, `git reset --hard`, ou toute commande destructive sans demande explicite.
- Ne jamais modifier la configuration git (`git config`).
- Conserver les hooks git (ne pas utiliser `--no-verify`) sauf demande explicite.
- Si un hook pre-commit échoue, corriger le problème, re-stager, puis créer un **nouveau** commit plutôt que d'amender.
- Si le contexte n'est pas clair sur la branche cible ou les fichiers à inclure, demander avant d'agir plutôt que de deviner.
