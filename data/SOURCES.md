# Official lycée data

- Publisher: DNE - Ministère de l'Education Nationale.
- Dataset: [Annuaire de l’éducation](https://data.education.gouv.fr/explore/dataset/fr-en-annuaire-education/); source systems: ONISEP and RAMSESE, as stated in official metadata.
- Metadata API: https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education
- Filtered JSON export: https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-annuaire-education/exports/json?where=type_etablissement%20%3D%20%27Lyc%C3%A9e%27%20AND%20etat%20%3D%20%27OUVERT%27
- Exact filter: `type_etablissement = 'Lycée' AND etat = 'OUVERT'`. No sector, academy, region, department or coordinate filter.
- License: **Licence Ouverte v2.0 (Etalab)**.
- Official license URL: http://www.etalab.gouv.fr/wp-content/uploads/2017/04/ETALAB-Licence-Ouverte-v2.0.pdf.
- Metadata lookup status: successful.

## Freshness and completeness

- Retrieval (UTC): 2026-10-09T15:34:15.951142+00:00
- Official dataset modified timestamp: 2026-10-09T05:01:22.377000+00:00.
- Official stated update frequency: Quotidienne.
- Verified API `total_count` before and after export: **5644**.
- Downloaded source rows: **5644**; unique UAI schools: **5606**; duplicate UAI rows consolidated: **38**.
- Schools with valid WGS84 coordinate pairs: **5560**; missing or invalid coordinate pairs retained: **46**.
- `updated_at` preserves each chosen row’s `date_maj_ligne`; retrieval time is not a school update date.
- Refresh: `python3 scripts/refresh_schools.py` from the project directory. Uses Python standard library only, urllib for HTTP, retries and gzip handling. A count mismatch aborts before replacing data.

## Normalization and geographic limits

- All official `Lycée` records marked `OUVERT`, both Public and Privé, are included. No bounding box: metropolitan France and overseas records are retained, including territories outside the European map viewport.
- This is the official directory’s coverage, not an independent census. Other source types (e.g. EREA, CFA or colleges) and closed/not-yet-open establishments are outside the exact filter, even if they offer lycée-level instruction. No exhaustive coverage of every overseas territory is implied where the official source has no records.
- Department, academy and region use official text labels; postcode remains a string. UAI is validated and preserved exactly, never synthesized.
- Sector is Public or Privé when declared. **4 records have a null official sector**, retained as `sector: null` rather than guessed or excluded. This is an explicit exception to the desired two-value sector schema. Missing-sector UAI: 0171680J, 0222078P, 0271911F, 0443066U.
- Addresses join nonempty `adresse_1`, `adresse_2`, `adresse_3`. Coordinates use official WGS84 latitude/longitude (falling back to `position`), not projected origin coordinates; no external geocoding or guessed positions. Coordinates can have approximate address or commune-level precision and are not guaranteed building locations.
- One record per UAI. Duplicate rows prefer most recent `date_maj_ligne`, then available coordinates, then deterministic lexical JSON order. Known pathway flags are unioned. If needed, use a geocoded duplicate’s coordinates and matching geographic/address fields. This represents one site, not every campus of a multi-site establishment.
- Pathways are included only for official `voie_* = 1`: Générale, Technologique, Professionnelle. An empty list means none affirmed in the source, not independently confirmed absence. Missing textual source facts remain null.
- No teacher, staff, replacement availability or allocation data is present in this official school dataset. Any demo teacher data must be clearly labeled synthetic.

## Calendrier scolaire officiel — deuxième jeu de données

- Source : https://data.education.gouv.fr/explore/dataset/fr-en-calendrier-scolaire/
- API export : https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets/fr-en-calendrier-scolaire/exports/json
- Publication : DNE - Ministère de l’Éducation nationale.
- Licence vérifiée dans les métadonnées officielles : Licence Ouverte v2.0 (Etalab).
- 2 587 enregistrements exportés, nombre confronté au `total_count` de l’API. Instantané et métadonnées dans `data/calendar.json`.
- Millésimes réellement présents : 2009-2010 à 2028-2029, avec des conventions de millésime variables pour certains territoires. Cela ne garantit pas une couverture future exhaustive par académie.
- Fuseau déclaré par le jeu : **Europe/Paris**. Les horodatages UTC sont conservés sans tronquer la date ; les périodes métropolitaines doivent être affichées dans le fuseau déclaré. Pour l’outre-mer, vérifier la convention de la source avant toute règle de gestion opérationnelle.
- Métadonnées DCAT temporelles restées à 2009-2025 malgré des lignes plus récentes : couverture évaluée à partir des lignes réelles, pas du seul intervalle DCAT.
- Départ après la classe le jour indiqué, reprise le matin du jour indiqué ; calendrier consultatif, jamais assimilé à la disponibilité d’un professeur ni à une interdiction de remplacement.
- Mise à jour explicite : `python3 scripts/refresh_calendar.py`.

### Department labels present in this snapshot

Ain, Aisne, Allier, Alpes-Maritimes, Alpes-de-Haute-Provence, Ardennes, Ardèche, Ariège, Aube, Aude, Aveyron, Bas-Rhin, Bouches-du-Rhône, Calvados, Cantal, Charente, Charente-Maritime, Cher, Corrèze, Corse-du-Sud, Creuse, Côte-d'Or, Côtes-d'Armor, Deux-Sèvres, Dordogne, Doubs, Drôme, Essonne, Eure, Eure-et-Loir, Finistère, Gard, Gers, Gironde, Guadeloupe, Guyane, Haut-Rhin, Haute-Corse, Haute-Garonne, Haute-Loire, Haute-Marne, Haute-Savoie, Haute-Saône, Haute-Vienne, Hautes-Alpes, Hautes-Pyrénées, Hauts-de-Seine, Hérault, Ille-et-Vilaine, Indre, Indre-et-Loire, Isère, Jura, La Réunion, Landes, Loir-et-Cher, Loire, Loire-Atlantique, Loiret, Lot, Lot-et-Garonne, Lozère, Maine-et-Loire, Manche, Marne, Martinique, Mayenne, Mayotte, Meurthe-et-Moselle, Meuse, Morbihan, Moselle, Nièvre, Nord, Nouvelle Calédonie, Oise, Orne, Paris, Pas-de-Calais, Polynésie Française, Puy-de-Dôme, Pyrénées-Atlantiques, Pyrénées-Orientales, Rhône, Saint-Barthélémy, Saint-Martin, Sarthe, Savoie, Saône-et-Loire, Seine-Maritime, Seine-Saint-Denis, Seine-et-Marne, Somme, St-Pierre-et-Miquelon, Tarn, Tarn-et-Garonne, Territoire de Belfort, Val-d'Oise, Val-de-Marne, Var, Vaucluse, Vendée, Vienne, Vosges, Wallis et Futuna, Yonne, Yvelines
