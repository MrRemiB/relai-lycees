# Relai Lycées
<!-- impeccable:product-schema 1 -->

## Platform
web

## Stack
Delegated by user: lightweight Python standard-library server, SQLite persistence, plain HTML/CSS/JavaScript and vendored Leaflet. Avoid unnecessary dependencies.

## Users
Lycée staff declare replacement needs; academy coordinators compare compatible replacements. France entire demo explicitly confirmed by user.

## Product Purpose
Interactive map of French lycées with input of replacement needs and geographical matching plus transparent relevant constraints.

## Capabilities and Constraints
Official open education institution data; synthetic demo-only teachers because no authorized nominative availability roster is provided. Persist needs and simulated assignments locally. Recommendations require discipline, dates, hours/capacity, sector and academy eligibility; routable eligible candidates are ranked by estimated car travel time from their fictional administrative base to the lycée. IGN Géoplateforme uses the BD TOPO road network, with a real route geometry and configurable maximum one-way travel minutes. No live traffic or timetable prediction. Provider failures or unroutable locations never produce invented minutes; partial comparisons are disclosed. Geographic km radii remain explicit prescreening/mobility constraints, not the ranking metric. No automated employment decision. No official ministry endorsement. No public real-person import without authentication and governance. Production auth/roles and rectorat integration remain open.

## Operating Context
Demo usable locally, desktop and mobile; future authenticated school/academy roles. A lycée selector substitutes institutional login in demo and must not imply secured multi-user access.

## Evidence on Hand
API fr-en-annuaire-education at data.education.gouv.fr verified reachable; includes UAI, coordinates, academy, sector, pathways. No real teacher registry or real needs supplied.

## Product Principles
Real public data and synthetic scenarios separated. Explain exclusions and ranking. Geographic proximity only after compatibility. Human validation. No sensitive or discriminatory ranking criteria.
