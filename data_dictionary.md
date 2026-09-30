# Data dictionary

This dictionary describes the canonical analytical files and source-side tables used by **Multiple Paths to Pressure: Defensive-Front Talent Structure and Resource Allocation in the NFL**. It prioritizes the variables that enter the frozen manuscript models. Full column inventories are provided for the mounted canonical files so that prefixed or audit-only fields remain discoverable without assigning unsupported interpretations to every inherited column.

## Naming conventions

- `_z`: standardized score, typically within season or within season-position as documented by the generating script.
- `_pct`: percentile/rank-style quantity unless the field name explicitly denotes percentage points.
- `_10`: rescaled variable where one regression unit represents 10 percentage points or 10 percentile points.
- `_pp`: quantity expressed directly in percentage points.
- `prior_`: previous-season player/team information shifted forward for lagged analysis.
- `layer2_`: field inherited into the final Layer 3 analytic panel from the Layer 2 / team-outcome merge.
- `resource_`: cap/draft resource construction or within-room resource distribution.

## Layer 1 team-season master

- **Repository path:** `data/canonical/layer1/Layer_1_Team_Season_Master.csv`
- **Grain:** defense-season
- **Period:** 2022–2025
- **Shape:** 128 rows × 49 columns
- **Role:** Canonical team pressure, rush-count pathway, and defensive-outcome panel used by Layer 1.
- **Release classification:** REVIEW_BEFORE_PUBLIC / provider-derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team` | Team abbreviation. |
| `dropbacks` | Eligible defensive dropbacks. |
| `pressures` | Pressure count. |
| `pressure_rate` | Pressures divided by eligible opportunity/dropbacks, depending on file grain. |
| `pressure_pct` | See methodology/provenance documentation and source script. |
| `rush_4_pressure_rate` | Pressure rate on four-man rushes. |
| `four_man_pressure_z` | Within-season standardized four-man pressure rate. |
| `rush_5_plus_pressure_rate` | Pressure rate when five or more rushers are sent. |
| `rush_5_plus_usage` | Share of eligible dropbacks with five or more rushers. |
| `epa_db` | EPA allowed per eligible dropback. |
| `epa_quality_z` | Sign-oriented EPA quality z-score; larger is better defense. |
| `success_rate_allowed` | Opponent success rate allowed. |
| `explosive_rate_allowed` | Explosive pass rate allowed. |

<details>
<summary>Full column inventory</summary>

```text
season, team, dropbacks, pressures, pressure_rate, pressure_z, pressure_pct, pressure_quintile
pressure_quartile, rush_3_or_less_db, rush_3_or_less_usage, rush_3_or_less_pressure_rate, rush_4_db
rush_4_usage, rush_4_pressure_rate, four_man_pressure_z, four_man_pressure_pct, rush_5_plus_db
rush_5_plus_usage, rush_5_plus_pressure_rate, five_plus_pressure_z, five_plus_pressure_pct
rush_6_plus_db, rush_6_plus_usage, rush_6_plus_pressure_rate, blitz_dependency, avg_rushers
avg_blockers, sacks, sack_rate, pressure_to_sack, scrambles, epa_db, epa_quality_z, epa_quality_pct
success_rate_allowed, success_quality_z, success_quality_pct, explosive_rate_allowed
explosive_quality_z, explosive_quality_pct, dvoa, dvoa_quality_z, dvoa_quality_pct
pass_defense_composite, pass_defense_composite_pct, above_avg_pass_defense
top_quartile_pass_defense, top_10_pass_defense
```

</details>

## Layer 2 player room master

- **Repository path:** `data/canonical/layer2/Layer_2_Player_Room_Master.csv`
- **Grain:** player-team-season segment
- **Period:** 2022–2025
- **Shape:** 1,709 rows × 26 columns
- **Role:** Canonical creation-quality and volume input for defensive-front ED/DI players.
- **Release classification:** REVIEW_BEFORE_PUBLIC / PFF-derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team` | Team abbreviation. |
| `player` | Player name. |
| `player_id` | Provider/player identifier used for joins. |
| `position` | Defensive-front position, primarily ED or DI. |
| `segment_share` | Share used to allocate a traded player-season to a team segment. |
| `rush_snaps` | Pass-rush/rush snap volume used in room weighting. |
| `pass_rush_opp` | Player pass-rush opportunities. |
| `pressures` | Pressure count. |
| `wins` | Pass-rush win count. |
| `pressure_rate` | Pressures divided by eligible opportunity/dropbacks, depending on file grain. |
| `win_rate` | Pass-rush wins divided by opportunities. |
| `tps_pressure_rate` | True-pass-set pressure rate. |
| `tps_win_rate` | True-pass-set pass-rush win rate. |
| `quality_z` | Season-position standardized creation-quality score. |
| `quality_pct` | Season-position creation-quality percentile. |
| `volume_pct` | Season-position volume percentile. |
| `star_index` | Creation/volume star index used in the canonical Layer 2 room build. |
| `rush_share` | See methodology/provenance documentation and source script. |
| `pressure_share` | See methodology/provenance documentation and source script. |

<details>
<summary>Full column inventory</summary>

```text
season, team, player, player_id, position, segment_type, segment_share, rush_snaps, pass_rush_opp
pressures, wins, pressure_rate, win_rate, tps_pressure_rate, tps_win_rate, shr_pressure_rate
shr_win_rate, quality_z, quality_pct, volume_pct, star_index, prior_quality_z, prior_available
rush_share, pressure_share, is_star
```

</details>

## Layer 2 team-season room master

- **Repository path:** `data/canonical/layer2/Layer_2_Team_Season_Room_Master.csv`
- **Grain:** defensive-front team-season
- **Period:** 2022–2025
- **Shape:** 128 rows × 177 columns
- **Role:** Room-level headliner/support structure joined to team pressure and defensive outcomes.
- **Release classification:** REVIEW_BEFORE_PUBLIC / provider-derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team` | Team abbreviation. |
| `room_players` | Number of player segments/players represented in the room. |
| `star_player` | See methodology/provenance documentation and source script. |
| `star_quality_z` | Creation quality of the leading rusher/headliner. |
| `support_quality_z` | Opportunity-weighted creation quality of qualifying non-headliner rushers. |
| `archetype` | Rule-based room archetype: Star + Depth, Heliocentric Star, Distributed Rotation, or Thin / Mixed. |
| `pressure_rate` | Pressures divided by eligible opportunity/dropbacks, depending on file grain. |
| `pressure_pct` | See methodology/provenance documentation and source script. |
| `rush_4_pressure_rate` | Pressure rate on four-man rushes. |
| `four_man_pressure_z` | Within-season standardized four-man pressure rate. |
| `rush_5_plus_pressure_rate` | Pressure rate when five or more rushers are sent. |
| `rush_5_plus_usage` | Share of eligible dropbacks with five or more rushers. |
| `epa_db` | EPA allowed per eligible dropback. |
| `epa_quality_z` | Sign-oriented EPA quality z-score; larger is better defense. |
| `success_rate_allowed` | Opponent success rate allowed. |
| `explosive_rate_allowed` | Explosive pass rate allowed. |

<details>
<summary>Full column inventory</summary>

```text
season, team, room_players, core_rushers_100, above_avg_rushers_100, high_quality_rushers_100
room_rush_snaps, room_pass_rush_opp, room_pressures, room_wins, room_player_pressure_rate
room_player_win_rate, snap_hhi, pressure_hhi, win_hhi, effective_rushers
effective_pressure_producers, top1_rush_share, top2_rush_share, top1_pressure_share
top2_pressure_share, pressure_concentration_gap, star_player, star_player_id, star_position
star_quality_z, star_quality_pct, star_volume_pct, star_index, star_rush_share, star_pressure_share
star_win_share, star_pressure_leverage, star_direct_dominance, star_gravity_distribution
second_player, second_quality_z, second_quality_pct, second_star_index, top2_quality_z
third_plus_quality_z, support_quality_z, support_pressure_rate, support_expected_pressure_rate
support_pressure_lift, support_win_rate, star_support_gap, trade_adjusted_players
trade_adjusted_rush_share, dropbacks, pressures, pressure_rate, pressure_z, pressure_pct
pressure_quintile, pressure_quartile, rush_3_or_less_db, rush_3_or_less_usage
rush_3_or_less_pressure_rate, rush_4_db, rush_4_usage, rush_4_pressure_rate, four_man_pressure_z
four_man_pressure_pct, rush_5_plus_db, rush_5_plus_usage, rush_5_plus_pressure_rate
five_plus_pressure_z, five_plus_pressure_pct, rush_6_plus_db, rush_6_plus_usage
rush_6_plus_pressure_rate, blitz_dependency, avg_rushers, avg_blockers, sacks, sack_rate
pressure_to_sack, scrambles, epa_db, epa_quality_z, epa_quality_pct, success_rate_allowed
success_quality_z, success_quality_pct, explosive_rate_allowed, explosive_quality_z
explosive_quality_pct, dvoa, dvoa_quality_z, dvoa_quality_pct, pass_defense_composite
pass_defense_composite_pct, above_avg_pass_defense, top_quartile_pass_defense, top_10_pass_defense
epa_defense_tier, composite_defense_tier, epa_at_least_average, epa_at_least_good, epa_elite
composite_at_least_average, composite_at_least_good, composite_elite, star_quality_z_filled
star_quality_z_z, star_quality_z_pct, star_index_filled, star_index_z, star_index_pct
support_quality_z_filled, support_quality_z_z, support_quality_z_pct, top2_quality_z_filled
top2_quality_z_z, top2_quality_z_pct, third_plus_quality_z_filled, third_plus_quality_z_z
third_plus_quality_z_pct, second_quality_z_filled, second_quality_z_z, second_quality_z_pct
snap_hhi_filled, snap_hhi_z, snap_hhi_pct, pressure_hhi_filled, pressure_hhi_z, pressure_hhi_pct
pressure_concentration_gap_filled, pressure_concentration_gap_z, pressure_concentration_gap_pct
effective_rushers_filled, effective_rushers_z, effective_rushers_pct
effective_pressure_producers_filled, effective_pressure_producers_z
effective_pressure_producers_pct, star_pressure_leverage_filled, star_pressure_leverage_z
star_pressure_leverage_pct, star_direct_dominance_filled, star_direct_dominance_z
star_direct_dominance_pct, star_gravity_distribution_filled, star_gravity_distribution_z
star_gravity_distribution_pct, support_pressure_lift_filled, support_pressure_lift_z
support_pressure_lift_pct, core_rushers_100_filled, core_rushers_100_z, core_rushers_100_pct
above_avg_rushers_100_filled, above_avg_rushers_100_z, above_avg_rushers_100_pct
high_quality_rushers_100_filled, high_quality_rushers_100_z, high_quality_rushers_100_pct
room_player_pressure_rate_filled, room_player_pressure_rate_z, room_player_pressure_rate_pct
room_player_win_rate_filled, room_player_win_rate_z, room_player_win_rate_pct
star_support_gap_filled, star_support_gap_z, star_support_gap_pct, trade_adjusted_rush_share_filled
trade_adjusted_rush_share_z, trade_adjusted_rush_share_pct, good_pressure, elite_access_pressure
top_pressure_quintile, star_support_interaction, archetype, gravity_candidate, gravity_proxy_score
```

</details>

## Layer 2 player pressure-impact master

- **Repository path:** `data/canonical/layer2/Layer_2_Player_Pressure_Impact_Master.csv`
- **Grain:** player-season
- **Period:** 2022–2025
- **Shape:** 3,417 rows × 32 columns
- **Role:** Finishing/conversion input used by the frozen creation-first V2 Layer 2 script.
- **Release classification:** REVIEW_BEFORE_PUBLIC / PFF-derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `player` | Player name. |
| `player_id` | Provider/player identifier used for joins. |
| `position` | Defensive-front position, primarily ED or DI. |
| `pass_rush_opp` | Player pass-rush opportunities. |
| `total_pressures` | Player pressure total used by the finishing file. |
| `sacks` | Sack count. |
| `hits` | Quarterback hit count. |
| `hurries` | Hurry count. |
| `shr_contact_conversion` | Stabilized share of pressures becoming sacks or hits. |
| `shr_contact_conversion_pct` | Percentile of stabilized contact conversion. |
| `pressure_impact_z` | Composite/standardized pressure-finishing impact measure retained in the source file. |
| `pressure_impact_pct` | Percentile counterpart of pressure impact. |

<details>
<summary>Full column inventory</summary>

```text
season, player, player_id, position, team_name, pass_rush_opp, total_pressures, sacks, hits, hurries
contact_pressures, contact_conversion, sack_conversion, hit_conversion, hurry_share
true_pass_set_total_pressures, true_pass_set_sacks, true_pass_set_hits, true_pass_set_hurries
tps_contact_pressures, tps_contact_conversion, shr_contact_conversion, shr_sack_conversion
shr_tps_contact_conversion, shr_contact_conversion_z, shr_sack_conversion_z
shr_tps_contact_conversion_z, shr_contact_conversion_pct, shr_sack_conversion_pct
shr_tps_contact_conversion_pct, pressure_impact_z, pressure_impact_pct
```

</details>

## Final Layer 2 player creation canonical

- **Repository path:** `data/canonical/layer2/MODEL_Layer2_PlayerTeamSeason_2022-2025_CreationCanonical.csv`
- **Grain:** player-team-season segment
- **Period:** 2022–2025
- **Shape:** 1,709 rows × 85 columns
- **Role:** Frozen creation-first player table that combines the canonical player-room construction with finishing fields and rebuild/audit fields.
- **Release classification:** REVIEW_BEFORE_PUBLIC / PFF-derived

Key fields include `quality_z`, `quality_pct`, `creation_score`, `creation_tier`, `finish_pct`, `finish_tier`, `prior_pressure_rate`, and rebuilt true-pass-set/shrinkage audit fields.

<details>
<summary>Full column inventory</summary>

```text
season, team, player, player_id, position, segment_type, segment_share, rush_snaps, pass_rush_opp
pressures, wins, pressure_rate, win_rate, tps_pressure_rate, tps_win_rate, shr_pressure_rate
shr_win_rate, quality_z, quality_pct, volume_pct, star_index, prior_quality_z, prior_available
rush_share, pressure_share, is_star, name_norm, id_key, name_norm_finish, position_finish
total_pressures, sacks, hits, hurries, shr_contact_conversion, shr_contact_conversion_pct
shr_sack_conversion, shr_sack_conversion_pct, shr_tps_contact_conversion
shr_tps_contact_conversion_pct, finish_available, creation_z, creation_pct, creation_score
creation_tier, is_creation_star, finish_pct, finish_rate_shrunk, finish_tier
player_creation_finish_profile, creation_sort_key, finish_tiebreak_key, raw_player, raw_position
raw_pass_rush_opp, raw_rush_snaps, raw_pressures, raw_wins, raw_tps_opp, raw_tps_pressures
raw_tps_wins, canonical_player_season_opp, team_segment_share, tps_opp_rebuilt
tps_pressures_rebuilt, tps_wins_rebuilt, tps_pressure_rate_rebuilt, tps_win_rate_rebuilt
prior_pressure_rate, prior_win_rate, prior_tps_pressure_rate, prior_tps_win_rate
shr_pressure_rate_rebuilt, shr_win_rate_rebuilt, shr_tps_pressure_rate_rebuilt
shr_tps_win_rate_rebuilt, team_segments, two_team_player_season, pressure_shrinkage_mismatch
win_shrinkage_mismatch, shr_pressure_rate_full_season, shr_win_rate_full_season
shr_tps_pressure_rate_full_season, shr_tps_win_rate_full_season, creation_method_version
```

</details>

## Final Layer 2 team creation-room canonical

- **Repository path:** `data/canonical/layer2/MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical.csv`
- **Grain:** defensive-front team-season
- **Period:** 2022–2025
- **Shape:** 128 rows × 219 columns
- **Role:** Final 128-row Layer 2 room table used by the V9 player-adjusted persistence and FTN×PFF concordance checks. It contains PFF room creation measures and the merged FTN overall/four-man pressure fields.
- **Release classification:** REVIEW_BEFORE_PUBLIC / provider-derived

Key fields include `room_player_pressure_rate`, `star_quality_z`, `support_quality_z`, `archetype`, `pressure_rate`, `four_man_pressure_rate`, `five_plus_pressure_rate`, and `five_plus_usage`.

<details>
<summary>Full column inventory</summary>

```text
season, team, room_players, core_rushers_100, above_avg_rushers_100, high_quality_rushers_100
room_rush_snaps, room_pass_rush_opp, room_pressures, room_wins, room_player_pressure_rate
room_player_win_rate, snap_hhi, pressure_hhi, win_hhi, effective_rushers
effective_pressure_producers, top1_rush_share, top2_rush_share, top1_pressure_share
top2_pressure_share, pressure_concentration_gap, star_player, star_player_id, star_position
star_quality_z, star_quality_pct, star_volume_pct, star_index, star_rush_share, star_pressure_share
star_win_share, star_pressure_leverage, star_direct_dominance, star_gravity_distribution
second_player, second_quality_z, second_quality_pct, second_star_index, top2_quality_z
third_plus_quality_z, support_quality_z, support_pressure_rate, support_expected_pressure_rate
support_pressure_lift, support_win_rate, star_support_gap, trade_adjusted_players
trade_adjusted_rush_share, star_quality_z_filled, star_quality_z_z, star_quality_z_pct
star_index_filled, star_index_z, star_index_pct, support_quality_z_filled, support_quality_z_z
support_quality_z_pct, top2_quality_z_filled, top2_quality_z_z, top2_quality_z_pct
third_plus_quality_z_filled, third_plus_quality_z_z, third_plus_quality_z_pct
second_quality_z_filled, second_quality_z_z, second_quality_z_pct, snap_hhi_filled, snap_hhi_z
snap_hhi_pct, pressure_hhi_filled, pressure_hhi_z, pressure_hhi_pct
pressure_concentration_gap_filled, pressure_concentration_gap_z, pressure_concentration_gap_pct
effective_rushers_filled, effective_rushers_z, effective_rushers_pct
effective_pressure_producers_filled, effective_pressure_producers_z
effective_pressure_producers_pct, star_pressure_leverage_filled, star_pressure_leverage_z
star_pressure_leverage_pct, star_direct_dominance_filled, star_direct_dominance_z
star_direct_dominance_pct, star_gravity_distribution_filled, star_gravity_distribution_z
star_gravity_distribution_pct, support_pressure_lift_filled, support_pressure_lift_z
support_pressure_lift_pct, core_rushers_100_filled, core_rushers_100_z, core_rushers_100_pct
above_avg_rushers_100_filled, above_avg_rushers_100_z, above_avg_rushers_100_pct
high_quality_rushers_100_filled, high_quality_rushers_100_z, high_quality_rushers_100_pct
room_player_pressure_rate_filled, room_player_pressure_rate_z, room_player_pressure_rate_pct
room_player_win_rate_filled, room_player_win_rate_z, room_player_win_rate_pct
star_support_gap_filled, star_support_gap_z, star_support_gap_pct, trade_adjusted_rush_share_filled
trade_adjusted_rush_share_z, trade_adjusted_rush_share_pct, star_support_interaction, archetype
gravity_candidate, gravity_proxy_score, allocated_pressures, allocated_sacks, allocated_hits
allocated_hurries, allocated_contact_pressures, finish_covered_rush_snaps, total_room_rush_snaps
room_contact_conversion, room_sack_conversion, finish_coverage_share, room_finish_pct, room_finish_z
room_finish_tier, headliner_player, headliner_player_id, headliner_position
headliner_creation_score, headliner_creation_tier, headliner_is_creation_star, headliner_finish_pct
headliner_finish_tier, headliner_profile, creation_finish_room_label, source_play_rows
nullified_rows, eligible_dropbacks, pressured_dropbacks, pressure_rate, pressure_percentile
three_or_fewer_dropbacks_legacy, three_or_fewer_pressures_legacy
three_or_fewer_pressure_rate_legacy, play_success_count, play_success_observations
play_success_rate_pct, play_explosive_passes_20, play_explosive_rate_pct, play_pass_attempt_proxy
team_games, team_att, team_com, team_com_pct, team_yds, team_ypa, team_td, team_epa, team_epa_per_db
epa_quality, epa_quality_percentile, epa_tier, average_or_better, good_or_elite, team_dvoa, team_int
team_tow, team_tow_pct, team_ycom, team_yac, team_yac_per_att, team_yac_per_com, team_yds_per_game
team_acc_pct, team_suc_pct, team_acom_pct, team_exp, team_exp_pct, team_exyd, team_extd, team_hl
team_hl_pct, team_dr, team_dr_pct, team_td_pct, team_int_pct, team_pbu, team_bat, att_difference
success_rate_difference_pct, explosive_rate_difference_pct, unclassified_rush_dropbacks
classified_rush_dropbacks, classified_rush_share, three_or_fewer_dropbacks, three_or_fewer_pressures
three_or_fewer_pressure_rate, four_man_dropbacks, four_man_pressures, four_man_pressure_rate
five_plus_dropbacks, five_plus_pressures, five_plus_pressure_rate, five_plus_usage
legacy_support_expected_pressure_rate, legacy_support_pressure_lift
legacy_support_pressure_lift_filled, legacy_support_pressure_lift_z
legacy_support_pressure_lift_pct, support_expectation_lineage_status, creation_room_method_version
finishing_method_status
```

</details>

## Layer 3 total resource index

- **Repository path:** `data/canonical/layer3/MODEL_Layer3_TeamSeason_TotalResourceIndex_2022-2025_v1.csv`
- **Grain:** team-season
- **Period:** 2022–2025
- **Shape:** 128 rows × 32 columns
- **Role:** Full 128-row cap-and-draft resource-index panel.
- **Release classification:** REVIEW_BEFORE_PUBLIC / derived from restricted + public inputs

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team_key` | Canonical team abbreviation/key. |
| `cap_opportunity_coverage` | Share of modeled room pass-rush opportunity covered by matched cap records. |
| `cap_high_coverage` | Indicator for meeting the primary cap-coverage threshold. |
| `coverage_adjusted_cap_share` | Observed modeled room cap share adjusted for cap-match opportunity coverage. |
| `active_draft_otc_strict` | Annualized active homegrown draft investment under the strict four-year rookie-control treatment. |
| `total_resource_index` | Season-standardized combined cap-and-draft resource index. |
| `total_resource_percentile` | Within-season percentile of the total resource index. |

<details>
<summary>Full column inventory</summary>

```text
season, team_key, cap_opportunity_coverage, cap_high_coverage, observed_modeled_room_cap_hit
observed_modeled_room_cap_share, coverage_adjusted_cap_share, active_draft_otc_strict
active_draft_otc_5yr, draft_otc_z_strict, draft_otc_z_5yr, active_draft_otc_hhi_strict
active_draft_otc_top1_share_strict, active_draft_otc_effective_players_strict
homegrown_active_rookie_count_strict, acquired_active_rookie_count_strict
homegrown_rookie_rush_share_strict, homegrown_rookie_pressure_share_strict, cap_adjusted_z
cap_observed_z, draft_otc_z_strict_recomputed, draft_otc_z_5yr_recomputed
draft_otc_z_strict_difference, draft_otc_z_5yr_difference, total_resource_index_raw
total_resource_index, total_resource_rank, total_resource_percentile
resource_index_observed_cap_raw, resource_index_observed_cap, resource_index_otc_5yr_raw
resource_index_otc_5yr
```

</details>

## Layer 3 primary resource-index sample

- **Repository path:** `data/canonical/layer3/MODEL_Layer3_PrimarySample_TotalResourceIndex_2023-2025_v1.csv`
- **Grain:** team-season
- **Period:** 2023–2025
- **Shape:** 82 rows × 32 columns
- **Role:** 82-row lagged primary sample restricted to qualifying resource coverage.
- **Release classification:** REVIEW_BEFORE_PUBLIC / derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team_key` | Canonical team abbreviation/key. |
| `cap_opportunity_coverage` | Share of modeled room pass-rush opportunity covered by matched cap records. |
| `cap_high_coverage` | Indicator for meeting the primary cap-coverage threshold. |
| `coverage_adjusted_cap_share` | Observed modeled room cap share adjusted for cap-match opportunity coverage. |
| `active_draft_otc_strict` | Annualized active homegrown draft investment under the strict four-year rookie-control treatment. |
| `total_resource_index` | Season-standardized combined cap-and-draft resource index. |

<details>
<summary>Full column inventory</summary>

```text
season, team_key, cap_opportunity_coverage, cap_high_coverage, observed_modeled_room_cap_hit
observed_modeled_room_cap_share, coverage_adjusted_cap_share, active_draft_otc_strict
active_draft_otc_5yr, draft_otc_z_strict, draft_otc_z_5yr, active_draft_otc_hhi_strict
active_draft_otc_top1_share_strict, active_draft_otc_effective_players_strict
homegrown_active_rookie_count_strict, acquired_active_rookie_count_strict
homegrown_rookie_rush_share_strict, homegrown_rookie_pressure_share_strict, cap_adjusted_z
cap_observed_z, draft_otc_z_strict_recomputed, draft_otc_z_5yr_recomputed
draft_otc_z_strict_difference, draft_otc_z_5yr_difference, total_resource_index_raw
total_resource_index, total_resource_rank, total_resource_percentile
resource_index_observed_cap_raw, resource_index_observed_cap, resource_index_otc_5yr_raw
resource_index_otc_5yr
```

</details>

## Layer 3 player resource allocation

- **Repository path:** `data/canonical/layer3/MODEL_Layer3_PlayerResourceAllocation_2022-2025_v1.csv`
- **Grain:** player-team-season segment
- **Period:** 2022–2025
- **Shape:** 1,709 rows × 52 columns
- **Role:** Player-level cap/draft units, room resource shares, and lagged player-quality bridge.
- **Release classification:** REVIEW_BEFORE_PUBLIC / derived from provider data

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team_key` | Canonical team abbreviation/key. |
| `player_id` | Provider/player identifier used for joins. |
| `player` | Player name. |
| `position` | Defensive-front position, primarily ED or DI. |
| `pass_rush_opportunities` | Player pass-rush opportunities. |
| `spotrac_cap_hit` | See methodology/provenance documentation and source script. |
| `player_cap_units` | Player cap share divided by the season mean observed player cap share. |
| `player_draft_units` | Player annualized draft value divided by the season mean annualized active draft value. |
| `player_resource_units` | Positive additive player resource units combining cap and draft units 50/50. |
| `room_resource_share` | Player resource units divided by team-season room resource units. |
| `prior_available` | Indicator that a valid previous-season player prior exists. |
| `prior_quality_z` | Previous-season creation-quality z-score. |
| `prior_quality_pct` | Previous-season creation-quality percentile; neutral 0.50 when prior is unavailable in Layer 3. |
| `prior_creation_score` | See methodology/provenance documentation and source script. |

<details>
<summary>Full column inventory</summary>

```text
resource_row_id, season, team_key, player_id, player, position, pass_rush_opportunities
spotrac_cap_hit, salary_cap_dollars, player_cap_share, cap_matched, draft_matched, draft_year
draft_team_key, overall_pick, homegrown_active_rookie_strict, acquired_active_rookie_strict
draft_otc_annual_strict, draft_otc_annual_5yr, cap_opportunity_coverage, cap_high_coverage
observed_modeled_room_cap_share, coverage_adjusted_cap_share, active_draft_otc_strict
cap_adjusted_z, draft_otc_z_strict_recomputed, total_resource_index, player_cap_pct
season_mean_player_cap_pct, season_mean_draft_otc_strict, player_cap_units, player_draft_units
player_resource_units, total_player_cap_units, total_player_draft_units, total_player_resource_units
room_cap_resource_share, room_draft_resource_share, room_resource_share, room_resource_rank
pass_rush_opp, pressures, quality_z, quality_pct, creation_score, pressure_rate, prior_available
prior_quality_z, prior_quality_pct, prior_creation_score, prior_pressure_rate, prior_pass_rush_opp
```

</details>

## Layer 3 team resource allocation

- **Repository path:** `data/canonical/layer3/MODEL_Layer3_TeamResourceAllocation_2022-2025_v1.csv`
- **Grain:** team-season
- **Period:** 2022–2025
- **Shape:** 128 rows × 99 columns
- **Role:** Full allocation/concentration/quality/continuity panel used to define the final lagged specification.
- **Release classification:** REVIEW_BEFORE_PUBLIC / derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team_key` | Canonical team abbreviation/key. |
| `total_resource_index` | Season-standardized combined cap-and-draft resource index. |
| `top1_resource_share` | Share of room resource units assigned to the highest-resource player. |
| `players_2_3_resource_share` | Combined resource share assigned to the second- and third-highest-resource players. |
| `resource_hhi` | Herfindahl-Hirschman Index of within-room player resource shares. |
| `effective_resource_players` | Effective number of resource players implied by concentration. |
| `resource_quality_alignment` | Resource-share-weighted prior player quality. |
| `unproven_resource_share` | Resource share assigned to players without a valid previous-season creation prior. |
| `returning_prior_rush_share` | Share of prior-season room pass-rush opportunity accounted for by current returning players. |
| `top1_resource_share_10` | Top-player resource share scaled so one unit equals 10 percentage points. |
| `players_2_3_resource_share_10` | Players 2–3 resource share scaled in 10-point units. |
| `unproven_resource_share_10` | Unproven resource share scaled in 10-point units. |
| `returning_prior_rush_share_10` | Returning prior rush share scaled in 10-point units. |

<details>
<summary>Full column inventory</summary>

```text
season, team_key, cap_opportunity_coverage, cap_high_coverage, observed_modeled_room_cap_hit
observed_modeled_room_cap_share, coverage_adjusted_cap_share, active_draft_otc_strict
active_draft_otc_5yr, draft_otc_z_strict, draft_otc_z_5yr, active_draft_otc_hhi_strict
active_draft_otc_top1_share_strict, active_draft_otc_effective_players_strict
homegrown_active_rookie_count_strict, acquired_active_rookie_count_strict
homegrown_rookie_rush_share_strict, homegrown_rookie_pressure_share_strict, cap_adjusted_z
cap_observed_z, draft_otc_z_strict_recomputed, draft_otc_z_5yr_recomputed
draft_otc_z_strict_difference, draft_otc_z_5yr_difference, total_resource_index_raw
total_resource_index, total_resource_rank, total_resource_percentile
resource_index_observed_cap_raw, resource_index_observed_cap, resource_index_otc_5yr_raw
resource_index_otc_5yr, top1_resource_share, top2_resource_share, top3_resource_share
player_2_resource_share, player_3_resource_share, players_2_3_resource_share
third_plus_resource_share, fourth_plus_resource_share, resource_hhi, effective_resource_players
players_for_50pct_resources, players_for_70pct_resources, players_for_80pct_resources
top1_cap_share, top2_cap_share, top3_cap_share, cap_resource_hhi, effective_cap_players
top1_draft_share, top2_draft_share, top3_draft_share, draft_resource_hhi, effective_draft_players
resource_shape_detail, resource_shape_primary, top_resource_player, second_resource_player
third_resource_player, prior_best_quality_z, prior_second_quality_z, prior_third_quality_z
prior_support_quality_z, resource_quality_alignment, resource_prior_rank_spearman
resource_share_prior_high_end, resource_share_prior_primary, resource_share_prior_depth
unproven_resource_share, top1_resource_prior_quality_pct, core_2_3_prior_quality_pct
returning_prior_rush_share, prior_model_eligible, resource_index, top1_resource_share_pct
top2_resource_share_pct, top3_resource_share_pct, resource_quality_alignment_pct
unproven_resource_share_pct, resource_index_pct, prior_support_quality_z_pct, allocation_strategy
alignment_tier, investment_tier, top1_resource_share_10, players_2_3_resource_share_10
resource_quality_alignment_10, unproven_resource_share_10, returning_prior_rush_share_10
top1_cap_share_10, top1_draft_share_10, shape_single_player, shape_multi_player_core
detail_single_player, detail_two_player_core, detail_three_player_core
top1_resource_share_centered_10, top1_resource_share_centered_10_sq
```

</details>

## Final Layer 3 analytic panel

- **Repository path:** `data/canonical/layer3/MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv`
- **Grain:** team-season
- **Period:** 2023–2025
- **Shape:** 82 rows × 338 columns
- **Role:** Locked 82-row modeling panel combining resource allocation, prior room quality, Layer 2 room variables, and current pressure/outcomes.
- **Release classification:** REVIEW_BEFORE_PUBLIC / derived

| Field | Meaning |
|---|---|
| `season` | NFL season. |
| `team_key` | Canonical team abbreviation/key. |
| `total_resource_index` | Season-standardized combined cap-and-draft resource index. |
| `top1_resource_share_10` | Top-player resource share scaled so one unit equals 10 percentage points. |
| `players_2_3_resource_share_10` | Players 2–3 resource share scaled in 10-point units. |
| `resource_quality_alignment` | Resource-share-weighted prior player quality. |
| `unproven_resource_share_10` | Unproven resource share scaled in 10-point units. |
| `returning_prior_rush_share_10` | Returning prior rush share scaled in 10-point units. |
| `layer2_headliner_quality_z` | See methodology/provenance documentation and source script. |
| `layer2_support_quality_z` | See methodology/provenance documentation and source script. |
| `layer2_overall_pressure_rate_pp` | Current overall pressure rate expressed in percentage points for final Layer 3 models. |
| `layer2_four_man_pressure_rate_pp` | Current four-man pressure rate expressed in percentage points for final Layer 3 models. |

<details>
<summary>Full column inventory</summary>

```text
season, team_key, cap_opportunity_coverage, cap_high_coverage, observed_modeled_room_cap_hit
observed_modeled_room_cap_share, coverage_adjusted_cap_share, active_draft_otc_strict
active_draft_otc_5yr, draft_otc_z_strict, draft_otc_z_5yr, active_draft_otc_hhi_strict
active_draft_otc_top1_share_strict, active_draft_otc_effective_players_strict
homegrown_active_rookie_count_strict, acquired_active_rookie_count_strict
homegrown_rookie_rush_share_strict, homegrown_rookie_pressure_share_strict, cap_adjusted_z
cap_observed_z, draft_otc_z_strict_recomputed, draft_otc_z_5yr_recomputed
draft_otc_z_strict_difference, draft_otc_z_5yr_difference, total_resource_index_raw
total_resource_index, total_resource_rank, total_resource_percentile
resource_index_observed_cap_raw, resource_index_observed_cap, resource_index_otc_5yr_raw
resource_index_otc_5yr, top1_resource_share, top2_resource_share, top3_resource_share
player_2_resource_share, player_3_resource_share, players_2_3_resource_share
third_plus_resource_share, fourth_plus_resource_share, resource_hhi, effective_resource_players
players_for_50pct_resources, players_for_70pct_resources, players_for_80pct_resources
top1_cap_share, top2_cap_share, top3_cap_share, cap_resource_hhi, effective_cap_players
top1_draft_share, top2_draft_share, top3_draft_share, draft_resource_hhi, effective_draft_players
resource_shape_detail, resource_shape_primary, top_resource_player, second_resource_player
third_resource_player, prior_best_quality_z, prior_second_quality_z, prior_third_quality_z
prior_support_quality_z, resource_quality_alignment, resource_prior_rank_spearman
resource_share_prior_high_end, resource_share_prior_primary, resource_share_prior_depth
unproven_resource_share, top1_resource_prior_quality_pct, core_2_3_prior_quality_pct
returning_prior_rush_share, prior_model_eligible, resource_index, top1_resource_share_pct
top2_resource_share_pct, top3_resource_share_pct, resource_quality_alignment_pct
unproven_resource_share_pct, resource_index_pct, prior_support_quality_z_pct, allocation_strategy
alignment_tier, investment_tier, top1_resource_share_10, players_2_3_resource_share_10
resource_quality_alignment_10, unproven_resource_share_10, returning_prior_rush_share_10
top1_cap_share_10, top1_draft_share_10, shape_single_player, shape_multi_player_core
detail_single_player, detail_two_player_core, detail_three_player_core
top1_resource_share_centered_10, top1_resource_share_centered_10_sq, team_key_model, layer2_team
layer2_room_players, layer2_core_rushers_100, layer2_above_avg_rushers_100
layer2_high_quality_rushers_100, layer2_room_rush_snaps, layer2_room_pass_rush_opp
layer2_room_pressures, layer2_room_wins, layer2_room_player_pressure_rate
layer2_room_player_win_rate, layer2_snap_hhi, layer2_pressure_hhi, layer2_win_hhi
layer2_effective_rushers, layer2_effective_pressure_producers, layer2_top1_rush_share
layer2_top2_rush_share, layer2_top1_pressure_share, layer2_top2_pressure_share
layer2_pressure_concentration_gap, layer2_star_player, layer2_star_player_id, layer2_star_position
layer2_star_quality_z, layer2_star_quality_pct, layer2_star_volume_pct, layer2_star_index
layer2_star_rush_share, layer2_star_pressure_share, layer2_star_win_share
layer2_star_pressure_leverage, layer2_star_direct_dominance, layer2_star_gravity_distribution
layer2_second_player, layer2_second_quality_z, layer2_second_quality_pct, layer2_second_star_index
layer2_top2_quality_z, layer2_third_plus_quality_z, layer2_support_quality_z
layer2_support_pressure_rate, layer2_support_expected_pressure_rate, layer2_support_pressure_lift
layer2_support_win_rate, layer2_star_support_gap, layer2_trade_adjusted_players
layer2_trade_adjusted_rush_share, layer2_star_quality_z_filled, layer2_star_quality_z_z
layer2_star_quality_z_pct, layer2_star_index_filled, layer2_star_index_z, layer2_star_index_pct
layer2_support_quality_z_filled, layer2_support_quality_z_z, layer2_support_quality_z_pct
layer2_top2_quality_z_filled, layer2_top2_quality_z_z, layer2_top2_quality_z_pct
layer2_third_plus_quality_z_filled, layer2_third_plus_quality_z_z, layer2_third_plus_quality_z_pct
layer2_second_quality_z_filled, layer2_second_quality_z_z, layer2_second_quality_z_pct
layer2_snap_hhi_filled, layer2_snap_hhi_z, layer2_snap_hhi_pct, layer2_pressure_hhi_filled
layer2_pressure_hhi_z, layer2_pressure_hhi_pct, layer2_pressure_concentration_gap_filled
layer2_pressure_concentration_gap_z, layer2_pressure_concentration_gap_pct
layer2_effective_rushers_filled, layer2_effective_rushers_z, layer2_effective_rushers_pct
layer2_effective_pressure_producers_filled, layer2_effective_pressure_producers_z
layer2_effective_pressure_producers_pct, layer2_star_pressure_leverage_filled
layer2_star_pressure_leverage_z, layer2_star_pressure_leverage_pct
layer2_star_direct_dominance_filled, layer2_star_direct_dominance_z
layer2_star_direct_dominance_pct, layer2_star_gravity_distribution_filled
layer2_star_gravity_distribution_z, layer2_star_gravity_distribution_pct
layer2_support_pressure_lift_filled, layer2_support_pressure_lift_z
layer2_support_pressure_lift_pct, layer2_core_rushers_100_filled, layer2_core_rushers_100_z
layer2_core_rushers_100_pct, layer2_above_avg_rushers_100_filled, layer2_above_avg_rushers_100_z
layer2_above_avg_rushers_100_pct, layer2_high_quality_rushers_100_filled
layer2_high_quality_rushers_100_z, layer2_high_quality_rushers_100_pct
layer2_room_player_pressure_rate_filled, layer2_room_player_pressure_rate_z
layer2_room_player_pressure_rate_pct, layer2_room_player_win_rate_filled
layer2_room_player_win_rate_z, layer2_room_player_win_rate_pct, layer2_star_support_gap_filled
layer2_star_support_gap_z, layer2_star_support_gap_pct, layer2_trade_adjusted_rush_share_filled
layer2_trade_adjusted_rush_share_z, layer2_trade_adjusted_rush_share_pct
layer2_star_support_interaction, layer2_archetype, layer2_gravity_candidate
layer2_gravity_proxy_score, layer2_allocated_pressures, layer2_allocated_sacks
layer2_allocated_hits, layer2_allocated_hurries, layer2_allocated_contact_pressures
layer2_finish_covered_rush_snaps, layer2_total_room_rush_snaps, layer2_room_contact_conversion
layer2_room_sack_conversion, layer2_finish_coverage_share, layer2_room_finish_pct
layer2_room_finish_z, layer2_headliner_player, layer2_headliner_player_id, layer2_headliner_position
layer2_headliner_creation_score, layer2_headliner_creation_tier, layer2_headliner_is_creation_star
layer2_headliner_finish_pct, layer2_headliner_profile, layer2_legacy_support_expected_pressure_rate
layer2_legacy_support_pressure_lift, layer2_legacy_support_pressure_lift_filled
layer2_legacy_support_pressure_lift_z, layer2_legacy_support_pressure_lift_pct
layer2_support_expectation_lineage_status, layer2_creation_room_method_version
layer2_creation_finish_room_label_rebuilt_x, layer2_room_contact_conversion_1
layer2_room_contact_conversion_pct, layer2_room_finish_tier, layer2_headliner_contact_conversion_pct
layer2_headliner_finish_tier, layer2_creation_finish_room_label_rebuilt_y
layer2_finishing_method_status, layer2_finishing_method_version, layer2_source_play_rows
layer2_nullified_rows, layer2_eligible_dropbacks, layer2_pressured_dropbacks, layer2_pressure_rate
layer2_pressure_percentile, layer2_three_or_fewer_dropbacks_legacy
layer2_three_or_fewer_pressures_legacy, layer2_three_or_fewer_pressure_rate_legacy
layer2_play_success_count, layer2_play_success_observations, layer2_play_success_rate_pct
layer2_play_explosive_passes_20, layer2_play_explosive_rate_pct, layer2_play_pass_attempt_proxy
layer2_team_games, layer2_team_att, layer2_team_com, layer2_team_com_pct, layer2_team_yds
layer2_team_ypa, layer2_team_td, layer2_team_epa, layer2_team_epa_per_db, layer2_epa_quality
layer2_epa_quality_percentile, layer2_epa_tier, layer2_average_or_better, layer2_good_or_elite
layer2_team_dvoa, layer2_team_int, layer2_team_tow, layer2_team_tow_pct, layer2_team_ycom
layer2_team_yac, layer2_team_yac_per_att, layer2_team_yac_per_com, layer2_team_yds_per_game
layer2_team_acc_pct, layer2_team_suc_pct, layer2_team_acom_pct, layer2_team_exp, layer2_team_exp_pct
layer2_team_exyd, layer2_team_extd, layer2_team_hl, layer2_team_hl_pct, layer2_team_dr
layer2_team_dr_pct, layer2_team_td_pct, layer2_team_int_pct, layer2_team_pbu, layer2_team_bat
layer2_att_difference, layer2_success_rate_difference_pct, layer2_explosive_rate_difference_pct
layer2_unclassified_rush_dropbacks, layer2_classified_rush_dropbacks, layer2_classified_rush_share
layer2_three_or_fewer_dropbacks, layer2_three_or_fewer_pressures
layer2_three_or_fewer_pressure_rate, layer2_four_man_dropbacks, layer2_four_man_pressures
layer2_four_man_pressure_rate, layer2_five_plus_dropbacks, layer2_five_plus_pressures
layer2_five_plus_pressure_rate, layer2_five_plus_usage, layer2_headliner_quality_z
layer2_headliner_support_interaction, layer2_headliner_creation_score_z, layer2_top_two_quality_z
layer2_overall_pressure_rate_pp, layer2_four_man_pressure_rate_pp, layer2_five_plus_pressure_rate_pp
layer2_epa_quality_per_dropback, layer2_success_defense_quality_pp
layer2_explosive_defense_quality_pp, layer2_arch_star_depth, layer2_arch_heliocentric
layer2_arch_distributed, layer2_room_finishing_z, layer2_headliner_finishing_z
```

</details>

## Public draft classes

- **Repository path:** `data/public_sources/draft_classes_2018_2025.csv`
- **Grain:** draft selection
- **Period:** 2018–2025
- **Shape:** 2,059 rows × 10 columns
- **Role:** Standardized draft-class input used to identify homegrown draft investment and rookie-control timing.
- **Release classification:** PUBLIC SOURCE

| Field | Meaning |
|---|---|
| `draft_year` | NFL draft year. |
| `draft_team` | Drafting team. |
| `round` | Draft round. |
| `overall_pick` | Overall draft selection number. |
| `player_name` | Source player name. |
| `position` | Defensive-front position, primarily ED or DI. |

<details>
<summary>Full column inventory</summary>

```text
draft_year, draft_team, round, overall_pick, player_name, position, college, gsis_id, pfr_player_id
draft_club
```

</details>

## Spotrac cap-hit source (not committed)

- **Repository path:** `data/restricted/spotrac_player_cap_hits_2022_2025.csv`
- **Grain:** player-team-season cap record
- **Period:** 2022–2025
- **Shape:** 6,761 rows × 7 columns
- **Role:** Local source input used to reconstruct defensive-front cap commitment. The public repository should omit this file unless redistribution permission is confirmed.
- **Release classification:** RESTRICTED pending rights review

| Field | Meaning |
|---|---|
| `player_name` | Source player name. |
| `cap_hit` | Player-season cap hit in dollars. |
| `position` | Defensive-front position, primarily ED or DI. |
| `season` | NFL season. |
| `team` | Team abbreviation. |
| `cap_hit_m` | Player-season cap hit in millions of dollars. |
| `name_clean` | Normalized source name for matching. |

<details>
<summary>Full column inventory</summary>

```text
player_name, cap_hit, position, season, team, cap_hit_m, name_clean
```

</details>

## Important interpretation notes

- `resource_quality_alignment` in the canonical allocation panel is the **resource-weighted prior quality level**. In the final manuscript M4 specification, the alignment regressor is constructed as the difference between resource-weighted prior quality and the equal-weight prior-room-quality measure, then scaled in 10-point units.
- The final V9 conditional-resource script reconstructs `prior_room_quality_pct` from current resource-bearing players in the player resource file and uses season fixed effects with team-clustered standard errors.
- FTN team pressure and PFF player pressure are different measurement systems and should not be numerically reconciled one-for-one.
- Archetype variables are descriptive summaries of continuous room-quality dimensions, not causal treatments or estimated latent classes.
