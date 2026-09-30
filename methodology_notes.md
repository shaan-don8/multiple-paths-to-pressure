# Methodology notes

## Scope and design

**Multiple Paths to Pressure: Defensive-Front Talent Structure and Resource Allocation in the NFL** uses a three-layer observational design covering the 2022–2025 NFL seasons. Layers 1 and 2 contain all 32 defenses in each season (128 defense-seasons). Layer 3 requires previous-season player quality and begins in 2023; the frozen primary sample contains 82 qualifying team-seasons.

The analysis is associational. Temporal ordering in Layer 3 improves the interpretation of prior quality relative to subsequent pressure, but it does not identify a causal return to spending, draft investment, continuity, concentration, or any specific roster-construction strategy.

## Layer 1 — pressure and defensive outcomes

### Unit and sample
- Unit: defense-season.
- Period: 2022–2025.
- Sample: 128 defense-seasons and 80,719 eligible dropbacks.
- Eligible dropbacks include pass attempts, sacks, and quarterback scrambles; nullified plays are excluded.

### Pressure measures
Pressure is calculated overall and conditional on rush count. The primary pathway variables are:

- overall pressure rate,
- four-man pressure efficiency,
- five-plus-rusher pressure efficiency, and
- five-plus-rusher usage.

Four-man pressure is treated as the primary personnel-linked construction pathway because it measures disruption while preserving seven potential coverage defenders. Five-plus pressure efficiency and five-plus usage are kept separate to distinguish effectiveness from deployment frequency.

### Outcomes
The primary outcome is EPA allowed per eligible dropback, sign-oriented so larger values indicate better defense. Secondary outcomes are success-rate prevention and explosive-pass prevention. An explosive pass is defined as a pass play gaining at least 20 yards.

### Estimation
Pooled Layer 1 specifications use within-season pressure percentile because league pressure environments differ across years. The empirical program includes:

- OLS models of sign-oriented defensive quality,
- logistic GLMs for average-or-better and good-or-elite outcome probabilities,
- linear versus spline comparisons for threshold evidence,
- a 5,000-draw bootstrap for coefficient/IQR uncertainty, and
- a joint pathway model containing four-man pressure efficiency, five-plus pressure efficiency, and five-plus usage.

## Layer 2 — creation, finishing, and room structure

### Unit and sample
- Player canonical table: 1,709 player-team-season segments.
- Team/room table: 128 defensive-front team-seasons.
- Defensive-front scope: PFF edge defenders (ED) and defensive interior defenders (DI).

### Creation
Creation quality is constructed from:

1. pressure rate,
2. pass-rush win rate,
3. true-pass-set pressure rate, and
4. true-pass-set win rate.

Components are stabilized toward season-position priors, standardized within season and position, and paired with a volume component so full-time production is distinguished from small-sample efficiency.

### Finishing
Finishing is evaluated separately through stabilized conversion of pressures into hits or sacks. In the frozen V2 methodology, finishing **does not alter or override creation standing**. This separation reflects the fact that sacks and hits occur downstream from pressure and are more sensitive to quarterback behavior, teammate interaction, and play geometry.

### Room structure
- **Headliner quality:** quality of the room's leading creator.
- **Support quality:** opportunity-weighted creation quality of the remaining qualifying players.
- Descriptive room archetypes: **Star + Depth**, **Heliocentric Star**, **Distributed Rotation**, and **Thin / Mixed**.

The continuous headliner/support measures carry the primary inferential weight. Archetypes are rule-based descriptive summaries, not estimated latent classes or universal optimal categories.

### Estimation
Season-adjusted OLS models estimate the simultaneous relationships between headliner quality, support quality, and team pressure. Overall and four-man pressure are modeled separately.

## Layer 3 — resource allocation and prior room quality

### Total resource commitment
The frozen resource index combines salary-cap and draft inputs:

1. reconstruct defensive-front cap commitment from player-season cap hits;
2. divide observed room cap hit by the league salary cap and adjust for opportunity coverage;
3. annualize active homegrown draft investment using the Fitzgerald-Spielberger/OTC pick-value curve;
4. standardize cap and draft commitment within season;
5. equally weight the standardized cap and draft components; and
6. re-standardize the combined index within season.

The primary cap-coverage requirement is at least **80% of pass-rush opportunity**.

### Within-room allocation
A separate positive resource-unit scale is used to describe distribution within the room. Player resource units combine cap and draft units; each player's within-room resource share is player resource units divided by total room resource units.

Primary allocation variables include:

- top-player resource share,
- players 2–3 combined resource share,
- resource HHI,
- effective resource-player count,
- resource-quality alignment,
- unproven resource share, and
- returning prior rush share.

### Prior room quality
The primary prior-room-quality measure is the equal-weight mean of the previous-season creation percentiles of current resource-bearing players. A player without a valid prior receives a neutral 50th-percentile value; the share of current resources assigned to such players is tracked separately as `unproven_resource_share`.

Resource-weighted prior quality weights each player's prior percentile by current resource share. **Alignment** is the difference between resource-weighted prior quality and equal-weight prior room quality. **Continuity** is measured by returning prior rush share.

### Final explanatory models
The 82-row panel is modeled using season indicators and team-clustered standard errors. Overall and four-man pressure are expressed in percentage points. The nested sequence is:

1. resources and concentration,
2. prior room quality,
3. continuity and unproven resource share,
4. resource-quality alignment.

Separate specifications evaluate total resources, HHI, top-player resource share, and players 2–3 resource share.

## Temporal persistence and validation

### Prior-pressure persistence
Baseline persistence models compare previous team pressure with prior player-based room quality. Because raw prior pressure partly contains persistent player ability, the peer-review sensitivity constructs a player-adjusted prior-pressure residual:

1. within each prior season, predict team pressure from that season's headliner and support quality using leave-one-team-out estimation;
2. calculate observed minus expected prior pressure; and
3. shift that residual forward as a control in the subsequent-season persistence model.

### Retrospective 2025 holdout
- Training: 55 qualifying team-seasons from 2023–2024.
- Holdout: 27 qualifying defenses from 2025.
- Preprocessing parameters are estimated on the training sample only.
- Season indicators are excluded because a 2025 fixed effect cannot be estimated from the training years.

Evaluation metrics include MAE, RMSE, Pearson correlation, mean signed error, conventional test-set R-squared, and out-of-sample R-squared relative to the training-sample mean. This is a retrospective/pseudo-out-of-sample exercise, not an untouched prospective forecast.

## Peer-review sensitivity analyses

Three standalone V9 checks use the same frozen input system:

1. **Conditional resource test:** evaluates the incremental total-resource association after demonstrated room quality and full room-construction controls, plus a resource-by-quality interaction.
2. **Player-adjusted persistence test:** replaces raw prior pressure with the leave-one-team-out residual described above.
3. **FTN × PFF concordance audit:** quantifies provider agreement at the defense-season level while preserving their different analytical definitions.

## Claim discipline

The final evidence supports a pressure gradient with EPA and success-rate quality, a strong personnel-linked role for four-man pressure, and independent headliner/support associations with team pressure. It does **not** identify a universal optimal spending level, a preferred concentration structure, or a causal return to additional resource commitment. Null estimates are interpreted as lack of reliable evidence in the observed sample rather than proof that a mechanism can never matter.
