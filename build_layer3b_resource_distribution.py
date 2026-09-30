#!/usr/bin/env python3
"""
Build Layer 3B: pass-rush resource distribution and allocation efficiency.

Purpose
-------
Layer 3A established that total cap-and-draft commitment carries directional
signal but does not explain most pressure or pass-defense variation. Layer 3B
asks where those resources are placed inside the room.

This build separates:
1. Total resource commitment
2. Resource concentration
3. Resource-quality alignment
4. Prior support quality
5. Continuity
6. Current-season outcomes

Primary analytical sample
-------------------------
- Team-seasons from 2023-2025
- At least 80% matched cap coverage by pass-rush opportunity
- Previous-season player creation used as the prior-quality input
- Players without a prior are assigned a neutral prior percentile of 0.50 and
  separately tracked as unproven resource share

Resource-unit construction
--------------------------
Player cap units:
    player cap % / league-season mean observed player cap %

Player draft units:
    annualized active OTC draft value /
    league-season mean annualized active OTC draft value

Player resource units:
    0.50 * cap units + 0.50 * draft units

Within-room resource share:
    player resource units / team-season room resource units

The resource-unit scale is deliberately positive and additive. It is used only
for within-room distribution. The existing season-standardized Layer 3 Resource
Investment Index remains the measure of total room commitment.

Outputs
-------
- Layer_3B_Player_Resource_Allocation.csv
- Layer_3B_Team_Allocation_Master.csv
- Layer_3B_Allocation_Shape_Summary.csv
- Layer_3B_Allocation_Strategy_Summary.csv
- Layer_3B_Allocation_Models.csv
- Layer_3B_Within_Team_Change_Models.csv
- Layer_3B_Matched_Pairs.csv
- Layer_3B_Matched_Comparison_Summary.csv
- Layer_3B_Sensitivity.csv
- Layer_3B_Findings.json
- Layer_3B_Methodology.md
- Four PNG graphics
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import matplotlib.pyplot as plt
import numpy as np
import statsmodels.api as sm
from scipy.stats import rankdata, spearmanr


PRIMARY_CAP_COVERAGE = 0.80
SECONDARY_CAP_COVERAGE = (0.85, 0.90)
MATCH_CALIPER = 0.35
BOOTSTRAP_ITERATIONS = 5000
RANDOM_SEED = 20260722

DETAIL_SHAPE_ORDER = [
    "Single-Player Bet",
    "Two-Player Core",
    "Three-Player Core",
    "Distributed Investment",
]

PRIMARY_SHAPE_ORDER = [
    "Single-Player Bet",
    "Multi-Player Core",
    "Distributed Investment",
]

STRATEGY_ORDER = [
    "Single-Player Bet",
    "Two-Player Core",
    "Three-Player Core",
    "Distributed Investment",
    "Misaligned Investment",
    "Low-Cost Developmental",
]

OUTCOMES = [
    "pressure_z",
    "four_man_pressure_z",
    "pass_defense_composite",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Folder containing the Layer 3A player and team masters.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=(
            "Output folder. Defaults to "
            "data-dir/outputs/layer_3b_resource_distribution."
        ),
    )
    return parser.parse_args()


def resolve_input(data_dir: Path, candidates: list[str]) -> Path:
    for candidate in candidates:
        path = data_dir / candidate
        if path.exists():
            return path

    raise FileNotFoundError(
        "Could not locate any required input candidate:\n"
        + "\n".join(str(data_dir / candidate) for candidate in candidates)
    )


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[str] | None = None,
) -> None:
    if columns is None:
        columns = list(rows[0].keys()) if rows else []

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore",
        )
        writer.writeheader()

        for row in rows:
            cleaned = {
                column: serialize_value(row.get(column))
                for column in columns
            }
            writer.writerow(cleaned)


def serialize_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (np.floating, float)):
        if not math.isfinite(float(value)):
            return ""
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if math.isfinite(number):
            return number
    except (TypeError, ValueError):
        pass
    return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def to_bool(value: Any) -> bool:
    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "y",
    }


def safe_divide(
    numerator: float,
    denominator: float,
    default: float = 0.0,
) -> float:
    if denominator == 0 or not math.isfinite(denominator):
        return default
    return numerator / denominator


def weighted_average(
    values: Iterable[float],
    weights: Iterable[float],
    default: float = 0.0,
) -> float:
    values_array = np.asarray(list(values), dtype=float)
    weights_array = np.asarray(list(weights), dtype=float)
    valid = (
        np.isfinite(values_array)
        & np.isfinite(weights_array)
        & (weights_array >= 0)
    )

    if not valid.any():
        return default

    values_array = values_array[valid]
    weights_array = weights_array[valid]
    total_weight = weights_array.sum()

    if total_weight <= 0:
        return float(np.mean(values_array)) if len(values_array) else default

    return float(np.average(values_array, weights=weights_array))


def percentile_map(
    rows: list[dict[str, Any]],
    value_column: str,
    group_column: str = "season",
) -> dict[tuple[Any, Any], float]:
    groups: dict[Any, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        groups[row[group_column]].append(row)

    output: dict[tuple[Any, Any], float] = {}

    for group_value, group_rows in groups.items():
        values = np.asarray(
            [to_float(row[value_column], np.nan) for row in group_rows],
            dtype=float,
        )

        valid = np.isfinite(values)
        percentiles = np.full(len(group_rows), np.nan, dtype=float)

        if valid.any():
            percentiles[valid] = (
                rankdata(values[valid], method="average")
                / valid.sum()
            )

        for row, percentile in zip(group_rows, percentiles):
            output[(group_value, row["_row_key"])] = float(percentile)

    return output


def season_mean(
    rows: list[dict[str, Any]],
    season: int,
    column: str,
) -> float:
    values = [
        to_float(row.get(column), 0.0)
        for row in rows
        if row["season"] == season
    ]
    return float(np.mean(values)) if values else 0.0


def aggregate_previous_player_seasons(
    player_rows: list[dict[str, Any]],
) -> dict[tuple[str, int], dict[str, float]]:
    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)

    for row in player_rows:
        grouped[(row["player_id"], row["season"])].append(row)

    output: dict[tuple[str, int], dict[str, float]] = {}

    for key, group in grouped.items():
        weights = [
            to_float(row.get("pass_rush_opp"), 0.0)
            for row in group
        ]

        output[key] = {
            "prior_quality_z": weighted_average(
                [to_float(row.get("quality_z"), 0.0) for row in group],
                weights,
                0.0,
            ),
            "prior_quality_pct": weighted_average(
                [to_float(row.get("quality_pct"), 0.5) for row in group],
                weights,
                0.5,
            ),
            "prior_creation_score": weighted_average(
                [to_float(row.get("creation_score"), 0.5) for row in group],
                weights,
                0.5,
            ),
            "prior_pressure_rate": weighted_average(
                [to_float(row.get("pressure_rate"), 0.0) for row in group],
                weights,
                0.0,
            ),
            "prior_pass_rush_opp": float(sum(weights)),
        }

    return output


def prepare_player_rows(
    raw_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    numeric_columns = [
        "segment_share",
        "rush_snaps",
        "pass_rush_opp",
        "pressures",
        "wins",
        "pressure_rate",
        "win_rate",
        "quality_z",
        "quality_pct",
        "volume_pct",
        "star_index",
        "creation_z",
        "creation_pct",
        "creation_score",
        "player_cap_pct",
        "cap_hit",
        "cap_hit_m",
        "draft_otc_annual_strict",
    ]

    for index, source in enumerate(raw_rows):
        row: dict[str, Any] = dict(source)
        row["_row_key"] = index
        row["season"] = to_int(source.get("season"))
        row["player_id"] = str(source.get("player_id", "")).strip()
        row["team"] = str(source.get("team", "")).strip()
        row["player"] = str(source.get("player", "")).strip()
        row["position"] = str(source.get("position", "")).strip()
        row["cap_matched"] = to_bool(source.get("cap_matched"))

        for column in numeric_columns:
            row[column] = to_float(source.get(column), 0.0)

        rows.append(row)

    return rows


def attach_priors_and_resource_units(
    player_rows: list[dict[str, Any]],
) -> None:
    prior_lookup = aggregate_previous_player_seasons(player_rows)
    seasons = sorted({row["season"] for row in player_rows})

    for season in seasons:
        cap_mean = season_mean(
            player_rows,
            season,
            "player_cap_pct",
        )
        draft_mean = season_mean(
            player_rows,
            season,
            "draft_otc_annual_strict",
        )

        for row in player_rows:
            if row["season"] != season:
                continue

            row["player_cap_units"] = safe_divide(
                row["player_cap_pct"],
                cap_mean,
                0.0,
            )
            row["player_draft_units"] = safe_divide(
                row["draft_otc_annual_strict"],
                draft_mean,
                0.0,
            )
            row["player_resource_units"] = (
                0.50 * row["player_cap_units"]
                + 0.50 * row["player_draft_units"]
            )

            prior = prior_lookup.get(
                (row["player_id"], season - 1)
            )

            if prior is None:
                row["prior_available"] = 0
                row["prior_quality_z"] = 0.0
                row["prior_quality_pct"] = 0.50
                row["prior_creation_score"] = 0.50
                row["prior_pressure_rate"] = 0.0
                row["prior_pass_rush_opp"] = 0.0
            else:
                row["prior_available"] = 1
                row.update(prior)


def prepare_team_rows(
    raw_rows: list[dict[str, str]],
) -> dict[tuple[int, str], dict[str, Any]]:
    output: dict[tuple[int, str], dict[str, Any]] = {}

    numeric_columns = [
        "resource_index",
        "resource_percentile",
        "cap_rush_coverage",
        "cap_pressure_coverage",
        "pressure_z",
        "four_man_pressure_z",
        "pass_defense_composite",
        "room_pass_rush_opp",
        "room_pressures",
        "pressure_rate",
        "four_man_pressure_pct",
        "support_quality_z",
        "star_index",
        "resource_adjusted_pressure",
        "resource_adjusted_four_man_pressure",
        "resource_adjusted_pass_defense",
    ]

    for source in raw_rows:
        row: dict[str, Any] = dict(source)
        row["season"] = to_int(source.get("season"))
        row["team"] = str(source.get("team", "")).strip()
        row["cap_high_coverage"] = to_bool(
            source.get("cap_high_coverage")
        )

        for column in numeric_columns:
            row[column] = to_float(source.get(column), np.nan)

        output[(row["season"], row["team"])] = row

    return output


def players_needed_for_share(
    shares: list[float],
    threshold: float,
) -> int:
    cumulative = 0.0

    for index, share in enumerate(shares, start=1):
        cumulative += share
        if cumulative >= threshold:
            return index

    return len(shares)


def concentration_hhi(shares: list[float]) -> float:
    return float(sum(share * share for share in shares))


def team_prior_continuity(
    season: int,
    team: str,
    current_player_ids: set[str],
    player_rows: list[dict[str, Any]],
) -> float:
    previous_rows = [
        row
        for row in player_rows
        if row["season"] == season - 1 and row["team"] == team
    ]

    previous_total = sum(
        to_float(row.get("pass_rush_opp"), 0.0)
        for row in previous_rows
    )

    returning_total = sum(
        to_float(row.get("pass_rush_opp"), 0.0)
        for row in previous_rows
        if row["player_id"] in current_player_ids
    )

    return safe_divide(returning_total, previous_total, 0.0)


def add_team_allocation_metrics(
    player_rows: list[dict[str, Any]],
    team_lookup: dict[tuple[int, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], list[dict[str, Any]]] = defaultdict(list)

    for row in player_rows:
        grouped[(row["season"], row["team"])].append(row)

    team_rows: list[dict[str, Any]] = []

    for (season, team), group in sorted(grouped.items()):
        team_base = team_lookup.get((season, team))

        if team_base is None:
            continue

        total_resource_units = sum(
            row["player_resource_units"] for row in group
        )
        total_cap_units = sum(
            row["player_cap_units"] for row in group
        )
        total_draft_units = sum(
            row["player_draft_units"] for row in group
        )

        for row in group:
            row["room_resource_share"] = safe_divide(
                row["player_resource_units"],
                total_resource_units,
                0.0,
            )
            row["room_cap_resource_share"] = safe_divide(
                row["player_cap_units"],
                total_cap_units,
                0.0,
            )
            row["room_draft_resource_share"] = safe_divide(
                row["player_draft_units"],
                total_draft_units,
                0.0,
            )

        ranked = sorted(
            group,
            key=lambda row: (
                row["player_resource_units"],
                row["pass_rush_opp"],
            ),
            reverse=True,
        )

        cap_ranked = sorted(
            group,
            key=lambda row: row["player_cap_units"],
            reverse=True,
        )

        draft_ranked = sorted(
            group,
            key=lambda row: row["player_draft_units"],
            reverse=True,
        )

        for rank, row in enumerate(ranked, start=1):
            row["room_resource_rank"] = rank

        resource_shares = [
            row["room_resource_share"] for row in ranked
        ]
        cap_shares = [
            row["room_cap_resource_share"] for row in cap_ranked
        ]
        draft_shares = [
            row["room_draft_resource_share"] for row in draft_ranked
        ]

        top1_share = sum(resource_shares[:1])
        top2_share = sum(resource_shares[:2])
        top3_share = sum(resource_shares[:3])
        player_2_3_share = sum(resource_shares[1:3])
        depth_share = max(0.0, 1.0 - top3_share)

        prior_ranked = sorted(
            group,
            key=lambda row: (
                row["prior_quality_z"],
                row["prior_pass_rush_opp"],
            ),
            reverse=True,
        )

        prior_best_quality_z = (
            prior_ranked[0]["prior_quality_z"]
            if prior_ranked
            else 0.0
        )

        prior_second_quality_z = (
            prior_ranked[1]["prior_quality_z"]
            if len(prior_ranked) >= 2
            else 0.0
        )

        prior_third_quality_z = (
            prior_ranked[2]["prior_quality_z"]
            if len(prior_ranked) >= 3
            else 0.0
        )

        prior_support_quality_z = float(
            np.mean(
                [
                    prior_second_quality_z,
                    prior_third_quality_z,
                ]
            )
        )

        resource_quality_alignment = sum(
            row["room_resource_share"]
            * row["prior_quality_pct"]
            for row in group
        )

        resource_share_prior_high_end = sum(
            row["room_resource_share"]
            for row in group
            if row["prior_quality_pct"] >= 0.75
        )

        resource_share_prior_primary = sum(
            row["room_resource_share"]
            for row in group
            if row["prior_quality_pct"] >= 0.90
        )

        resource_share_prior_depth = sum(
            row["room_resource_share"]
            for row in group
            if row["prior_quality_pct"] < 0.50
        )

        unproven_resource_share = sum(
            row["room_resource_share"]
            for row in group
            if not row["prior_available"]
        )

        resource_values = [
            row["player_resource_units"] for row in group
        ]
        prior_values = [
            row["prior_quality_pct"] for row in group
        ]

        if (
            len(group) >= 3
            and len(set(resource_values)) > 1
            and len(set(prior_values)) > 1
        ):
            rank_alignment = float(
                spearmanr(resource_values, prior_values).statistic
            )
        else:
            rank_alignment = np.nan

        ranked_second_third = ranked[1:3]
        second_third_weight = sum(
            row["room_resource_share"]
            for row in ranked_second_third
        )

        top1_resource_prior_quality_pct = (
            ranked[0]["prior_quality_pct"]
            if ranked
            else 0.50
        )

        core_2_3_prior_quality_pct = weighted_average(
            [
                row["prior_quality_pct"]
                for row in ranked_second_third
            ],
            [
                row["room_resource_share"]
                for row in ranked_second_third
            ],
            0.50,
        )

        current_player_ids = {
            row["player_id"] for row in group
        }

        returning_rush_share = team_prior_continuity(
            season=season,
            team=team,
            current_player_ids=current_player_ids,
            player_rows=player_rows,
        )

        resource_hhi = concentration_hhi(resource_shares)
        cap_hhi = concentration_hhi(cap_shares)
        draft_hhi = concentration_hhi(draft_shares)

        row: dict[str, Any] = {
            "season": season,
            "team": team,
            "archetype": team_base.get("archetype", ""),
            "cap_high_coverage": int(
                team_base["cap_high_coverage"]
            ),
            "cap_rush_coverage": team_base["cap_rush_coverage"],
            "resource_index": team_base["resource_index"],
            "resource_percentile": team_base["resource_percentile"],
            "pressure_z": team_base["pressure_z"],
            "four_man_pressure_z": team_base[
                "four_man_pressure_z"
            ],
            "pass_defense_composite": team_base[
                "pass_defense_composite"
            ],
            "resource_adjusted_pressure": team_base[
                "resource_adjusted_pressure"
            ],
            "resource_adjusted_four_man_pressure": team_base[
                "resource_adjusted_four_man_pressure"
            ],
            "resource_adjusted_pass_defense": team_base[
                "resource_adjusted_pass_defense"
            ],
            "room_player_segments": len(group),
            "total_player_resource_units": total_resource_units,
            "total_player_cap_units": total_cap_units,
            "total_player_draft_units": total_draft_units,
            "top1_resource_share": top1_share,
            "top2_resource_share": top2_share,
            "top3_resource_share": top3_share,
            "player_2_resource_share": (
                resource_shares[1]
                if len(resource_shares) >= 2
                else 0.0
            ),
            "player_3_resource_share": (
                resource_shares[2]
                if len(resource_shares) >= 3
                else 0.0
            ),
            "players_2_3_resource_share": player_2_3_share,
            "third_plus_resource_share": max(
                0.0,
                1.0 - top2_share,
            ),
            "fourth_plus_resource_share": depth_share,
            "resource_hhi": resource_hhi,
            "effective_resource_players": safe_divide(
                1.0,
                resource_hhi,
                np.nan,
            ),
            "players_for_50pct_resources": players_needed_for_share(
                resource_shares,
                0.50,
            ),
            "players_for_70pct_resources": players_needed_for_share(
                resource_shares,
                0.70,
            ),
            "players_for_80pct_resources": players_needed_for_share(
                resource_shares,
                0.80,
            ),
            "top1_cap_share": sum(cap_shares[:1]),
            "top2_cap_share": sum(cap_shares[:2]),
            "top3_cap_share": sum(cap_shares[:3]),
            "cap_resource_hhi": cap_hhi,
            "effective_cap_players": safe_divide(
                1.0,
                cap_hhi,
                np.nan,
            ),
            "top1_draft_share": sum(draft_shares[:1]),
            "top2_draft_share": sum(draft_shares[:2]),
            "top3_draft_share": sum(draft_shares[:3]),
            "draft_resource_hhi": draft_hhi,
            "effective_draft_players": safe_divide(
                1.0,
                draft_hhi,
                np.nan,
            ),
            "top_resource_player": (
                ranked[0]["player"] if ranked else ""
            ),
            "top_resource_player_units": (
                ranked[0]["player_resource_units"]
                if ranked
                else 0.0
            ),
            "second_resource_player": (
                ranked[1]["player"]
                if len(ranked) >= 2
                else ""
            ),
            "third_resource_player": (
                ranked[2]["player"]
                if len(ranked) >= 3
                else ""
            ),
            "prior_best_quality_z": prior_best_quality_z,
            "prior_second_quality_z": prior_second_quality_z,
            "prior_third_quality_z": prior_third_quality_z,
            "prior_support_quality_z": prior_support_quality_z,
            "resource_quality_alignment": (
                resource_quality_alignment
            ),
            "resource_prior_rank_spearman": rank_alignment,
            "resource_share_prior_high_end": (
                resource_share_prior_high_end
            ),
            "resource_share_prior_primary": (
                resource_share_prior_primary
            ),
            "resource_share_prior_depth": (
                resource_share_prior_depth
            ),
            "unproven_resource_share": unproven_resource_share,
            "top1_resource_prior_quality_pct": (
                top1_resource_prior_quality_pct
            ),
            "core_2_3_prior_quality_pct": (
                core_2_3_prior_quality_pct
            ),
            "returning_prior_rush_share": returning_rush_share,
            "prior_model_eligible": int(season >= 2023),
        }

        team_rows.append(row)

    return team_rows


def add_percentiles_and_shapes(
    team_rows: list[dict[str, Any]],
) -> None:
    columns = [
        "top1_resource_share",
        "top2_resource_share",
        "top3_resource_share",
        "resource_quality_alignment",
        "unproven_resource_share",
        "resource_index",
        "prior_support_quality_z",
    ]

    for column in columns:
        mapping = percentile_map(team_rows, column)

        for row in team_rows:
            row[f"{column}_pct"] = mapping[
                (row["season"], row["_row_key"])
            ]

    for row in team_rows:
        top1 = row["top1_resource_share"]
        top2 = row["top2_resource_share"]
        top3 = row["top3_resource_share"]

        if top1 >= 0.40:
            detail_shape = "Single-Player Bet"
        elif top2 >= 0.60:
            detail_shape = "Two-Player Core"
        elif top3 >= 0.70:
            detail_shape = "Three-Player Core"
        else:
            detail_shape = "Distributed Investment"

        if detail_shape in {
            "Two-Player Core",
            "Three-Player Core",
        }:
            primary_shape = "Multi-Player Core"
        else:
            primary_shape = detail_shape

        resource_percentile = row["resource_index_pct"]
        alignment_percentile = row[
            "resource_quality_alignment_pct"
        ]
        unproven_percentile = row[
            "unproven_resource_share_pct"
        ]

        if (
            resource_percentile <= 0.25
            and unproven_percentile >= 0.50
        ):
            strategy = "Low-Cost Developmental"
        elif (
            resource_percentile > 0.25
            and alignment_percentile <= 0.25
        ):
            strategy = "Misaligned Investment"
        else:
            strategy = detail_shape

        row["resource_shape_detail"] = detail_shape
        row["resource_shape_primary"] = primary_shape
        row["allocation_strategy"] = strategy

        if alignment_percentile >= 0.75:
            row["alignment_tier"] = "High Alignment"
        elif alignment_percentile <= 0.25:
            row["alignment_tier"] = "Low Alignment"
        else:
            row["alignment_tier"] = "Neutral Alignment"

        if resource_percentile >= 0.75:
            row["investment_tier"] = "High Investment"
        elif resource_percentile <= 0.25:
            row["investment_tier"] = "Low Investment"
        else:
            row["investment_tier"] = "Average Investment"

        row["top1_resource_share_10"] = (
            row["top1_resource_share"] * 10.0
        )
        row["players_2_3_resource_share_10"] = (
            row["players_2_3_resource_share"] * 10.0
        )
        row["resource_quality_alignment_10"] = (
            row["resource_quality_alignment"] * 10.0
        )
        row["unproven_resource_share_10"] = (
            row["unproven_resource_share"] * 10.0
        )
        row["returning_prior_rush_share_10"] = (
            row["returning_prior_rush_share"] * 10.0
        )
        row["top1_cap_share_10"] = (
            row["top1_cap_share"] * 10.0
        )
        row["top1_draft_share_10"] = (
            row["top1_draft_share"] * 10.0
        )


def attach_row_keys(team_rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(team_rows):
        row["_row_key"] = index


def season_dummies(
    row: dict[str, Any],
    base_season: int,
    seasons: list[int],
) -> list[float]:
    return [
        1.0 if row["season"] == season else 0.0
        for season in seasons
        if season != base_season
    ]


def fit_clustered_model(
    rows: list[dict[str, Any]],
    outcome: str,
    predictors: list[str],
    model_name: str,
    model_group: str,
    minimum_cap_coverage: float = PRIMARY_CAP_COVERAGE,
    excluded_season: int | None = None,
) -> list[dict[str, Any]]:
    eligible = []

    for row in rows:
        if row["season"] < 2023:
            continue
        if row["cap_rush_coverage"] < minimum_cap_coverage:
            continue
        if excluded_season is not None and row["season"] == excluded_season:
            continue

        outcome_value = to_float(row.get(outcome), np.nan)

        if not math.isfinite(outcome_value):
            continue

        predictor_values = [
            to_float(row.get(predictor), np.nan)
            for predictor in predictors
        ]

        if not all(math.isfinite(value) for value in predictor_values):
            continue

        eligible.append(row)

    if len(eligible) <= len(predictors) + 5:
        return []

    seasons = sorted({row["season"] for row in eligible})
    base_season = seasons[0]

    design = []
    outcome_values = []
    team_groups = []

    for row in eligible:
        design_row = [1.0]
        design_row.extend(
            [to_float(row[predictor], 0.0) for predictor in predictors]
        )
        design_row.extend(
            season_dummies(row, base_season, seasons)
        )

        design.append(design_row)
        outcome_values.append(to_float(row[outcome], 0.0))
        team_groups.append(row["team"])

    x = np.asarray(design, dtype=float)
    y = np.asarray(outcome_values, dtype=float)
    groups = np.asarray(team_groups)

    model = sm.OLS(y, x).fit(
        cov_type="cluster",
        cov_kwds={"groups": groups},
    )

    parameter_names = ["Intercept"]
    parameter_names.extend(predictors)
    parameter_names.extend(
        [
            f"season_{season}"
            for season in seasons
            if season != base_season
        ]
    )

    rows_out: list[dict[str, Any]] = []

    for index, parameter in enumerate(parameter_names):
        interval = model.conf_int()[index]

        rows_out.append(
            {
                "model_group": model_group,
                "model_name": model_name,
                "outcome": outcome,
                "minimum_cap_coverage": minimum_cap_coverage,
                "excluded_season": (
                    excluded_season
                    if excluded_season is not None
                    else ""
                ),
                "parameter": parameter,
                "coefficient": float(model.params[index]),
                "cluster_se": float(model.bse[index]),
                "p_value": float(model.pvalues[index]),
                "ci_low": float(interval[0]),
                "ci_high": float(interval[1]),
                "adjusted_r2": float(model.rsquared_adj),
                "n": int(model.nobs),
                "team_clusters": len(set(team_groups)),
            }
        )

    return rows_out


def add_shape_dummies(team_rows: list[dict[str, Any]]) -> None:
    for row in team_rows:
        shape = row["resource_shape_primary"]
        row["shape_single_player"] = int(
            shape == "Single-Player Bet"
        )
        row["shape_multi_player_core"] = int(
            shape == "Multi-Player Core"
        )

        detail = row["resource_shape_detail"]
        row["detail_single_player"] = int(
            detail == "Single-Player Bet"
        )
        row["detail_two_player_core"] = int(
            detail == "Two-Player Core"
        )
        row["detail_three_player_core"] = int(
            detail == "Three-Player Core"
        )

        centered_top1 = (
            row["top1_resource_share"]
            - 0.30
        )
        row["top1_resource_share_centered_10"] = (
            centered_top1 * 10.0
        )
        row["top1_resource_share_centered_10_sq"] = (
            row["top1_resource_share_centered_10"] ** 2
        )


def build_primary_models(
    team_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    all_rows: list[dict[str, Any]] = []

    specifications = [
        (
            "Distribution with prior quality controls",
            [
                "resource_index",
                "top1_resource_share_10",
                "players_2_3_resource_share_10",
                "prior_best_quality_z",
                "prior_support_quality_z",
                "returning_prior_rush_share_10",
            ],
        ),
        (
            "Alignment and unproven resource model",
            [
                "resource_index",
                "top1_resource_share_10",
                "players_2_3_resource_share_10",
                "resource_quality_alignment_10",
                "unproven_resource_share_10",
                "returning_prior_rush_share_10",
            ],
        ),
        (
            "Nonlinear one-player concentration",
            [
                "resource_index",
                "top1_resource_share_centered_10",
                "top1_resource_share_centered_10_sq",
                "prior_best_quality_z",
                "prior_support_quality_z",
                "returning_prior_rush_share_10",
            ],
        ),
        (
            "Primary allocation shape model",
            [
                "resource_index",
                "shape_single_player",
                "shape_multi_player_core",
                "resource_quality_alignment_10",
                "prior_support_quality_z",
                "returning_prior_rush_share_10",
            ],
        ),
        (
            "Cap and draft top-player concentration",
            [
                "resource_index",
                "top1_cap_share_10",
                "top1_draft_share_10",
                "resource_quality_alignment_10",
                "prior_support_quality_z",
                "returning_prior_rush_share_10",
            ],
        ),
    ]

    for outcome in OUTCOMES:
        for model_name, predictors in specifications:
            all_rows.extend(
                fit_clustered_model(
                    rows=team_rows,
                    outcome=outcome,
                    predictors=predictors,
                    model_name=model_name,
                    model_group="primary",
                )
            )

    return all_rows


def build_consecutive_differences(
    team_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lookup = {
        (row["season"], row["team"]): row
        for row in team_rows
    }

    output: list[dict[str, Any]] = []

    difference_columns = [
        "resource_index",
        "top1_resource_share_10",
        "players_2_3_resource_share_10",
        "resource_quality_alignment_10",
        "unproven_resource_share_10",
        "pressure_z",
        "four_man_pressure_z",
        "pass_defense_composite",
    ]

    for row in team_rows:
        previous = lookup.get((row["season"] - 1, row["team"]))

        if previous is None:
            continue

        if (
            row["cap_rush_coverage"] < PRIMARY_CAP_COVERAGE
            or previous["cap_rush_coverage"] < PRIMARY_CAP_COVERAGE
        ):
            continue

        transition: dict[str, Any] = {
            "season": row["season"],
            "team": row["team"],
            "transition": (
                f"{row['season'] - 1}-{row['season']}"
            ),
        }

        for column in difference_columns:
            transition[f"delta_{column}"] = (
                to_float(row[column], 0.0)
                - to_float(previous[column], 0.0)
            )

        output.append(transition)

    return output


def fit_change_model(
    rows: list[dict[str, Any]],
    outcome: str,
    predictors: list[str],
    model_name: str,
) -> list[dict[str, Any]]:
    eligible = []

    for row in rows:
        outcome_value = to_float(row.get(outcome), np.nan)
        predictor_values = [
            to_float(row.get(predictor), np.nan)
            for predictor in predictors
        ]

        if (
            math.isfinite(outcome_value)
            and all(math.isfinite(value) for value in predictor_values)
        ):
            eligible.append(row)

    if len(eligible) <= len(predictors) + 5:
        return []

    transitions = sorted(
        {row["transition"] for row in eligible}
    )
    base_transition = transitions[0]

    design = []
    outcome_values = []
    team_groups = []

    for row in eligible:
        design_row = [1.0]
        design_row.extend(
            [to_float(row[predictor], 0.0) for predictor in predictors]
        )
        design_row.extend(
            [
                1.0 if row["transition"] == transition else 0.0
                for transition in transitions
                if transition != base_transition
            ]
        )
        design.append(design_row)
        outcome_values.append(to_float(row[outcome], 0.0))
        team_groups.append(row["team"])

    model = sm.OLS(
        np.asarray(outcome_values, dtype=float),
        np.asarray(design, dtype=float),
    ).fit(
        cov_type="cluster",
        cov_kwds={"groups": np.asarray(team_groups)},
    )

    parameter_names = ["Intercept"]
    parameter_names.extend(predictors)
    parameter_names.extend(
        [
            f"transition_{transition}"
            for transition in transitions
            if transition != base_transition
        ]
    )

    output: list[dict[str, Any]] = []

    for index, parameter in enumerate(parameter_names):
        interval = model.conf_int()[index]

        output.append(
            {
                "model_group": "within_team_change",
                "model_name": model_name,
                "outcome": outcome,
                "parameter": parameter,
                "coefficient": float(model.params[index]),
                "cluster_se": float(model.bse[index]),
                "p_value": float(model.pvalues[index]),
                "ci_low": float(interval[0]),
                "ci_high": float(interval[1]),
                "adjusted_r2": float(model.rsquared_adj),
                "n": int(model.nobs),
                "team_clusters": len(set(team_groups)),
            }
        )

    return output


def build_change_models(
    difference_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    predictors = [
        "delta_resource_index",
        "delta_top1_resource_share_10",
        "delta_players_2_3_resource_share_10",
        "delta_resource_quality_alignment_10",
        "delta_unproven_resource_share_10",
    ]

    output: list[dict[str, Any]] = []

    for outcome in OUTCOMES:
        output.extend(
            fit_change_model(
                rows=difference_rows,
                outcome=f"delta_{outcome}",
                predictors=predictors,
                model_name=(
                    "Within-team resource-distribution change"
                ),
            )
        )

    return output


def bootstrap_mean_ci(
    values: list[float],
    seed: int,
) -> tuple[float, float, float]:
    clean = np.asarray(
        [value for value in values if math.isfinite(value)],
        dtype=float,
    )

    if len(clean) == 0:
        return np.nan, np.nan, np.nan

    rng = np.random.default_rng(seed)
    means = np.empty(BOOTSTRAP_ITERATIONS, dtype=float)

    for index in range(BOOTSTRAP_ITERATIONS):
        sample = rng.choice(clean, size=len(clean), replace=True)
        means[index] = sample.mean()

    return (
        float(clean.mean()),
        float(np.quantile(means, 0.025)),
        float(np.quantile(means, 0.975)),
    )


def greedy_match(
    team_rows: list[dict[str, Any]],
    group_a: str,
    group_b: str,
    group_column: str,
) -> list[dict[str, Any]]:
    rows_a = [
        row
        for row in team_rows
        if (
            row[group_column] == group_a
            and row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
        )
    ]

    rows_b = [
        row
        for row in team_rows
        if (
            row[group_column] == group_b
            and row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
        )
    ]

    pairs: list[dict[str, Any]] = []

    for season in sorted({row["season"] for row in rows_a}):
        season_a = sorted(
            [row for row in rows_a if row["season"] == season],
            key=lambda row: row["resource_index"],
        )
        available_b = [
            row for row in rows_b if row["season"] == season
        ]

        for row_a in season_a:
            candidates = [
                row_b
                for row_b in available_b
                if abs(
                    row_a["resource_index"]
                    - row_b["resource_index"]
                )
                <= MATCH_CALIPER
            ]

            if not candidates:
                continue

            def distance(row_b: dict[str, Any]) -> float:
                resource_distance = (
                    row_a["resource_index"]
                    - row_b["resource_index"]
                )
                support_distance = (
                    row_a["prior_support_quality_z"]
                    - row_b["prior_support_quality_z"]
                )
                return math.sqrt(
                    resource_distance ** 2
                    + 0.25 * support_distance ** 2
                )

            row_b = min(candidates, key=distance)
            available_b.remove(row_b)

            pair: dict[str, Any] = {
                "comparison": f"{group_a} vs {group_b}",
                "season": season,
                "group_a": group_a,
                "team_a": row_a["team"],
                "group_b": group_b,
                "team_b": row_b["team"],
                "resource_index_a": row_a["resource_index"],
                "resource_index_b": row_b["resource_index"],
                "resource_index_difference": (
                    row_a["resource_index"]
                    - row_b["resource_index"]
                ),
                "prior_support_quality_a": row_a[
                    "prior_support_quality_z"
                ],
                "prior_support_quality_b": row_b[
                    "prior_support_quality_z"
                ],
                "alignment_a": row_a[
                    "resource_quality_alignment"
                ],
                "alignment_b": row_b[
                    "resource_quality_alignment"
                ],
            }

            for outcome in OUTCOMES:
                pair[f"{outcome}_a"] = row_a[outcome]
                pair[f"{outcome}_b"] = row_b[outcome]
                pair[f"{outcome}_difference"] = (
                    row_a[outcome] - row_b[outcome]
                )

            pairs.append(pair)

    return pairs


def build_matched_comparisons(
    team_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comparisons = [
        (
            "Single-Player Bet",
            "Multi-Player Core",
            "resource_shape_primary",
        ),
        (
            "Single-Player Bet",
            "Distributed Investment",
            "resource_shape_primary",
        ),
        (
            "Multi-Player Core",
            "Distributed Investment",
            "resource_shape_primary",
        ),
    ]

    pairs: list[dict[str, Any]] = []

    for group_a, group_b, group_column in comparisons:
        pairs.extend(
            greedy_match(
                team_rows=team_rows,
                group_a=group_a,
                group_b=group_b,
                group_column=group_column,
            )
        )

    summary: list[dict[str, Any]] = []

    for comparison in sorted(
        {pair["comparison"] for pair in pairs}
    ):
        comparison_pairs = [
            pair
            for pair in pairs
            if pair["comparison"] == comparison
        ]

        for outcome_index, outcome in enumerate(OUTCOMES, start=1):
            values = [
                pair[f"{outcome}_difference"]
                for pair in comparison_pairs
            ]

            mean_difference, ci_low, ci_high = bootstrap_mean_ci(
                values,
                RANDOM_SEED + outcome_index,
            )

            summary.append(
                {
                    "comparison": comparison,
                    "outcome": outcome,
                    "matched_pairs": len(comparison_pairs),
                    "mean_a_minus_b": mean_difference,
                    "ci_low": ci_low,
                    "ci_high": ci_high,
                    "ci_excludes_zero": int(
                        math.isfinite(ci_low)
                        and math.isfinite(ci_high)
                        and (ci_low > 0 or ci_high < 0)
                    ),
                    "median_resource_index_difference": float(
                        np.median(
                            [
                                pair[
                                    "resource_index_difference"
                                ]
                                for pair in comparison_pairs
                            ]
                        )
                    )
                    if comparison_pairs
                    else np.nan,
                }
            )

    return pairs, summary


def build_group_summary(
    team_rows: list[dict[str, Any]],
    group_column: str,
    order: list[str],
) -> list[dict[str, Any]]:
    summary: list[dict[str, Any]] = []

    metric_columns = [
        "resource_index",
        "top1_resource_share",
        "top2_resource_share",
        "top3_resource_share",
        "effective_resource_players",
        "resource_quality_alignment",
        "prior_best_quality_z",
        "prior_support_quality_z",
        "returning_prior_rush_share",
        "pressure_z",
        "four_man_pressure_z",
        "pass_defense_composite",
        "resource_adjusted_pressure",
    ]

    for group_value in order:
        group = [
            row
            for row in team_rows
            if row.get(group_column) == group_value
        ]

        high_coverage = [
            row
            for row in group
            if row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
        ]

        row: dict[str, Any] = {
            group_column: group_value,
            "team_seasons": len(group),
            "high_coverage_team_seasons": len(high_coverage),
        }

        for metric in metric_columns:
            values = [
                to_float(source.get(metric), np.nan)
                for source in group
            ]
            clean = [
                value
                for value in values
                if math.isfinite(value)
            ]
            row[f"median_{metric}"] = (
                float(np.median(clean)) if clean else np.nan
            )

        summary.append(row)

    return summary


def build_sensitivity(
    team_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []

    for minimum_coverage in (
        PRIMARY_CAP_COVERAGE,
        *SECONDARY_CAP_COVERAGE,
    ):
        for outcome in OUTCOMES:
            rows = fit_clustered_model(
                rows=team_rows,
                outcome=outcome,
                predictors=[
                    "resource_index",
                    "top1_resource_share_10",
                    "players_2_3_resource_share_10",
                    "resource_quality_alignment_10",
                    "prior_support_quality_z",
                    "returning_prior_rush_share_10",
                ],
                model_name="Coverage-threshold sensitivity",
                model_group="sensitivity",
                minimum_cap_coverage=minimum_coverage,
            )

            for row in rows:
                if row["parameter"] in {
                    "top1_resource_share_10",
                    "players_2_3_resource_share_10",
                    "resource_quality_alignment_10",
                    "prior_support_quality_z",
                }:
                    output.append(row)

    for excluded_season in (2023, 2024, 2025):
        for outcome in OUTCOMES:
            rows = fit_clustered_model(
                rows=team_rows,
                outcome=outcome,
                predictors=[
                    "resource_index",
                    "top1_resource_share_10",
                    "players_2_3_resource_share_10",
                    "resource_quality_alignment_10",
                    "prior_support_quality_z",
                    "returning_prior_rush_share_10",
                ],
                model_name="Leave-one-season-out sensitivity",
                model_group="sensitivity",
                minimum_cap_coverage=PRIMARY_CAP_COVERAGE,
                excluded_season=excluded_season,
            )

            for row in rows:
                if row["parameter"] in {
                    "top1_resource_share_10",
                    "players_2_3_resource_share_10",
                    "resource_quality_alignment_10",
                    "prior_support_quality_z",
                }:
                    output.append(row)

    return output


def coefficient_lookup(
    model_rows: list[dict[str, Any]],
    model_name: str,
    outcome: str,
    parameter: str,
) -> dict[str, Any]:
    for row in model_rows:
        if (
            row["model_name"] == model_name
            and row["outcome"] == outcome
            and row["parameter"] == parameter
        ):
            return row

    return {}


def make_same_resources_chart(
    team_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    plot_rows = [
        row
        for row in team_rows
        if row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
    ]

    figure, axis = plt.subplots(figsize=(12, 8))

    for shape in PRIMARY_SHAPE_ORDER:
        group = [
            row
            for row in plot_rows
            if row["resource_shape_primary"] == shape
        ]

        x = [row["top1_resource_share"] for row in group]
        y = [
            row["resource_adjusted_pressure"]
            for row in group
        ]
        sizes = [
            45.0
            + 22.0
            * max(0.0, row["resource_index"] + 2.0)
            for row in group
        ]

        axis.scatter(
            x,
            y,
            s=sizes,
            alpha=0.65,
            label=shape,
        )

    axis.axhline(0, linewidth=1)
    axis.set_title("Same Resources, Different Pass-Rush Builds")
    axis.set_xlabel("Top player share of room resources")
    axis.set_ylabel("Pressure above/below resource expectation")
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_alignment_chart(
    team_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    plot_rows = [
        row
        for row in team_rows
        if (
            row["season"] >= 2023
            and row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
        )
    ]

    figure, axis = plt.subplots(figsize=(12, 8))

    for shape in PRIMARY_SHAPE_ORDER:
        group = [
            row
            for row in plot_rows
            if row["resource_shape_primary"] == shape
        ]

        axis.scatter(
            [
                row["resource_quality_alignment"]
                for row in group
            ],
            [row["pressure_z"] for row in group],
            alpha=0.65,
            label=shape,
        )

    x = np.asarray(
        [
            row["resource_quality_alignment"]
            for row in plot_rows
        ],
        dtype=float,
    )
    y = np.asarray(
        [row["pressure_z"] for row in plot_rows],
        dtype=float,
    )

    if len(x) >= 2:
        fit = np.polyfit(x, y, deg=1)
        grid = np.linspace(x.min(), x.max(), 100)
        axis.plot(grid, fit[0] * grid + fit[1], linewidth=1)

    axis.axhline(0, linewidth=1)
    axis.set_title(
        "Resource-Quality Alignment and Pressure Creation"
    )
    axis.set_xlabel(
        "Resource-weighted prior creation percentile"
    )
    axis.set_ylabel("Current-season pressure z-score")
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_support_chart(
    team_rows: list[dict[str, Any]],
    output_path: Path,
) -> None:
    plot_rows = [
        row
        for row in team_rows
        if (
            row["season"] >= 2023
            and row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
        )
    ]

    figure, axis = plt.subplots(figsize=(12, 8))

    axis.scatter(
        [
            row["prior_support_quality_z"]
            for row in plot_rows
        ],
        [row["pressure_z"] for row in plot_rows],
        alpha=0.65,
    )

    x = np.asarray(
        [
            row["prior_support_quality_z"]
            for row in plot_rows
        ],
        dtype=float,
    )
    y = np.asarray(
        [row["pressure_z"] for row in plot_rows],
        dtype=float,
    )

    if len(x) >= 2:
        fit = np.polyfit(x, y, deg=1)
        grid = np.linspace(x.min(), x.max(), 100)
        axis.plot(grid, fit[0] * grid + fit[1], linewidth=1)

    axis.axhline(0, linewidth=1)
    axis.axvline(0, linewidth=1)
    axis.set_title(
        "Prior Support Quality and Current Pressure Creation"
    )
    axis.set_xlabel(
        "Prior quality of the room's second and third creators"
    )
    axis.set_ylabel("Current-season pressure z-score")

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_shape_outcomes_chart(
    shape_summary: list[dict[str, Any]],
    output_path: Path,
) -> None:
    lookup = {
        row["resource_shape_primary"]: row
        for row in shape_summary
    }

    labels = [
        shape
        for shape in PRIMARY_SHAPE_ORDER
        if shape in lookup
    ]
    values = [
        lookup[shape]["median_pressure_z"]
        for shape in labels
    ]

    figure, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar(labels, values)

    axis.axhline(0, linewidth=1)
    axis.set_title(
        "Current Pressure Creation by Resource Distribution"
    )
    axis.set_ylabel("Median pressure z-score")
    axis.tick_params(axis="x", rotation=12)

    for bar, value in zip(bars, values):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + (0.03 if value >= 0 else -0.03),
            f"{value:+.2f}",
            ha="center",
            va="bottom" if value >= 0 else "top",
        )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def build_findings(
    player_rows: list[dict[str, Any]],
    team_rows: list[dict[str, Any]],
    primary_models: list[dict[str, Any]],
    change_models: list[dict[str, Any]],
    shape_summary: list[dict[str, Any]],
    matched_summary: list[dict[str, Any]],
    sensitivity: list[dict[str, Any]],
    source_paths: dict[str, str],
) -> dict[str, Any]:
    distribution_pressure = {
        parameter: coefficient_lookup(
            primary_models,
            "Distribution with prior quality controls",
            "pressure_z",
            parameter,
        )
        for parameter in [
            "resource_index",
            "top1_resource_share_10",
            "players_2_3_resource_share_10",
            "prior_best_quality_z",
            "prior_support_quality_z",
            "returning_prior_rush_share_10",
        ]
    }

    alignment_pressure = {
        parameter: coefficient_lookup(
            primary_models,
            "Alignment and unproven resource model",
            "pressure_z",
            parameter,
        )
        for parameter in [
            "resource_quality_alignment_10",
            "unproven_resource_share_10",
            "top1_resource_share_10",
            "players_2_3_resource_share_10",
        ]
    }

    alignment_four_man = coefficient_lookup(
        primary_models,
        "Alignment and unproven resource model",
        "four_man_pressure_z",
        "resource_quality_alignment_10",
    )

    nonlinear = coefficient_lookup(
        primary_models,
        "Nonlinear one-player concentration",
        "pressure_z",
        "top1_resource_share_centered_10_sq",
    )

    high_coverage_rows = [
        row
        for row in team_rows
        if row["cap_rush_coverage"] >= PRIMARY_CAP_COVERAGE
    ]

    return {
        "status": "Layer 3B resource distribution build complete",
        "source_paths": source_paths,
        "sample": {
            "player_segments": len(player_rows),
            "team_seasons": len(team_rows),
            "prior_model_team_seasons": len(
                [
                    row
                    for row in high_coverage_rows
                    if row["season"] >= 2023
                ]
            ),
            "high_coverage_team_seasons": len(
                high_coverage_rows
            ),
            "median_cap_rush_coverage": float(
                np.median(
                    [
                        row["cap_rush_coverage"]
                        for row in team_rows
                    ]
                )
            ),
        },
        "v1_methodology": {
            "player_resource_units": (
                "Equal-weight positive cap units and active homegrown "
                "draft units, each normalized to the league-season "
                "mean player value."
            ),
            "total_resource_commitment": (
                "Existing Layer 3 Resource Investment Index."
            ),
            "prior_quality": (
                "Previous-season creation quality; neutral 0.50 "
                "percentile for players without a prior."
            ),
            "primary_models": (
                "2023-2025 team-seasons with at least 80% cap "
                "coverage; team-clustered standard errors."
            ),
            "shape_rule": {
                "single_player": "Top player receives at least 40% of room resources.",
                "two_player": (
                    "Top player below 40% and top two receive at "
                    "least 60%."
                ),
                "three_player": (
                    "Top player below 40%, top two below 60%, and "
                    "top three receive at least 70%."
                ),
                "distributed": "All remaining rooms.",
            },
        },
        "headline_models": {
            "pressure_distribution_model": distribution_pressure,
            "pressure_alignment_model": alignment_pressure,
            "four_man_alignment": alignment_four_man,
            "nonlinear_top1_concentration": nonlinear,
        },
        "shape_summary": shape_summary,
        "matched_comparisons": matched_summary,
        "within_team_change_models": change_models,
        "sensitivity": sensitivity,
        "limitations": [
            (
                "Player-level resource shares use observed matched cap "
                "charges. Primary models restrict the sample but cannot "
                "fully eliminate unmatched-cap distortion."
            ),
            (
                "Current-season roster membership is observed after the "
                "fact; the quality variables are temporally lagged, but "
                "this is not a true preseason roster snapshot."
            ),
            (
                "Rookies and other players without a prior are assigned "
                "a neutral quality percentile and separately tracked as "
                "unproven resource share."
            ),
            (
                "Allocation shapes are descriptive threshold groups. "
                "Continuous concentration and alignment models carry "
                "more inferential weight."
            ),
            (
                "Results are associative and do not establish a causal "
                "optimal roster-construction strategy."
            ),
        ],
    }


def build_methodology_markdown(
    findings: dict[str, Any],
) -> str:
    sample = findings["sample"]

    return f"""# Layer 3B: Resource Distribution and Allocation Efficiency

## Objective

Layer 3A measured how much cap and active draft capital each pass-rush room
consumed. Layer 3B measures where those resources are placed and whether
concentration, prior player quality, support quality, alignment, and continuity
help explain current pressure creation and pass-defense outcomes.

## Positive player resource units

Within each season:

- Cap units equal player cap percentage divided by the league-season mean
  observed player cap percentage.
- Draft units equal annualized active OTC draft value divided by the
  league-season mean active draft value.
- Player resource units are an equal-weight average of cap and draft units.
- Within-room resource share is the player's units divided by the room total.

This positive scale is used only for resource distribution. The existing
Layer 3 Resource Investment Index remains the total-commitment measure.

## Resource distribution metrics

The team master reports:

- top-one, top-two, and top-three resource shares;
- the combined share placed in players two and three;
- cap-only and draft-only concentration;
- HHI and effective resource-player counts;
- players required to reach 50%, 70%, and 80% of room resources;
- resource-quality alignment;
- resource shares assigned to prior high-end, primary, depth, and unproven
  players;
- prior best-player and support quality;
- returning prior rush share.

## Resource shapes

- **Single-Player Bet:** top player receives at least 40% of room resources.
- **Two-Player Core:** top player is below 40%, but the top two reach 60%.
- **Three-Player Core:** top player is below 40%, the top two are below 60%,
  and the top three reach 70%.
- **Distributed Investment:** all remaining rooms.

Two- and three-player rooms are also combined into a primary
**Multi-Player Core** category for models and matched comparisons.

## Temporal separation

Player quality inputs come from the previous season. Players without a prior
are assigned a neutral creation percentile of 0.50 and are separately tracked
through unproven resource share.

The primary model sample contains
{sample["prior_model_team_seasons"]} team-seasons from 2023-2025 with at least
{PRIMARY_CAP_COVERAGE:.0%} cap coverage by pass-rush opportunity.

Models use team-clustered standard errors and season fixed effects.

## Interpretation

The continuous models carry more weight than the categorical resource shapes.
A non-significant concentration coefficient does not prove that distribution
never matters. It means that concentration alone does not reliably separate
outcomes after total investment, prior talent, support quality, and continuity
are considered.

Resource-quality alignment asks whether the room's largest commitments are
attached to players who had already demonstrated creation ability. Prior support
quality asks whether the second and third creators entering the season were
credible.

## Limitations

- Player-level cap distribution is based on matched observed charges.
- Current roster membership is observed after the season rather than from a
  preseason transaction snapshot.
- Rookie uncertainty is represented through neutral priors and an unproven
  resource-share control.
- Results are associative and should not be interpreted as causal estimates of
  the optimal defensive-line build.
"""


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)

    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else data_dir
        / "outputs"
        / "layer_3b_resource_distribution"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    player_path = resolve_input(
        data_dir,
        [
            "layer_3_resources/Layer_3_Player_Resource_Bridge.csv",
            "outputs/layer_3_resources/Layer_3_Player_Resource_Bridge.csv",
            "Layer_3_Player_Resource_Bridge.csv",
        ],
    )

    team_path = resolve_input(
        data_dir,
        [
            "layer_3_resources/Layer_3_Team_Resource_Master.csv",
            "outputs/layer_3_resources/Layer_3_Team_Resource_Master.csv",
            "Layer_3_Team_Resource_Master.csv",
        ],
    )

    player_rows = prepare_player_rows(read_csv(player_path))
    team_lookup = prepare_team_rows(read_csv(team_path))

    attach_priors_and_resource_units(player_rows)

    team_rows = add_team_allocation_metrics(
        player_rows=player_rows,
        team_lookup=team_lookup,
    )

    attach_row_keys(team_rows)
    add_percentiles_and_shapes(team_rows)
    add_shape_dummies(team_rows)

    primary_models = build_primary_models(team_rows)

    difference_rows = build_consecutive_differences(team_rows)
    change_models = build_change_models(difference_rows)

    matched_pairs, matched_summary = build_matched_comparisons(
        team_rows
    )

    primary_shape_summary = build_group_summary(
        team_rows=team_rows,
        group_column="resource_shape_primary",
        order=PRIMARY_SHAPE_ORDER,
    )

    detail_shape_summary = build_group_summary(
        team_rows=team_rows,
        group_column="resource_shape_detail",
        order=DETAIL_SHAPE_ORDER,
    )

    strategy_summary = build_group_summary(
        team_rows=team_rows,
        group_column="allocation_strategy",
        order=STRATEGY_ORDER,
    )

    sensitivity = build_sensitivity(team_rows)

    source_paths = {
        "player_resource_bridge": str(player_path),
        "team_resource_master": str(team_path),
    }

    findings = build_findings(
        player_rows=player_rows,
        team_rows=team_rows,
        primary_models=primary_models,
        change_models=change_models,
        shape_summary=primary_shape_summary,
        matched_summary=matched_summary,
        sensitivity=sensitivity,
        source_paths=source_paths,
    )

    methodology = build_methodology_markdown(findings)

    player_columns = [
        "season",
        "team",
        "player",
        "player_id",
        "position",
        "pass_rush_opp",
        "pressures",
        "player_cap_pct",
        "draft_otc_annual_strict",
        "player_cap_units",
        "player_draft_units",
        "player_resource_units",
        "room_resource_share",
        "room_cap_resource_share",
        "room_draft_resource_share",
        "room_resource_rank",
        "prior_available",
        "prior_quality_z",
        "prior_quality_pct",
        "prior_creation_score",
        "prior_pressure_rate",
        "prior_pass_rush_opp",
        "cap_matched",
        "cap_match_status",
        "cap_source_name",
        "draft_match_status",
        "draft_source_name",
    ]

    team_columns = [
        "season",
        "team",
        "archetype",
        "cap_high_coverage",
        "cap_rush_coverage",
        "resource_index",
        "resource_percentile",
        "resource_shape_primary",
        "resource_shape_detail",
        "allocation_strategy",
        "alignment_tier",
        "investment_tier",
        "top_resource_player",
        "second_resource_player",
        "third_resource_player",
        "top1_resource_share",
        "top2_resource_share",
        "top3_resource_share",
        "player_2_resource_share",
        "player_3_resource_share",
        "players_2_3_resource_share",
        "third_plus_resource_share",
        "fourth_plus_resource_share",
        "resource_hhi",
        "effective_resource_players",
        "players_for_50pct_resources",
        "players_for_70pct_resources",
        "players_for_80pct_resources",
        "top1_cap_share",
        "top2_cap_share",
        "top3_cap_share",
        "cap_resource_hhi",
        "effective_cap_players",
        "top1_draft_share",
        "top2_draft_share",
        "top3_draft_share",
        "draft_resource_hhi",
        "effective_draft_players",
        "prior_best_quality_z",
        "prior_second_quality_z",
        "prior_third_quality_z",
        "prior_support_quality_z",
        "resource_quality_alignment",
        "resource_prior_rank_spearman",
        "resource_share_prior_high_end",
        "resource_share_prior_primary",
        "resource_share_prior_depth",
        "unproven_resource_share",
        "top1_resource_prior_quality_pct",
        "core_2_3_prior_quality_pct",
        "returning_prior_rush_share",
        "pressure_z",
        "four_man_pressure_z",
        "pass_defense_composite",
        "resource_adjusted_pressure",
        "resource_adjusted_four_man_pressure",
        "resource_adjusted_pass_defense",
    ]

    outputs = {
        "player_allocation": (
            output_dir
            / "Layer_3B_Player_Resource_Allocation.csv"
        ),
        "team_master": (
            output_dir
            / "Layer_3B_Team_Allocation_Master.csv"
        ),
        "primary_shape_summary": (
            output_dir
            / "Layer_3B_Allocation_Shape_Summary.csv"
        ),
        "detail_shape_summary": (
            output_dir
            / "Layer_3B_Allocation_Shape_Detail.csv"
        ),
        "strategy_summary": (
            output_dir
            / "Layer_3B_Allocation_Strategy_Summary.csv"
        ),
        "models": (
            output_dir / "Layer_3B_Allocation_Models.csv"
        ),
        "change_rows": (
            output_dir
            / "Layer_3B_Within_Team_Changes.csv"
        ),
        "change_models": (
            output_dir
            / "Layer_3B_Within_Team_Change_Models.csv"
        ),
        "matched_pairs": (
            output_dir / "Layer_3B_Matched_Pairs.csv"
        ),
        "matched_summary": (
            output_dir
            / "Layer_3B_Matched_Comparison_Summary.csv"
        ),
        "sensitivity": (
            output_dir / "Layer_3B_Sensitivity.csv"
        ),
        "findings": (
            output_dir / "Layer_3B_Findings.json"
        ),
        "methodology": (
            output_dir / "Layer_3B_Methodology.md"
        ),
        "same_resources_chart": (
            output_dir
            / "Layer_3B_Same_Resources_Different_Builds.png"
        ),
        "alignment_chart": (
            output_dir
            / "Layer_3B_Resource_Alignment_vs_Pressure.png"
        ),
        "support_chart": (
            output_dir
            / "Layer_3B_Prior_Support_vs_Pressure.png"
        ),
        "shape_chart": (
            output_dir
            / "Layer_3B_Pressure_by_Resource_Shape.png"
        ),
    }

    write_csv(
        outputs["player_allocation"],
        player_rows,
        player_columns,
    )
    write_csv(
        outputs["team_master"],
        team_rows,
        team_columns,
    )
    write_csv(
        outputs["primary_shape_summary"],
        primary_shape_summary,
    )
    write_csv(
        outputs["detail_shape_summary"],
        detail_shape_summary,
    )
    write_csv(
        outputs["strategy_summary"],
        strategy_summary,
    )
    write_csv(outputs["models"], primary_models)
    write_csv(outputs["change_rows"], difference_rows)
    write_csv(outputs["change_models"], change_models)
    write_csv(outputs["matched_pairs"], matched_pairs)
    write_csv(outputs["matched_summary"], matched_summary)
    write_csv(outputs["sensitivity"], sensitivity)

    with outputs["findings"].open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            findings,
            handle,
            indent=2,
            default=serialize_value,
        )

    outputs["methodology"].write_text(
        methodology,
        encoding="utf-8",
    )

    make_same_resources_chart(
        team_rows,
        outputs["same_resources_chart"],
    )
    make_alignment_chart(
        team_rows,
        outputs["alignment_chart"],
    )
    make_support_chart(
        team_rows,
        outputs["support_chart"],
    )
    make_shape_outcomes_chart(
        primary_shape_summary,
        outputs["shape_chart"],
    )

    print(
        json.dumps(
            {
                "status": "Layer 3B build complete",
                "output_dir": str(output_dir),
                "player_segments": len(player_rows),
                "team_seasons": len(team_rows),
                "prior_model_team_seasons": findings[
                    "sample"
                ]["prior_model_team_seasons"],
                "outputs": {
                    key: path.name
                    for key, path in outputs.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
