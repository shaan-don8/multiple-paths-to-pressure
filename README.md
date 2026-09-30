# Multiple Paths to Pressure: Defensive-Front Talent Structure and Resource Allocation in the NFL

This repository is the reproducibility package for **Multiple Paths to Pressure: Defensive-Front Talent Structure and Resource Allocation in the NFL**, an observational NFL roster-construction study by **Shaan Donohue**.

The project evaluates defensive-front construction as a three-layer sequence:

1. **Pressure and defensive outcomes:** how team pressure relates to EPA, success-rate prevention, and explosive-pass prevention, including four-man and five-plus-rusher pathways.
2. **Player and room quality:** how leading-player quality and supporting-cast quality combine to produce team pressure.
3. **Resource allocation:** whether salary-cap and draft-resource commitment predicts subsequent pressure once demonstrated room quality, continuity, uncertainty, and resource distribution are considered.

All source data and analytical files used for the frozen manuscript were frozen on **July 27, 2026**. The study is descriptive and associational; the lagged design does **not** identify a causal return to spending, draft investment, continuity, or concentration.

## Study samples

| Layer | Primary unit | Period | Final sample |
|---|---|---:|---:|
| Layer 1 | Defense-season | 2022–2025 | 128 defense-seasons; 80,719 eligible dropbacks |
| Layer 2 | Defensive-front team-season | 2022–2025 | 128 team-seasons; 1,709 player-team-season segments in the canonical player table |
| Layer 3 | Lagged defensive-front team-season | 2023–2025 | 82 qualifying team-seasons |
| Temporal validation | Lagged team-season | train 2023–2024 / test 2025 | 55 training observations / 27 retrospective holdout observations |

## Data sources

- **FTN Data:** team pressured-dropback outcomes, rush-count pathways, and play/team defensive outcomes.
- **Pro Football Focus:** ED/DI player pass-rush opportunities, pressures, wins, true-pass-set production, positions, and room membership.
- **Spotrac:** player-season salary-cap hits used to reconstruct room cap commitment.
- **nflverse / Pro Football Reference:** public draft classes used to identify draft year, team, pick, and player identity.
- **Fitzgerald-Spielberger / Over The Cap draft-value curve:** draft capital valuation used in the primary resource index.

FTN and PFF pressure measures are intentionally assigned different analytical roles. The project tests their team-season concordance rather than requiring numerical equality.

## Repository structure

```text
multiple-paths-to-pressure/
├── README.md
├── LICENSE
├── CITATION.cff
├── requirements.txt
├── .gitignore
├── data/
│   ├── canonical/
│   │   ├── layer1/
│   │   ├── layer2/
│   │   └── layer3/
│   ├── public_sources/
│   └── restricted/
├── scripts/
│   ├── layer1/
│   ├── layer2/
│   ├── layer3/
│   └── peer_review/
├── outputs/
│   ├── layer2/
│   ├── peer_review/
│   ├── figures/
│   └── tables/
├── docs/
│   ├── data_dictionary.md
│   ├── data_provenance.md
│   ├── reproduction_guide.md
│   ├── methodology_notes.md
│   └── file_manifest.csv
└── manuscript/
```

## Canonical analytical chain

```text
FTN team/play data ───────────────→ Layer 1 team-season pressure/outcome panel

PFF player data ──────────────────→ Layer 2 player creation/finishing files
                                      ↓
                                  Layer 2 room-quality panel
                                      ↓
Spotrac cap data ───────┐             │
Public draft data ──────┼─────────────┘
Draft-value curve ──────┘
          ↓
Layer 3 total resource index
          ↓
Layer 3 within-room allocation + prior quality
          ↓
82-row final analytic panel
          ↓
final models + temporal validation + peer-review sensitivity analyses
```

## Core frozen methodology

### Layer 1
Overall pressure and pressure conditional on rush count are related to defensive outcomes. Pooled models use within-season pressure percentile because league pressure environments differ by year. The primary defensive-quality outcome is sign-oriented EPA quality; success-rate and explosive-pass prevention are secondary outcomes. Four-man pressure efficiency, five-plus pressure efficiency, and five-plus usage are modeled separately.

### Layer 2
Creation quality is built from pressure rate, pass-rush win rate, true-pass-set pressure rate, and true-pass-set win rate. The components are stabilized toward season-position priors and standardized within season and position. Finishing is modeled separately through stabilized pressure-to-hit/sack conversion and does **not** alter creation standing. The four descriptive room archetypes are **Star + Depth, Heliocentric Star, Distributed Rotation, and Thin / Mixed**.

### Layer 3
The primary total-resource index equally weights within-season standardized cap commitment and active draft commitment, then re-standardizes the combined score within season. The primary lagged sample requires at least 80% opportunity-weighted cap coverage. Prior room quality is the equal-weight mean of previous-season creation percentiles among current resource-bearing players. Missing priors receive a neutral 50th-percentile value and are separately captured by unproven resource share.

Final explanatory models use season indicators and team-clustered standard errors. Overall and four-man pressure are modeled in percentage points. The frozen models enter resource commitment/concentration, prior room quality, continuity/unproven share, and resource-quality alignment sequentially.

## Reproducing the analysis

See [`docs/reproduction_guide.md`](docs/reproduction_guide.md) for the full run order and the distinction between:

- **public/canonical reproduction**, which starts from legally distributable canonical analytical files; and
- **full source reproduction**, which additionally requires licensed provider inputs that are not committed to the public repository.

The scripts currently use a `--data-dir` interface and expect their named inputs to be available under that directory. The reproduction guide uses an untracked `work/` staging directory to preserve the clean repository layout without changing the frozen scripts.

## Data availability and licensing

This repository intentionally separates **code**, **public-source data**, **provider-licensed data**, and **derived analytical data**.

Raw FTN and PFF source data are not intended for public redistribution. The Spotrac export is also treated as restricted pending confirmation of redistribution rights. Provider-derived canonical tables should be reviewed against the applicable licenses before a public release. See [`data/restricted/README.md`](data/restricted/README.md) and [`docs/data_provenance.md`](docs/data_provenance.md).

The MIT license in this repository applies to original code and repository documentation only. It does not grant rights to third-party data or provider content.

## Interpretation boundary

The study does **not** estimate one optimal defensive-front spending level or allocation structure. Its final claims are narrower: pressure is associated with stronger pass-defense outcomes; four-man pressure provides the clearest personnel-linked pathway; headliner and support quality both carry room-level signal; and, conditional on demonstrated room quality and the frozen room-construction controls, additional total resource commitment does not show a reliable positive incremental association with subsequent pressure in the observed sample.

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).
