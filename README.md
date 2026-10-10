# Relai Lycées — remplacements et temps de trajet

Carte interactive des lycées français et aide explicable à la recherche de remplaçants, **classés par temps de trajet estimé en voiture**. Projet indépendant, sans affiliation ni validation du ministère de l’Éducation nationale.

Les établissements sont réels ; les **1 600 professeurs de démonstration sont fictifs**. Aucun fichier RH ni domicile réel n’est publié.

## Branche production — pilote coordinateur authentifié

Voir **[PRODUCTION.md](PRODUCTION.md)** pour l’installation native Gunicorn dans un venv isolé, le compte coordinateur configuré par saisie masquée, SQLite partagé, les lots asynchrones jusqu’à **3 000 besoins**, la protection CSRF/session, systemd/Caddy TLS et les sauvegardes/restaurations. Les commandes `app.py` ci-dessous restent celles du démonstrateur local non authentifié ; elles ne sont pas l’entrée production. Ce pilote conserve uniquement des profils fictifs, sans SSO ni homologation RH nationale. Aucun secret prédéfini, aucune publication production vers Pages.

## Configuration métier et intégrations serveur

Voir [BUSINESS_SERVER.md](BUSINESS_SERVER.md) et [openapi.json](openapi.json) : paramètres manuels après connexion, moteur Python métier partagé single/lot, import anonyme transactionnel, révisions/idempotence/audit et jetons intégration scoped. Aucun connecteur RH réel, SSO ni conformité nationale supposés.

## Version sans serveur — GitHub Pages

Démo publique : https://mrremib.github.io/relai-lycees/

Le workflow `.github/workflows/pages.yml` teste et construit une version statique autonome : carte, données officielles, profils fictifs, compatibilités et calculs IGN dans le navigateur. **Aucun serveur Python ni SQLite n'est requis sur GitHub Pages.** Les besoins et affectations sont conservés dans le stockage local du navigateur, pas dans le dépôt : ils ne sont pas partagés entre lycées, appareils ou navigateurs. Ne saisir aucune donnée RH réelle. Internet reste nécessaire pour la carte et l'API IGN, qui reçoit l'IP du navigateur et les deux coordonnées, sans nom ni date de mission.

Reproduire le site : `python3 scripts/build_pages.py`, puis `python3 -m http.server 8130 --directory dist/pages`. Ouvrir http://localhost:8130. Le dossier généré est construit uniquement depuis une liste de sources publiques, jamais depuis `runtime/`. Le site publié est public ; le code et les jeux ouverts sont dans https://github.com/MrRemiB/relai-lycees.

Les paragraphes Python/SQLite ci-dessous décrivent **l'autre mode : serveur local**, conservé pour les tests et l'évolution future. Ils ne s'appliquent pas à la persistance du site GitHub Pages. Une véritable coordination multi-utilisateur exige toujours une base partagée et une authentification.

## Démarrer le serveur local

Python 3.11 ou supérieur, sans dépendance Python externe. Internet est nécessaire pour les tuiles cartographiques et les calculs routiers IGN ; l’annuaire, le formulaire et les besoins enregistrés restent locaux.

```bash
cd relai-lycees
python3 app.py
```

Ouvrir **http://localhost:8127**. Le service écoute uniquement sur `127.0.0.1`. Sous Linux/WSL, `bash start.sh` est aussi disponible. Autre port : `python3 app.py --port 8128`.

**Ne pas exposer ce démonstrateur tel quel à Internet.** Publier le code sur GitHub ne déploie pas le serveur Python ; GitHub Pages seul n’exécute pas l’API ni SQLite.

## Parcours

1. Rechercher un lycée ou le sélectionner sur la carte, avec filtres académie/secteur.
2. Déclarer discipline, voie, période et heures hebdomadaires ; préciser le **temps maximum aller en voiture**, 90 minutes par défaut.
3. Le rayon kilométrique est un préfiltre géographique à vol d’oiseau. Il ne sert plus à classer les suggestions.
4. Rechercher : les compatibilités sont filtrées, puis les itinéraires calculables sont classés par **durée routière croissante**.
5. Visualiser le véritable tracé routier, sa durée estimée et sa distance routière.
6. Enregistrer et valider explicitement une affectation **simulée** ; retrouver les besoins dans le suivi et libérer une affectation.

« Essayer un scénario » prépare un cas fictif dans un lycée réel de Dijon, sans enregistrement automatique. Cela ne représente pas une absence réelle.

## Trois services de données ouvertes

- **Annuaire de l’éducation** : UAI, nom, adresse, coordonnées, académie, statut et voies. Instantané de **5 606 lycées uniques**, dont **5 560 géolocalisés** ; les 46 sans coordonnées restent dans la liste. Quatre statuts absents restent inconnus, sans inférence. Données sous Licence Ouverte v2.0 Etalab.
- **Calendrier scolaire officiel** : 2 587 lignes de congés/jalons par académie et zone, à titre informatif. Une période de vacances ne prouve pas l’indisponibilité d’un professeur et ne bloque pas le matching.
- **IGN Géoplateforme — navigation** : moteur `bdtopo-osrm`, réseau BD TOPO, voiture (`car`), chemin le plus rapide (`fastest`), géométrie GeoJSON. La réponse précise la version du réseau utilisée.

Sources :
- https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/
- https://data.education.gouv.fr/explore/dataset/fr-en-calendrier-scolaire/
- https://ignf.github.io/cartes.gouv.fr-documentation/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/calcul-itineraire/

L’annuaire est un instantané, pas une preuve de disponibilité de remplaçants. Rafraîchissement explicite :

```bash
python3 scripts/refresh_schools.py
python3 scripts/refresh_calendar.py
```

Redémarrer ensuite. Les profils fictifs persistés ne constituent pas un flux actualisé de ressources humaines. Les détails de source, dédoublonnage, licences et couverture sont consignés dans `data/SOURCES.md`.

## Comment sont calculés les trajets ?

**Trajet aller, base administrative fictive → lycée.** Les minutes proviennent de la durée renvoyée par IGN, pas d’une formule distance/vitesse. Le tracé est celui de la réponse IGN, pas une ligne droite dessinée pour simuler une route.

- **Pas de trafic en temps réel**, pas de prédiction de bouchons, pas d’horaire de départ ni de recherche multimodale/transports en commun. Ces estimations ne sont pas des garanties de durée ni d’accessibilité.
- Couverture documentée IGN : France métropolitaine et DROM. Les autres territoires, réseaux discontinus et points sans coordonnées peuvent être non calculables ; aucune position ni durée de secours n’est inventée.
- Un trajet indisponible, mal formé, raccordé trop loin des points demandés ou supérieur au maximum de minutes n’est pas proposé pour affectation.
- Cache local des routes : 7 jours pour les succès, durée limitée pour les échecs ; clés directionnelles par coordonnées exactes, ressource, profil et optimisation. Le cache n’est pas un suivi de déplacements.
- Au plus 4 requêtes réseau par seconde dans un processus applicatif, sous le plafond public documenté de 5/s/IP. Plusieurs instances partageant une IP exigeraient un régulateur distribué.
- Les requêtes sont bornées en nombre et durée. Si tous les trajets éligibles ne peuvent pas être évalués, le **classement partiel est signalé** : « le plus rapide » signifie alors parmi les trajets effectivement calculés, pas dans tout le vivier. Une nouvelle recherche peut compléter le cache.
- Ne pas utiliser l’API publique comme garantie de disponibilité ou SLA d’un système RH de production.

## Matching : contraintes avant temps de trajet

Discipline, voie, secteur, dates complètes, volume hebdomadaire, académie ou autorisation croisée explicite des deux côtés, rayon de mobilité et préfiltre du besoin. Toute affectation chevauchant les dates inclusives bloque un autre remplacement, même avec des heures libres, faute d’emploi du temps détaillé.

Ensuite : calcul routier, maximum de minutes et tri par durée, distance routière puis capacité disponible/identifiant en cas d’égalité. L’affectation recalcule/vérifie le trajet et les compatibilités, sans faire confiance à une durée fournie par le navigateur, puis vérifie les conflits dans une transaction SQLite.

Aucun critère d’âge, de sexe, d’origine, de religion, de santé ou de situation familiale ne participe au classement. Qualifications et autorisations réelles nécessitent un vivier métier autorisé. **Aucune affectation réelle n’est automatique.**

## Confidentialité et persistance

SQLite et cache routier dans `runtime/`, hors racine web et exclus de Git/de l’archive. Besoins et affectations simulées survivent au redémarrage. Le sélecteur d’établissement n’est **pas une authentification** : cette démo locale est partagée, sans isolation par lycée.

Les calculs IGN transmettent les coordonnées de départ/arrivée des bases **fictives** et des établissements, ainsi que l’adresse IP du serveur. Ni le nom du profil, ni sa discipline, ni les dates de remplacement ne sont nécessaires à la requête routière. Les tuiles OpenStreetMap transmettent l’IP du navigateur et la zone consultée. Aucun calcul ne fait appel à un service d’IA.

## Tests et distribution

Les tests utilisent des bases temporaires et des fournisseurs routiers de test explicitement injectés ; **la CI ne contacte pas IGN** et ne doit pas modifier l’état utilisateur.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q app.py matching.py routing.py scripts tests
node --check static/app.js
node --check static/utils.js
node frontend_tests/utils.test.mjs
```

Le workflow GitHub Actions reprend ces vérifications. `QA.md` distingue vérification locale, appels réels et résultats CI. Génération de l’archive portable, sans état de simulation ni cache :

```bash
python3 scripts/package_demo.py
```

## Passage en service institutionnel — hors périmètre

- SSO institutionnel et droits lycée/rectorat strictement cloisonnés ; audit des accès.
- Vivier RH autorisé : habilitations, disponibilités et zones de remplacement vérifiées, règles TZR/contractuels et partage de service/horaire précis.
- DPO : finalité/base légale, minimisation de localisation, information des agents, droits, conservation, sous-traitants et analyse d’impact si nécessaire. Aucun domicile publié.
- Sauvegardes/restauration, HTTPS, supervision, quotas, sécurité et exploitation.
- Politique de trajets validée : tarifs, péages/ferries, contraintes d’accessibilité, trafic, transports en commun ; contrat et conditions de service adaptés à l’usage.
- Audit d’accessibilité institutionnelle ; les vérifications responsive ne constituent pas une certification RGAA.

## Fichiers

`app.py` API/SQLite, `matching.py` compatibilités, `routing.py` service IGN/cache/classement routier, `static/` interface avec Leaflet vendored, `data/` instantanés officiels, `scripts/` rafraîchissement/génération/packaging, `tests/` tests isolés. Leaflet et markercluster conservent leurs licences dans `static/vendor/`. Les documents et bases ne sont pas servis par le serveur.
