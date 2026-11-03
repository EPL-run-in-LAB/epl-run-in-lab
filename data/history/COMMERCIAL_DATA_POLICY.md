# Commercial data readiness (EPL Run-in Lab)

This directory is a separate historical foundation. Existing EPL predictions, the
Championship/EPL master CSVs, Goal-API, and current open-matchday cup data are
not re-licensed by this work.

## Included data

* [openfootball/football.json](https://github.com/openfootball/football.json) —
  [CC0 1.0](https://github.com/openfootball/football.json/blob/master/LICENSE.md),
  historical Bundesliga, La Liga, Serie A and Ligue 1 (2021/22–2025/26).
  Source commit is pinned in each season snapshot.
* [openfootball/espana](https://github.com/openfootball/espana) and
  [openfootball/italy](https://github.com/openfootball/italy) — CC0 1.0
  Football.TXT source of 20 repaired scores in 2024/25 matchday 38.
* [Ligue 1 official disciplinary decision](https://ligue1.com/fr/articles/l1_article_5189-discipline-toutes-les-decisions-l1-270526):
  Nantes–Toulouse 2026-05-17 was abandoned, but the league awarded its 0–0
  score. This individual factual correction is separately sourced; it does
  not mean the league's website content or database is CC0.
  The fixture is excluded from ordinary full-match model training.

CC0 applies to the contributors' rights in the dataset. It does not
automatically clear third-party trademarks, club logos, provider-specific
rights, contract terms, or prove that every score is accurate. Continue
showing data provenance and review usage before activating advertising.

## Excluded and alternative data paths

| Source | Status for potential ad-supported deployment | Replacement path |
| --- | --- | --- |
| Existing EPL/Championship master CSVs | Provenance to audit. Do not assume commercial permission. | Rebuild a rights-reviewed dataset from CC0 sources, then benchmark new model separately. |
| open-matchday | Compilation explicitly non-commercial; keep current cup ingestion isolated. | OpenFootball CC0 for historical/partial current fixtures; or contract for a commercial match feed. |
| Football-Data.co.uk free CSVs | Stated personal/academic fair-use limitation; no commercial feed or model training without agreement. | CC0 OpenFootball for basic scores; commercially licensed provider for shots and advanced stats. |
| football-data.org | API has free and paid tiers, attribution and plan requirements; explicit monetized use permission needs verification. | Evaluate written terms and appropriate commercial subscription. |
| GOAL-API / other feeds | Existing rights and terms not reviewed in this effort. | Confirm in writing whether advertising, retention, reuse and derived metrics are allowed. |

Official terms:
* https://football-data.co.uk/contact.php
* https://github.com/oladeeayo/open-matchday
* https://www.football-data.org/pricing
* https://www.football-data.org/documentation/faq

## Commercially licensed feed candidates (not installed)

* [FootyStats API FAQ](https://footystats.org/api/documentations/faq) says its
  API data may be used for websites, stored databases, prediction systems and
  machine-learning analysis. Its separate
  [API legal terms](https://footystats.org/api/documentations/terms-of-use-and-legal)
  prohibit raw-data resale and redistribution. Before using it in an ad-funded
  EPL Run-in Lab, confirm the specific paid plan, advertising rights, caching,
  bulk/history access, and public JSON export permissions.
* [football-data.org](https://www.football-data.org/pricing) offers paid
  historical plans, but publication/advertising and derived-model rights must
  be verified under the subscription terms; attribution is requested.
* A provider with expressly granted commercial analytics and storage rights
  is preferable to scraping an unlicensed public match website.

Do not automatically switch to any provider without verifying and recording
the active contract or license and the data's redistribution limits. For
commercial deployment, the current open-matchday ingestion must be replaced
or authorized independently of this CC0 historical warehouse.

## Architecture

* Raw source snapshots live in data/history/snapshots, not docs/.
* scripts/build_history_warehouse.py produces SQLite + validation report.
* No prediction code, public fixtures, or Pages UI is changed.
* Club IDs are generated conservatively from country and normalized name.
  Cross-competition aliases and manager/player records require curated registries.
* Stale upstream files, zero-goal draws, abandoned matches and re-scheduled
  fixtures must not be silently inferred or converted into completed 90-minute matches.

Before monetization: separately audit every active current-season feed, historical
feature source and asset license. Use a commercial agreement if a provider's
rules do not expressly permit an advertising-supported application.
