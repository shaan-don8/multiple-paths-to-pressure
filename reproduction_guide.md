# Reproduction guide

## 1. Environment

The final verification environment used:

```text
Python 3.13.5
```

Create an isolated environment and install the pinned packages:

```bash
python -m venv .venv
# Windows PowerShell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The frozen scripts use `--data-dir` / `--output-dir` arguments and generally resolve named inputs from one data directory. To preserve the repository's clean source/data separation, use an untracked staging directory:

```text
work/repro/
```

`work/` is excluded by `.gitignore`.

## 2. Reproduction modes

### Mode A — canonical/public reproduction

Use this when the provider-derived canonical files have been cleared for public redistribution. Start from the included Layer 1/2/3 canonical files and rerun downstream models, summaries, validation, and peer-review checks.

### Mode B — full source reproduction

Use this when you possess legitimate access to the underlying FTN, PFF, and Spotrac source files. Place local source copies in `work/repro/` under the exact names required by the frozen scripts. These files remain untracked.

If provider-derived canonical data cannot be distributed publicly, outside reviewers can still inspect the code, documentation, aggregate result tables, figures, model outputs, and checksums; exact source-to-canonical rebuilding will require licensed inputs.

## 3. Layer 1

Frozen script:

```text
scripts/layer1/build_layer1_pressure_analysis_local.py
```

Published outputs from the script are:

```text
Layer_1_Team_Season_Master.csv
Layer_1_Pressure_Threshold_Analysis.xlsx
```

### Canonical-master mode

Place the frozen team-season master in `work/repro/` as:

```text
Layer_1_Team_Season_Master.csv
```

Then run:

```bash
python scripts/layer1/build_layer1_pressure_analysis_local.py   --data-dir work/repro   --output-dir work/repro
```

### Raw rebuild mode

The raw rebuild path additionally requires the four season pressure workbooks and four FTN season-outcome CSVs named as documented in the script. Run:

```bash
python scripts/layer1/build_layer1_pressure_analysis_local.py   --data-dir work/repro   --output-dir work/repro   --rebuild-master
```

Expected team-season sample: **128 rows**.

## 4. Layer 2

Copy these canonical inputs into `work/repro/`:

```text
Layer_2_Player_Room_Master.csv
Layer_2_Team_Season_Room_Master.csv
Layer_2_Player_Pressure_Impact_Master.csv
```

Run the frozen V2 construction:

```bash
python scripts/layer2/build_layer2_creation_finish_v2.py   --data-dir work/repro   --output-dir work/repro
```

Expected core outputs include:

```text
Layer_2_Creation_Finish_v2_Player_Master.csv
Layer_2_Creation_Finish_v2_Team_Master.csv
Layer_2_Creation_Finish_v2_Archetype_Summary.csv
Layer_2_Creation_Finish_v2_Incremental_Models.csv
Layer_2_Creation_Finish_v2_Stability.csv
Layer_2_Creation_Finish_v2_Sanity_Check.csv
Layer_2_Creation_Finish_v2_Audit.json
```

Then run:

```bash
python scripts/layer2/build_layer2_final_findings.py   --data-dir work/repro   --output-dir work/repro
```

The frozen Layer 2 player input contains **1,709 player-team-season segments** and the team master contains **128 team-seasons**.

Do **not** substitute the superseded `build_layer2_creation_finish.py` or exploratory `build_layer2_dual_axis.py`. The frozen V2 methodology keeps finishing separate from creation standing.

## 5. Draft classes

The standardized 2018–2025 draft file can be regenerated from the public nflverse draft-picks release:

```bash
python scripts/layer3/build_draft_classes_2018_2025.py   --data-dir work/repro
```

Expected complete file:

```text
draft_classes_2018_2025.csv
```

The frozen local copy contains **2,059 selections**.

## 6. Layer 3A — total resource investment

Required staged inputs:

```text
Layer_2_Creation_Finish_v2_Player_Master.csv
Layer_2_Creation_Finish_v2_Team_Master.csv
spotrac_player_cap_hits_2022_2025.csv
draft_classes_2018_2025.csv
```

If a local `draft_values.csv` is absent, the frozen script retrieves the public draft-value file used by the project.

Run:

```bash
python scripts/layer3/build_layer3_resource_investment.py   --data-dir work/repro   --output-dir work/repro/layer_3_resources
```

Core outputs:

```text
Layer_3_Player_Resource_Bridge.csv
Layer_3_Team_Resource_Master.csv
Layer_3_Archetype_Resource_Summary.csv
Layer_3_Resource_Models.csv
Layer_3_Resource_Sensitivity.csv
Layer_3_Identity_Audit.csv
Layer_3_Findings.json
Layer_3_Methodology.md
```

## 7. Layer 3B — within-room resource distribution

The Layer 3B script resolves the Layer 3A player bridge and team resource master from `layer_3_resources/`, `outputs/layer_3_resources/`, or the staging root.

Run:

```bash
python scripts/layer3/build_layer3b_resource_distribution.py   --data-dir work/repro   --output-dir work/repro/layer_3b_resource_distribution
```

Core outputs include:

```text
Layer_3B_Player_Resource_Allocation.csv
Layer_3B_Team_Allocation_Master.csv
Layer_3B_Allocation_Shape_Summary.csv
Layer_3B_Allocation_Strategy_Summary.csv
Layer_3B_Allocation_Models.csv
Layer_3B_Within_Team_Change_Models.csv
Layer_3B_Matched_Pairs.csv
Layer_3B_Matched_Comparison_Summary.csv
Layer_3B_Sensitivity.csv
Layer_3B_Findings.json
Layer_3B_Methodology.md
```

The final lagged primary sample should resolve to **82 unique team-seasons from 2023–2025**.

## 8. Final canonical Layer 3 panel

The frozen downstream analyses use:

```text
MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv
MODEL_Layer3_PlayerResourceAllocation_2022-2025_v1.csv
MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical.csv
```

**Packaging gap:** the retained script that constructs the final 338-column Layer 3 analytic panel from the upstream Layer 3 allocation/model-specification inputs has not yet been copied into the repository package. Until that script is added, treat `MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv` as the frozen canonical boundary for final-model and V9 reproduction. Do not describe the public repository as a complete source-to-final-panel automated rebuild.

Key audit expectations:

- 82 unique team-season rows in the analytic panel;
- seasons 2023–2025 only;
- 55 observations in the 2023–2024 training set;
- 27 observations in the 2025 retrospective holdout;
- no duplicate `(season, team_key)` pairs;
- bounded share variables where applicable.

## 9. Peer-review sensitivity analyses

Run from the repository root after staging the two required canonical Layer 3 files under `work/repro/`.

### Conditional resource test

```bash
python scripts/peer_review/v9_01_conditional_resource_test.py   --analytic work/repro/MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv   --player-resource work/repro/MODEL_Layer3_PlayerResourceAllocation_2022-2025_v1.csv   --outdir work/repro/v9_01
```

Primary audit values:

- total resource index, overall pressure: approximately **-0.39 pp**, 95% CI **[-1.06, 0.28]**;
- prior room quality (+10 percentile points), overall pressure: approximately **+2.19 pp**, 95% CI **[1.18, 3.20]**;
- total resource index, four-man pressure: approximately **-0.51 pp**, 95% CI **[-1.12, 0.10]**;
- prior room quality (+10 percentile points), four-man pressure: approximately **+2.04 pp**, 95% CI **[1.03, 3.05]**.

### Player-adjusted prior-pressure persistence

```bash
python scripts/peer_review/v9_02_residualized_prior_pressure_test.py   --analytic work/repro/MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv   --player-resource work/repro/MODEL_Layer3_PlayerResourceAllocation_2022-2025_v1.csv   --outdir work/repro/v9_02
```

The four-man full-room specification should retain a prior-room-quality estimate near **+2.06 pp** while residual prior pressure remains statistically imprecise.

### FTN × PFF concordance

The concordance audit uses the final 128-row Layer 2 creation-room canonical file, which contains both the PFF ED/DI room pressure measure and the FTN team/rush-count pressure fields.

```bash
python scripts/peer_review/v9_03_ftn_pff_concordance_audit.py \
  --room work/repro/MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical.csv \
  --outdir work/repro/v9_03
```

The frozen target concordance is Pearson `r = 0.724` against FTN overall pressure and `r = 0.718` against FTN four-man pressure after within-season standardization.

## 10. Final verification checklist

Before declaring a reproduction successful:

1. Compare generated file dimensions with `docs/data_dictionary.md`.
2. Compare SHA-256 hashes for unchanged canonical inputs using `docs/file_manifest.csv`.
3. Confirm the Layer 2 team master contains 128 team-seasons.
4. Confirm the final Layer 3 analytic panel contains exactly 82 unique team-seasons.
5. Confirm the retrospective split is 55 train / 27 holdout.
6. Reconcile the principal coefficients against the frozen manuscript tables/appendix.
7. Treat small floating-point formatting differences separately from substantive coefficient differences.

## 11. What a reproduction does not establish

Successful code execution reproduces the frozen transformations and estimates. It does not independently validate provider charting decisions, establish causal identification, or grant redistribution rights for licensed data.
