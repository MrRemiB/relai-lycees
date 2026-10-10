# Vérification exécutée

## Portée

Démonstrateur local national, pas un service institutionnel de ressources humaines. Données d’établissements réelles ; tous les professeurs et besoins saisis lors de la QA sont fictifs. Aucun test ne prouve une authentification ou une intégration rectorale.

## Résultats automatisés

Exécution parent :

- `python3 -m unittest discover -s tests -v` : **26 tests, tous réussis** (après ajout de la régression sur les identifiants SQLite).
- `node --check static/app.js` et `node --check static/utils.js` : réussite.
- `node frontend_tests/utils.test.mjs` : **16 assertions réussies**.
- Données : 5 644 lignes source, 5 606 UAI distincts, 5 560 établissements géolocalisés, 46 sans coordonnées conservés, 4 statuts non renseignés conservés sans inférence.
- Calendrier : 2 587 enregistrements, licence Etalab v2.0 vérifiée ; conservation des horodatages, conversion Europe/Paris métropolitaine testée, jalons à durée nulle conservés.
- Concurrence d’affectation, conflits de dates, compatibilités, validation stricte, stockage isolé, persistance après redémarrage et import démo atomique couverts par les tests serveur.

## Navigateur réel — exécution parent

Service réel : `http://127.0.0.1:8127`, pas une API fictive.

- Carte nationale : 3 451 lycées publics sélectionnés par défaut, 3 423 points ; total du jeu 5 606. Tuiles OpenStreetMap effectivement chargées (15 au dernier contrôle), aucune image cassée.
- Scénario de remplacement Carnot, UAI `0210015C`, à Dijon : mathématiques, voie générale, 12 h/semaine, du 2026-10-16 au 2026-10-30.
- Trois suggestions fictives : 6,4 km, 29,4 km et 79,2 km à vol d’oiseau. Recherche seule : aucun enregistrement automatique.
- Parcours testé : enregistrer et affecter → lecture exacte `/api/needs` confirmant l’affectation → libérer → lecture confirmant le besoin ouvert sans professeur → clôturer → lecture confirmant le statut clôturé.
- Le seul besoin créé par la vérification parent a été supprimé après contrôle de son identifiant, de son UAI, de son horodatage et du statut clôturé. Base livrée avec zéro besoin initial et 1 600 profils anonymes fictifs.
- Filtre Guadeloupe : 37 établissements publics, 37 géolocalisés ; résultats hors métropole conservés.
- Dialog Sources : ouverture/fermeture native et licences/liens/couverture présents.
- Vues 1440×960, 390×844 et 320×740 : aucune largeur de document excédant le viewport ; à 320 px aucun bouton/champ/select ne déborde horizontalement. Contrôle responsive de bureau/mobile, pas validation de clavier physique iOS/Android.
- Captures inspectées : `.impeccable/review/desktop-initial.png`, `desktop.png`, `mobile.png`, `mobile-mission.png`. Le panneau est délibérément déroulé sur la capture des suggestions de bureau ; la capture initiale conserve le haut du panneau.

## Vérifications frontend complémentaires

Le développeur frontend rapporte des tests navigateur avec serveur réel et base SQLite temporaire : sauvegarde seule, recalcul d’un besoin, affectation directe, relecture des mutations, et dégradation en cas de blocage Leaflet/calendrier. Voir `frontend_tests/VERIFICATION.md`. Ces résultats sont séparés de l’exécution parent ci-dessus.

## Design et limites

Détecteur Impeccable exécuté une fois : un avertissement consultatif « bordure fine et ombre 24px », lié au dialog de données. Pas de diagnostic automatique de conformité RGAA. Les captures montrent une carte dominante, la navigation navy et le panneau de mission choisi par l’utilisateur.

Distances non routières, aucune garantie de trajet. Tout chevauchement de dates bloque conservatoirement une deuxième affectation, faute d’emploi du temps horaire. Pas d’optimisation globale du vivier ni d’affectation réelle. Polynésie française et Wallis-et-Futuna ne reçoivent pas de positions inventées quand les coordonnées officielles sont absentes. Pas de SSO ni droits par établissement, pas de déploiement public/TLS.

## Relecture indépendante finale

Première revue : interface moderne map-first conforme, séparation des données officielles/fictives conforme, matching et stockage cohérents avec le périmètre. Un défaut matériel P2 identifié : identifiants `need_id` ou IDs de routes au-delà du maximum SQLite causaient une déconnexion API.

Correction : validation entière stricte dans `matching.need_identifier`, validation de payload et route avant transaction, garde défensive dans le stockage. Test RED reproduisant la déconnexion, puis GREEN. Vérification sur le serveur redémarré : les quatre routes renvoient **HTTP 400 JSON**, les identifiants maximaux dans la plage sont acceptés puis retournent **404** si absents, aucune mutation de besoin/affectation.

Contre-relecture indépendante du correctif : **disposition `ship`, correctif antérieur résolu** ; test ciblé réexécuté sur base isolée. Ce verdict porte sur le correctif listé, pas sur un nouvel audit global de production. Documentation `DESIGN.md` et `.impeccable/design.json` produite et contrôlée. Pas de modification visuelle depuis les captures revues.

Archive livrée sans base SQLite ni état de scénario ; reconstruction déterministe des profils fictifs au premier lancement. Code, instantanés officiels, licences tierces, tests et documentation inclus. L’application est livrée en local, sans déploiement public.
