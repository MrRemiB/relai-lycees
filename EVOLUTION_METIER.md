# Évolution métier configurable — contrat de livraison

## Portée
Aide à la décision avec profils fictifs, non SI RH homologué. Démo Pages main limitée100, puis production serveur3000. Aucun texte non consolidé transformé en règle nationale implicite. Règles locales manuelles versionnées dans la démo, exposition contrôlée/importable serveur. Aucune affectation officielle ni liquidation paie.

## Modèle v1
- Configuration : schema_version, revision, libellé, académie/périmètre, source/référence libre bornée, date validation, état draft/validated, modes RCD/rectoral et seuil indicatif RCD configurable, fraîcheur des imports configurable, marge trajet configurable, politique hors-zone stricte ou revue, critères priorité/rareté, modes voiture ou revue manuelle. Aucune préférence ne contourne les contraintes discipline, secteur ou dates.
- Zones : IDs stables, libellés, académie, liste UAI existants, zones limitrophes autorisées explicitement. Une zone géométrique/administrative ne se confond pas avec rayon.
- Dossiers profils DEMO : teacher_id existant, statut TZR/contractuel/volontaire RCD/non renseigné, RAD UAI, zone(s), dates périmètre contrat si contractuel, capacité déclarée/validation, modes mobilité autorisés, source_updated_at ; aucune donnée santé/domicile/personnelle libre.
- Besoins : enrichissement facultatif rétrocompatible type mission RCD/rectoral/non renseigné et séances date/start/end/timezone Europe/Paris/site UAI ; contrôle strict horaires et liens dates sans prétendre traiter tous fuseaux outremer. EDT connu exige séances connues, sinon blocage conservateur dates. Transitions de site exigent estimation routière réelle + marge ou revue manuelle ; jamais vitesse inventée.
- Pédagogie/financier : distinguer heures à couvrir et service fait ; valeurs/validations manquantes averties, pas droit à affecter/payer. Pas barèmes Pacte/ISSR codés à partir de sources anciennes.

## Comportement
Garder mode historique explicite démo simple. Mode métier contrôlé configuré doit exclure de la liste exécutable ou mettre en revue tout contrôle administratif inconnu (statut, zone, contrat, règle draft, fraîcheur). Afficher contrôle conforme/refus/revue et motifs sans présenter contrôle simulé comme conformité réglementaire. Variante RCD interne nécessite engagement/conditions validés manuellement et UAI approprié ; rectoral TZR/contractuel vérifie périmètre. Prolongation dépassant seuil alerte/requalification proposée jamais acte automatique. Mutation configuration/profil/EDT invalide recherches, lots et reprise anciennes ; fingerprints incluent revision+référentiels métier.

## UX démo
Onglet Paramètres métier, formulaires compréhensibles, édition config/zones/dossiers/indisponibilités, scénario configuré, aperçu avant application et export/import JSON strict atomique (pas upload RH réel). Persistance namespace séparé versionné ; réinitialisation explicite. Résultats simples et lots utilisent règles identiques. 100 besoins max maintenus. Carte conserve rôle visuel et liste/table alternative. Pas faux numéro SIRH ni « homologué ».

## API installable prévue
GET/PUT /api/v1/config avec revision attendue ; GET référentiels zones/profils/plannings ; POST /api/v1/imports/validate dryrun sans mutation ; POST /api/v1/imports/commit avec revision attendue et idempotency key, import transactionnel borné et audit ; GET /api/v1/events pour invalidation/readback, schémas et contrats documentés/OpenAPI. Sessions/CSRF existants pour humains ; jeton intégration scoped en fichier/env uniquement, habilitations read/import/config, aucun secret navigateur, origine non pertinente uniquement pour bearer non-cookie. Rôles API ne remplacent pas SSO ou cloisonnement UAI. Protection schema inconnu/ID/source/fraîcheur/conflict/idempotence. Entrées profils strictement anonymes pour ce pilote. Connecteurs entrants pull/push compatibles spécifications, aucune URL de callback arbitraire SSRF. Documenter sortie snapshot+status pour raccordement outils externes, aucune API privée supputée.

## Recette
Tests RED/GREEN règle inconnue/draft/revue, zone versus rayon, contrat hors dates, RCD versus rectoral, données expirées, horaires, conflit/transition intersites, révisions/snapshot, import atomique/limites1003000 et valeurs malformées. Parité backend/browser cases métier. QA navigateur public scénario configuré et invalidation ; server HTTP auth+importdryruncommitidempotence+batchpersistance. Branches publiées avec auteur MrRemiB, CI verte, aucune copie runtime/secrets. Remonter limites explicites hors périmètre plutôt que stub ou faux connecteur.
