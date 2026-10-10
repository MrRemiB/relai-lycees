# Installation native — pilote coordinateur authentifié

**Portée : pilote partagé avec profils fictifs, pas un service RH national conforme/homologué.** Un seul compte/ rôle `coordinator`, pas de SSO, pas de droits par établissement, pas de roster RH réel ni de journal d’audit nominatif. Avant tout usage RH : rectorat, DPO, base légale, rétention, audit de sécurité, SSO et cloisonnement des droits. Cette livraison ne déploie rien à l’extérieur.

## Installation locale vérifiable

Python 3.11+ et Node 22+ pour la QA. Docker n’est pas nécessaire.

```sh
git clone --branch production --single-branch https://github.com/MrRemiB/relai-lycees.git
cd relai-lycees
python3 -m venv .venv-production
.venv-production/bin/python -m pip install -r requirements-production.txt
.venv-production/bin/python -m pip check
.venv-production/bin/python -m unittest discover -s tests -v
node --test frontend_tests/*.test.mjs
.venv-production/bin/python scripts/smoke_production.py
```

Le smoke démarre **réellement Gunicorn**, sur un port loopback temporaire, avec base isolée et identifiants aléatoires non affichés. Il teste health, authentification, refus CSRF/origine, création et calcul serveur de 3 000 besoins sans coordonnées (différés honnêtement, aucune requête IGN), annulation, redémarrage/relecture, déconnexion. Il refuse aussi réellement un deuxième processus et un démarrage sans secrets. Il supprime uniquement sa base temporaire et arrête ses propres processus. Aucun secret prédéfini ou utilisateur n’est utilisé.

Pour votre compte pilote, préparer DNS/TLS puis, depuis un terminal interactif :

```sh
.venv-production/bin/python scripts/setup_credentials.py \
  --origin https://relai.votre-domaine.fr \
  --db runtime/pilot.sqlite3 --output .env
.venv-production/bin/gunicorn -c gunicorn.conf.py wsgi:application
```

La saisie est **masquée deux fois**, 16 caractères minimum. Le helper refuse les entrées non interactives et d’écraser un fichier existant. Il crée un fichier 0600 contenant seulement un hash PBKDF2-SHA256 (600 000 itérations, sel aléatoire), un secret de session aléatoire et la configuration allowlistée. Aucun mot de passe en argument, historique shell, stdout ou Git. `.env.example` n’a aucun secret et ses valeurs vides provoquent un refus de démarrage. Le chargeur `.env` n’exécute jamais du shell. Variables d’environnement explicites prioritaires sur le fichier ; `RELAI_ENV_FILE` sélectionne un fichier 0600 alternatif.

Gunicorn écoute exclusivement **127.0.0.1:8137**. Accéder au pilote à `https://relai.votre-domaine.fr/login` via le proxy TLS, **pas en HTTP public**. Le smoke est l’unique exemple HTTP : `RELAI_COOKIE_SECURE=false` n’est autorisé que pour une origine loopback explicite. Secure est vrai par défaut.

## Déploiement Linux sous systemd et Caddy

Modèles : `deploy/relai.service`, `deploy/Caddyfile`. Ces modèles sont livrés ; systemd/Caddy/TLS ne sont pas installés ou activés par cette tâche. Installer Caddy selon sa documentation et prévoir DNS A/AAAA corrects, ports 80/443 et droits de certificats. Ne jamais ouvrir 8137 à Internet ni utiliser `app.py` comme serveur public.

1. Créer l’utilisateur dédié `relai` sans connexion shell et les répertoires `/opt/relai` (code en lecture seule), `/etc/relai` (0700, root), `/var/lib/relai` (0700, relai).
2. Copier uniquement l’allowlist de livraison ci-dessous dans `/opt/relai`. Le propriétaire du code doit rester root, pas l’utilisateur web. Créer le venv **sur la machine cible** et installer les exigences épinglées.
3. Exécuter le helper en terminal administrateur avec `--output /etc/relai/pilot.env --db /var/lib/relai/pilot.sqlite3 --origin https://relai.votre-domaine.fr`. Fichier root:root 0600 ; systemd lit `EnvironmentFile` avant de changer d’utilisateur.
4. Installer `deploy/relai.service` sous `/etc/systemd/system/relai.service`. Adapter les chemins si nécessaire. Le service impose un utilisateur sans privilèges, umask 0077, système/code en lecture seule, répertoires d’état explicites, aucune capability, interdiction de nouveaux privilèges, familles réseau limitées.
5. Adapter le domaine du Caddyfile à l’origine exacte. **Pas de `file_server`** ni de routes proxy excluant les assets : tout passe par l’authentification WSGI. Caddy fournit TLS et HSTS ; taille de corps bornée. N’activer des journaux d’accès qu’après examen de confidentialité/rétention.
6. Valider et activer sur la cible :

```sh
sudo systemd-analyze verify /etc/systemd/system/relai.service
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now relai
sudo systemctl reload caddy
curl --fail https://relai.votre-domaine.fr/health
curl -i https://relai.votre-domaine.fr/api/bootstrap  # 401, aucune donnée
```

Se connecter dans le navigateur ; vérifier que le cookie est `Secure; HttpOnly; SameSite=Strict`, les lots et besoins relus depuis SQLite et la déconnexion invalide la session. Ces vérifications cible/TLS restent à faire par l’exploitant.

**Un seul processus et huit threads HTTP.** Le verrou OS par base refuse un autre processus/worker. Ne pas augmenter `workers`, utiliser `--preload`, lancer une seconde instance ou faire un reload Gunicorn HUP/USR2 avec chevauchement de workers. Pour mise à jour/rotation : `systemctl restart relai` (arrêt puis démarrage). Un job actif devient `interrupted` après un crash/redémarrage ; il ne redémarre pas IGN tout seul. Reprendre explicitement une passe. Le cache IGN partage la même admission process-wide avec le workflow individuel existant.

## Sécurité API et sessions

- Public : `GET /health` retourne uniquement `{ "status": "ok" }`, `GET/POST /login` (aucune donnée métier).
- Tous les assets, `/`, API individuelles et jobs exigent une session valide. Aucun accès brut à Python, SQLite, données, docs ou secrets.
- Session opaque aléatoire signée HMAC-SHA256, enregistrée côté serveur, TTL absolue 8 heures ; cookie HttpOnly, SameSite Strict, Secure par défaut. Déconnexion révoque la ligne SQLite. Aucun rôle revendiqué depuis un payload client.
- `POST /login` exige `Origin` exactement égal à `RELAI_ORIGIN` (HTTPS en cible). Les autres POST exigent **aussi** `X-CSRF-Token`, fourni dans le JSON login/bootstrap. Refus d’une origine absente/différente ou d’un Fetch Metadata cross-site/same-site. Pas de CORS permissif.
- JSON strict : clés dupliquées, NaN/Infinity, champs inconnus, nombres booléens, dates impossibles et corps >3 Mo refusés. Le workflow individuel conserve sa validation existante et ses transactions atomiques.
- Dix tentatives de login par adresse de pair en 15 minutes (table SQLite). Le proxy loopback est volontairement vu comme pair commun : limitation conservatrice partagée, pas un système anti-abus distribué. Ne pas faire confiance à X-Forwarded-For client.
- CSP, no-store, nosniff, frame denial ; tuiles OSM externes déclarées. Pas de requêtes IGN depuis le panneau serveur ; le navigateur n’envoie que les jobs à ce serveur.

## Contrat des lots persistés

`POST /api/batches` avec `{ "needs": [ ... ] }` → 201 `{job}`. Exactement 1 à 3 000 besoins ; **validation complète avant toute écriture**, rejet atomique. Chaque besoin contient exactement :

```json
{
  "school_id": "UAI officiel présent dans le bootstrap",
  "subject": "Mathématiques", "pathway": "Générale",
  "start_date": "2026-10-10", "end_date": "2026-10-20",
  "hours": 12, "urgency": "Normale", "allow_cross_academy": false,
  "max_distance_km": 150, "max_travel_minutes": 90
}
```

Les dates ci-dessus ne sont qu’un exemple de schéma. Les champs sont validés par `matching.validate_need` pour création et matching, sans élargir les payloads du workflow individuel. Urgence `Normale|Urgente`, radius 0–2 000 km, max minutes 0–480, heures 0,1–60. Aucun champ personnel. Les besoins de lot ne créent ni besoins individuels ni affectations.

- `GET /api/batches` → 100 jobs récents (identifiants/statuts/comptes).
- `GET /api/batches/{id}` → job complet, progression, snapshot, résultats et comptes exacts.
- `POST /api/batches/{id}/run` avec `{}` → 202 : **une passe asynchrone**, réponse immédiate ; 409 si un job est encore actif.
- `POST /api/batches/{id}/cancel` avec `{}` → 200 : annulation persistée, génération invalidée. Une requête IGN déjà partie peut finir/cache, mais ne publie pas de résultat post-annulation. Nouvelle passe possible dès la sortie du worker.

États : `queued`, `running`, `partial`, `completed`, `cancelled`, `interrupted`, `stale`, `failed`. Une passe réévalue toutes les éligibilités, les dates et les affectations persistées. Elle ordonne urgence, rareté puis date, interdit tous les chevauchements inclusifs entre propositions et affectations existantes. **Heuristique gloutonne, pas optimisation globale ni réaffectation optimale.** Les profils sont fictifs. Une proposition n’est pas affectée automatiquement ; la validation humaine du workflow individuel existant refait le trajet et les contrôles atomiques.

Progression d’éligibilité persistée toutes les 25 lignes puis phase routage ; comptes calculés depuis les résultats, jamais depuis une estimation. Une passe cible au plus **80 paires uniques**, une seule invocation de `RouteService` : 4 req/s, 4 workers IGN et délai routage 30 s. Curseur durable round-robin entre reprises, y compris au-delà des premiers trajets inconnus. Le délai total inclut aussi la revalidation CPU/SQLite ; 30 s n’est pas un SLA du job entier. Pas de retry automatique, ni milliers de requêtes simultanées, ni durée substituée.

Résultats `proposed|deferred|unassigned` dont la somme vaut `total`. Preuve routière : secondes exactes, distance, fournisseur, version de ressource, horodatage, expiration. Géométries restent dans le cache RouteService, pas dupliquées dans les lignes de job. Trajets inconnus/indisponibles ou école sans coordonnées/secteur fiable : différés. Comparaison partielle explicitée même lorsqu’une proposition est disponible. L’absence de candidat compatible, un trajet vérifié incompatible ou un conflit démontré peuvent laisser non pourvu. Les propositions sont invalidées à la lecture si snapshot enseignants/écoles/affectations a changé ou si un trajet accumulé a expiré ; le worker vérifie aussi le snapshot avant d’écrire. Aucun export UI de job `stale/running/interrupted/failed`.

Le panneau production utilise ces APIs, relit après mutations, peut lister/ouvrir les jobs après rechargement, annuler/reprendre et exporter toutes les lignes. Aucun job production calculé seulement par Worker navigateur ni sauvegardé dans le navigateur. Le chemin `staticMode` distinct conserve le démonstrateur public limité à **100** besoins ; cette branche n’est jamais publiée vers Pages. La CI production n’a aucun job de publication et le workflow Pages refuse même un dispatch depuis production.

## Sauvegarde cohérente, restauration, rotation

Ne pas copier un SQLite vivant avec `cp` : utiliser l’API backup SQLite :

```sh
sudo -u relai /opt/relai/.venv-production/bin/python /opt/relai/scripts/backup_sqlite.py \
  /var/lib/relai/pilot.sqlite3 /var/lib/relai/backups/pilot-AAAAMMJJ.sqlite3
```

Le fichier destination doit être absent ; création 0600, snapshot transactionnel et contrôles `integrity_check`/`foreign_key_check`. Protéger/chiffrer les sauvegardes hors machine et fixer une durée de rétention adaptée au pilote. La base contient besoins, enseignants fictifs, affectations, jobs et sessions. Le cache `routes.sqlite3` est indépendant et jetable ; la preuve des propositions est déjà dans la base pilote. Une sauvegarde de cache ne garantit pas le même instant que celle des jobs ; ne pas présenter les deux fichiers comme une transaction commune.

Restauration : arrêter `relai`, sauvegarder la base actuellement utilisée avec le script, vérifier le backup choisi avec SQLite, remplacer **seulement** la base pilote prévue (jamais à chaud), propriétaire `relai`, mode0600. Retirer d’éventuels journaux SQLite de cette base avec le service arrêté, jamais pendant qu’une connexion existe. Vider `pilot_sessions` pour ne pas réactiver d’anciens accès ; conserver les jobs et affectations. Garder l’ancien code/environnement avec le backup pour rollback. Le cache de routes peut être supprimé et reconstruit.

```sh
sudo systemctl stop relai
# sauvegarde du fichier courant + vérification de l’intégrité du backup choisi
# installation de la base restaurée avec propriétaire relai et mode0600
sudo -u relai /opt/relai/.venv-production/bin/python -c \
  "import sqlite3; d=sqlite3.connect('/var/lib/relai/pilot.sqlite3'); assert d.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert not d.execute('PRAGMA foreign_key_check').fetchall(); d.execute('DELETE FROM pilot_sessions'); d.commit(); d.close()"
sudo systemctl start relai
curl --fail https://relai.votre-domaine.fr/health
```

Après restauration : connexion, relecture des IDs/comptes attendus, job actif désormais `interrupted`, reprise explicite puis revalidation des propositions avant export. En cas de panne IGN, conserver `partial/deferred` et ne jamais transformer une indisponibilité en absence de candidat ou en trajet inventé. Pour rotation de secrets : générer un **nouveau fichier** avec le helper, installer celui-ci sous le chemin prévu, vider les sessions et redémarrer. Aucun secret publié dans un ticket ou les logs.

## Allowlist de livraison

Code : `app.py`, `matching.py`, `routing.py`, `batches.py`, `production.py`, `wsgi.py`, `gunicorn.conf.py`, `requirements-production.txt`, `static/`, `scripts/` (sources .py seulement), `data/schools.json`, `data/calendar.json`, `data/SOURCES.md`, `deploy/`, cette documentation et `.env.example`. Tests optionnels : `tests/`, `frontend_tests/`. Exclure les `.env` réels, runtime, SQLite/cache/locks/journaux, venv, dist, captures et caches Python. Créer le venv sur cible ; ne pas transporter un environnement WSL comme installation Linux.

La version Gunicorn/packaging épinglée a été installée dans un venv isolé et réellement exécutée. L’activation systemd, les certificats Caddy, les sauvegardes de votre base réelle et une homologation RH ne sont pas revendiquées.
