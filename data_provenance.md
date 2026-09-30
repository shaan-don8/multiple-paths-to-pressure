# Data provenance and lineage

## Freeze policy

The analytical source data and derived files used for the frozen manuscript were frozen on **July 27, 2026**. Repository files should be compared against the checksums in `file_manifest.csv` before a public release or reproduction run.

## Source-to-model lineage

| Source | Provider / origin | Primary variables | Transformation boundary | Public-repo default |
|---|---|---|---|---|
| FTN pressure / team-defense data | FTN Data | pressured dropbacks, rush count, EPA, success, explosive outcomes | Layer 1 team-season aggregation and normalization | Restricted raw source |
| PFF ED/DI player data | Pro Football Focus | opportunities, pressures, wins, true-pass-set production, position/team | Layer 2 creation/room construction | Restricted raw source |
| PFF finishing fields | Pro Football Focus-derived project file | sacks, hits, hurries, pressure conversion | Layer 2 finishing construction | Review derived redistribution rights |
| Player-season cap hits | Spotrac | cap hit, team, position, season | Layer 3 cap reconstruction and opportunity-coverage adjustment | Restricted pending rights review |
| Draft classes | nflverse / Pro Football Reference | year, team, round, pick, player, position, IDs | standardized 2018–2025 draft table | Public source |
| Draft-value curve | Fitzgerald-Spielberger / Over The Cap values distributed through `nfldata` | pick-value columns including OTC | annualized active rookie-control draft investment | Public source / verify upstream terms |

## Layer 1 lineage

```text
FTN play-level pressure data + FTN team defensive outcomes
    ↓
team-season aggregation
    ↓
overall / rush-count pressure rates
    ↓
within-season z-scores and percentiles
    ↓
Layer_1_Team_Season_Master.csv
    ↓
Layer 1 regressions, bootstrap, pathway models, figures/tables
```

The final Layer 1 sample contains 128 defense-seasons and 80,719 eligible dropbacks. FTN defines the team pressured-dropback event used for team pressure outcomes.

## Layer 2 lineage

```text
PFF ED/DI player pass-rush production
    ↓
Layer_2_Player_Room_Master.csv
        +
PFF-derived finishing fields
    ↓
Layer_2_Player_Pressure_Impact_Master.csv
        +
Layer_2_Team_Season_Room_Master.csv
    ↓
build_layer2_creation_finish_v2.py
    ↓
Layer_2_Creation_Finish_v2_Player_Master.csv
Layer_2_Creation_Finish_v2_Team_Master.csv
    ↓
final creation-canonical player / room tables
    ↓
build_layer2_final_findings.py
    ↓
final Layer 2 summaries, models, and graphics
```

Creation determines standing; finishing is descriptive and is not blended into the frozen creation score. Team-season room measures retain the distinction between the headliner and support rotation.

## Layer 3 lineage

```text
Layer 2 V2 player/team files
      +
Spotrac player-season cap hits
      +
draft_classes_2018_2025.csv
      +
public draft_values.csv (Fitzgerald-Spielberger/OTC curve)
      ↓
build_layer3_resource_investment.py
      ↓
Layer_3_Player_Resource_Bridge.csv
Layer_3_Team_Resource_Master.csv
      ↓
build_layer3b_resource_distribution.py
      ↓
player resource shares, HHI, prior quality, alignment,
continuity, unproven share, allocation summaries
      ↓
MODEL_Layer3_* canonical files
      ↓
[retained final model-specification build step — script still to be added to repo]
      ↓
MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv
      ↓
final Layer 3 models / V9 sensitivity analyses
```

The 82-row analytic panel is frozen and available, but the repository should not claim a complete automated Layer 3B-to-final-panel rebuild until the retained final model-specification script is copied from the local archive and verified.

The final primary Layer 3 panel contains 82 unique 2023–2025 team-seasons satisfying the lagged-prior and resource-coverage requirements.

## Provider reconciliation

FTN and PFF pressure values should not be forced into one-to-one equality. FTN supplies a binary team pressured-dropback event; PFF supplies player-attributed ED/DI pressure production. A single team pressured dropback can produce multiple player pressure credits, team pressure can include non-ED/DI rushers, and provider charting definitions differ.

The frozen concordance audit therefore evaluates agreement rather than equality. Across 128 defense-seasons, season-standardized PFF ED/DI room pressure correlated 0.724 with FTN overall pressure and 0.718 with FTN four-man pressure; corresponding Spearman correlations were 0.694 and 0.689.

## Identity and trade handling

Player names and team abbreviations are normalized before source joins. Traded player-seasons are represented as team-specific segments when necessary so production, opportunity, and resource values remain aligned to the organization for which they occurred.

## Missing prior treatment

For Layer 3 prior quality, current resource-bearing players without a valid previous-season creation estimate are assigned a neutral prior percentile of 0.50. Their current within-room resource share is separately captured by `unproven_resource_share`, preserving uncertainty rather than treating missing history as evidence of poor quality.

## Redistribution boundary

The local analytical archive may contain provider-derived canonical files required for exact reproduction. Public GitHub inclusion is a separate rights question. `file_manifest.csv` therefore records both analytical role and release classification. Do not infer redistribution permission merely because a file is technically derived or included in the local frozen archive.
