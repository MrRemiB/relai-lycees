# Contrat navigateur métier v1 — prototype fictif

Référence de portée : `EVOLUTION_METIER.md`. Les recherches `research/SYNTHESE-PRESTATAIRE.md`, `regles-metier.md`, `usages-integrations.md` et `conformite.md` ne certifient pas les textes consolidés actuels. Aucun seuil, zone ou état `validated` de ce prototype n'est une règle nationale, une homologation, une nomination ou un droit à payer.

## Parcours effectivement connecté

En mode Pages explicite (`meta relai-mode=static`) : onglet **Paramètres métier** → charger modèle ou scénario actuel → modifier formulaires/référentiels JSON → **Valider et prévisualiser** (sans mutation) → **Appliquer explicitement** → lecture de la configuration appliquée. Le scénario préfère un profil public actuel de Dijon, ancré à un lycée réel, et ne crée pas de professeur ni de besoin dans la source. Les zones et les statuts qu'il prépare sont fictifs. Il prépare des dossiers TZR, contractuel et RCD lorsqu'assez de profils sont présents, un contrat, un engagement et des EDT connus vides. L'état initial est **draft** : les recherches restent en revue jusqu'à validation manuelle **simulée** explicite.

Le bouton mission ouvre un besoin sans enregistrer/affecter. L'onglet lot propose la même mission et un modèle JSON v1, sans modifier les paramètres appliqués. Ancien CSV inchangé, champs facultatifs via JSON. Recherches et worker consomment le même `matchEligible` → `businessCheck`; le lot contrôle en plus les collisions, la capacité cumulée et le solde RCD entre ses propositions. Aucune affectation automatique, maximum Pages **100 besoins**. Les simulations individuelles restent des clics explicites et réversibles avec recontrôle frais IGN.

- `historical` : règles historiques discipline/voie/secteur/académie/disponibilité/capacité/rayons/date. **Aucun contrôle administratif** annoncé.
- `controlled` : refus prouvé → `excluded`; dossier/règle/source/contrat/capacité/mobilité inconnus ou non validés → `review`, jamais candidat exécutable. Les contraintes de base restent impératives.
- TZR rectoral : RAD et zones explicites, adjacence **orientée** `zone.adjacent_zone_ids`, pas un rayon. Hors zone : refus ou revue selon la configuration.
- Contractuel rectoral : contrat manuel validé, intervalle intégral et sites/zones contractualisés. Aucun contrat inconnu accepté.
- RCD interne : statut volontaire RCD, engagement validé, même UAI, dates, séances et solde. Dépassement du seuil local indicatif → alerte/requalification en revue, jamais mutation automatique de circuit. Les sollicitations TZR en RCD avec accord rectoral spécifique ne sont **pas** modélisées : elles ne sont pas proposées par ce prototype.
- RAD déclaré : origine réelle des appels IGN du mode contrôlé, coordonnées provenant uniquement de l'annuaire. Le RAD n'est pas présenté comme l'origine juridique universelle d'un déplacement. Les anciennes routes affectées conservent leur origine UAI enregistrée, même après modification du dossier.
- Permissions interacadémiques : permission du profil de référence, permission du dossier et opt-in du besoin sont toutes nécessaires. La déclaration métier peut restreindre, pas élargir silencieusement le vivier de référence.
- Fraîcheur dossier/EDT : horodatage absent, futur ou âge supérieur à `freshness_days` → revue. Date de validation future → revue. Périmètre config absent → revue, hors périmètre renseigné → refus.
- Disponibilité manuelle remplace les bornes de disponibilité du profil de démonstration; capacité déclarée remplace son compteur fictif, mais nécessite `capacity_validated`. Ce n'est **pas** un calcul ORS/pondérations/corps/temps partiel.

## JSON de configuration exporté (pas une API serveur disponible)

Namespace local séparé `relai-business-v1`; document complet ≤ **2 500 000 octets UTF-8**, versionné et relu après écriture. Les clés indiquées ci-dessous sont obligatoires au sein de chaque objet présent. `null` est accepté **seulement** où indiqué; pas de champs RH libres dans les profils. Champs inconnus, clés JSON dupliquées, doublons de listes/IDs, nombres non finis/booléens numériques, dates inexistantes, liens inconnus et objets malformés sont rejetés avant écriture. Import complet **replace**, pas patch ni append. Pas de donnée nominative, santé, domicile, contact, notes de personne ou identifiant SIRH. Libellé et référence libres bornés concernent exclusivement les règles fictives.

Racine :

```
{
  schema_version: 1,
  revision: entier sûr >= 0,
  config: Config,
  zones: Zone[],
  profiles: Profile[]
}
```

**Config** :

| Clé | Type / limites |
|---|---|
| mode | `historical` ou `controlled` |
| label | chaîne non vide ≤160 caractères, sans contrôles |
| academy | académie existante ou `null` |
| school_ids | UAI existants distincts, ≤5000 |
| source_reference | référence de règle ≤300 caractères ou `null` |
| validated_on | date réelle `YYYY-MM-DD` ou `null` |
| state | `draft` / `validated` (manuel simulé) |
| mission_modes | sous-ensemble distinct non vide de `RCD`, `rectoral` |
| rcd_max_days | nombre fini 1…365, seuil local indicatif inclusif |
| freshness_days | nombre fini 1…3650 |
| travel_margin_minutes | nombre fini 0…240 |
| out_of_zone | `exclude` / `review` |
| mobility_mode | `car` / `manual` (manual ne produit aucun trajet voiture autorisé) |
| priority | `urgent_scarcity` / `scarcity`, utilisé par l'ordre du lot |

**Zone** (≤500) : `id` unique conforme `Z[A-Za-z0-9_-]{1,63}`, `label` ≤160, `academy` existante, `school_ids` UAI de cette académie, `adjacent_zone_ids` IDs de zones existantes distincts, sans auto-adjacence. Une adjacence n'est pas inférée à partir de coordonnées et n'est pas réciproque implicitement.

**Profile** (≤5000, IDs uniques) :

| Clé | Type |
|---|---|
| teacher_id | ID anonyme `DEMO-\d{4,8}` existant dans le vivier chargé |
| status | `TZR`, `contractual`, `RCD`, `unknown` |
| rad_school_id | UAI existant ou `null` |
| zone_ids | IDs de zones distincts |
| contract | `null` ou `{start_date,end_date,school_ids,zone_ids,validated}` |
| capacity_hours | nombre fini 0.1…60 ou `null` |
| capacity_validated | booléen strict |
| rcd_engagement | `null` ou `{school_id,start_date,end_date,hours_limit,hours_reserved,hours_done,validated}` |
| mobility_modes | sous-ensemble distinct de `car`, `manual` |
| cross_academy | booléen strict, permission supplémentaire du dossier |
| source_updated_at | horodatage UTC ISO `YYYY-MM-DDTHH:MM:SS[.sss]Z` réel ou `null` |
| availability | `null` ou `{start_date,end_date}` |
| timetable | `null` ou `{known:bool,sessions:Session[],source_updated_at:UTC|null}` |

Dates contractuelles, engagement et disponibilité : intervalle réel ordonné, bornes inclusives. Contrat : sites/zones existants, `validated` booléen; périmètre vide est valide syntaxiquement mais provoque une revue métier. Engagement : UAI existant, heures numériques 0…2000; `hours_reserved` représente les réservations **externes manuelles**, `hours_done` le réalisé externe déclaré. Le moteur ajoute les simulations locales RCD et les propositions du lot, sans transformer une proposition en service fait. Éviter de recopier une simulation locale dans `hours_reserved` : elle serait comptée deux fois conservatoirement. Libérer une simulation la retire du décompte local. Pas de liquidation financière, pas de journal de réalisation/paie.

## Besoins / séances rétrocompatibles

Les champs historiques restent inchangés. Champs facultatifs supplémentaires :

- `mission_type`: `RCD` / `rectoral` / `unknown`; absent = inconnu en mode contrôlé.
- `sessions`: tableau (≤1000) de `{date,start,end,timezone,school_id}`. Date réelle, horaires `HH:MM` stricts de `00:00` à `23:59`, `start < end`, UAI existant **égal à l'UAI du besoin**, date dans ses bornes. Pas de chevauchement de séances dans le document. Fuseau IANA valide; seul **Europe/Paris métropolitain** est exécuté. Tout autre fuseau et toute académie ultramarine passent en revue. Les heures Europe/Paris inexistantes/ambiguës (DST) et les séances traversant un changement de décalage sont en revue, sans durée supposée. Pas de séance de nuit traversant minuit, récurrences, semaines A/B ou calendrier scolaire assimilé à un EDT individuel.

EDT inconnu : toute affectation aux dates chevauchantes bloque conservatoirement. EDT `known:true` : séances requises et source récente; séances occupées versus demandées contrôlées. Même site et séances non chevauchantes peuvent être compatibles dans la limite cumulée hebdomadaire déclarée. Sites différents : **revue conservatrice**, car le prototype ne persiste pas de preuve routière de transition site→site; le trajet RAD→mission ne remplace pas cette preuve. Le helper testé accepte une estimation réelle validée + marge, mais aucun formulaire ne prétend avoir connecté cette fonctionnalité optionnelle. Aucune vitesse/temps de trajet inventé.

Lots JSON : `{schema_version:1,needs:[NeedInput...]}`, jusqu'à100 Pages (fonction réutilisable configurable3000 pour le parent serveur). Entrée strictement historique + les deux champs facultatifs, import atomique. Le CSV historique ne transporte pas séances/circuit; utiliser JSON pour ne pas les perdre. Export résultats JSON : `{schema_version:1,kind:"relai-business-proposals",context:SHA256,business_revision:entier|null,generated_at:UTC,routing_mode:"IGN-car-partial"|"geographic-unrouted",proof_scope:texte,result:{rows,counts}}`. `rows` conserve les besoins, l'état, les motifs/flags, profil proposé et durée réelle ou null; `counts` total/proposed/review/deferred/unassigned. Cet export d'observation ne peut pas être importé comme décision d'affectation. Pas de géométrie routière dans l'export du lot. CSV résultats enrichi par `mission_type`, `sessions` JSON, `review_flags` JSON, `exclusion_reasons` JSON. Aperçu exact JSON avant calcul et sauvegarde conservant ces champs.

## Interface locale browser API / sorties

Ces routes sont des appels JavaScript `createBrowserAPI`, **pas des endpoints HTTP installés** :

- `/api/business` sans payload → document appliqué.
- `/api/business/validate` avec `{document:objet|texteJSON,expected_revision:entier,confirm_demo:true}` → `{valid:true,document}`; dry-run, aucune mutation.
- `/api/business/commit` même payload → document complet relu; compare `expected_revision` à la révision stockée et écrit `revision=expected_revision+1`, indépendamment de la révision importée.
- `/api/business/reset` `{confirm:true}` → mode historique vide, **révision incrémentée** pour empêcher une reprise d'ancien snapshot. Le reset métier est séparé du reset des besoins/routes.
- `/api/bootstrap` → `business` complet et profils effectifs (RAD, capacité et disponibilité manuels en contrôlé), écoles et affectations existantes.
- `/api/match` → candidats exécutables simulés, `excluded` et `review` séparés avec motifs; `summary.review`, `business_mode`, `business_revision`, `snapshot` SHA-256 du contexte. Refus administratif ne se confond pas avec route différée/indisponible.
- Affectation individuelle : `business_revision` facultatif pour rétrocompatibilité, fourni par l'UI Pages depuis le résultat recherché; une révision obsolète est rejetée. Recontrôle du contexte et de l'éligibilité après route fraîche, sans verrouillage multi-onglets garanti. Route enregistrée avec `route_origin_school_id` en contrôlé; séances/circuit/site conservés et revérifiés à la lecture.
- Lot : états `proposed`, `review`, `deferred` (routage inconnu), `unassigned`, compte exact de chaque classe. `review_flags` et `exclusion_reasons` expliquent le contrôle; plusieurs motifs peuvent concerner un profil.

`business-context.js` calcule le même fingerprint single/lot : document métier complet/révision, état de fraîcheur effectif, écoles (IDs, academies, secteurs, voies, coordonnées), profils effectifs, affectations sans géométrie. Mutation locale → effacement immédiat des recherches/propositions/routes de lot; autre onglet → invalidation et relecture exigée. Export/sauvegarde/reprise revérifient le fingerprint; reprise obsolète **refusée**, pas un resume des anciens résultats. Les routes expirées restent différées. Les besoins enregistrés restent consultables mais ne sont pas une garantie d'éligibilité après une nouvelle règle.

## Raccordement serveur à réaliser par le parent

Le schéma ci-dessus est le format ouvert d'échange du prototype. La variante installable doit porter les valeurs et règles sans élargir ce qui est validé : GET/PUT `/api/v1/config`, révision attendue, référentiels zones/profils/plannings, imports validate/commit transactionnels avec idempotency-key, audit/readback et événements d'invalidation. Sessions/CSRF/roles/scopes sont des responsabilités serveur. Aucun secret, callback arbitraire, connecteur SIRH, SSO ministériel, notification ni endpoint privé supposé n'a été ajouté ici. La parité serveur **métier** reste à développer/tester; les tests historiques de parité sont conservés.

## Vérification de cette livraison

Tests RED/GREEN : moteur absent au premier lancement; puis régressions réellement rouges sur capacité cumulée single/lot, solde RCD et origine RAD, territoire ultramarin. Dernière exécution : `node --test --test-skip-pattern='Python eligibility' frontend_tests/*.test.mjs` : **62 tests réussis, 0 échec**; les huit modules modifiés passent `node --check`. Le test historique qui lance un sous-processus Python a été conservé et filtré dans cette dernière exécution (pas de modification de code Python). Un premier lancement de la suite complète l'avait exécuté; la parité métier serveur reste non développée ici. Tests métier unitaires et browser API : strict JSON/dry-run/commit/relecture atomique, revision/fingerprints, mêmes revues single/lot, contrat/date/zone/RCD/fraîcheur, horaires/transitions, sessions persistées et maximum100.

QA locale réelle sur source à `http://127.0.0.1:8131` via `node frontend_tests/serve-business.mjs` (réutilise seulement le snapshot DEMO sanitizé déjà présent dans `dist/pages/data/teachers.json`; aucune modification du snapshot officiel). Draft :0 exécutables,1 ligne en revue métier sans route différée. Validated simulé : recherche réelle3 candidats IGN (0 min,44 min,1 h13); lot réel IGN1 proposé/1,0 revue/0 différé/0 non pourvu. Aucun besoin ni affectation enregistré par ce scénario de QA. Sauvegarde explicite relue, changement marge10→15 révision2→3, table immédiatement vidée et reprise refusée. Configuration contrôlée conservée après un vrai `location.reload()`. Import UI contenant un champ dossier inconnu rejeté, état local inchangé; réimport anonyme accepté en aperçu sans mutation. Export réel téléchargé/parsée : schema_version1, revision1,25 dossiers. Export résultats réel téléchargé/parsée : fingerprint64 caractères, revision1,1 besoin dont1 différé routage, séances conservées. Vues390/320 : largeur document égale au viewport, aucun input/select/textarea/bouton métier hors écran; capture320 inspectée. Pas d'audit RGAA, ni QA publiée : le parent publie Pages avant la variante serveur.

Limitations supplémentaires : pas de règles consolidées nationales, ORS/pondérations, preuve contractuelle officielle, paie/ISSR/Pacte, solde partagé multiutilisateur, validation transports publics, décisions concurrentes institutionnelles ou connecteur EDT. Un EDT déclaré vide reste une hypothèse fictive validée manuellement, pas un planning obtenu d'un SI autorisé. Le namespace local est borné mais n'est ni sécurisé, authentifié, ni un coffre RH. Les erreurs natives de confirmation dans l'outil navigateur ont nécessité acceptation du dialog par CDP; la sauvegarde a ensuite été relue réellement.
