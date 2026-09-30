#!/usr/bin/env python3
"""
Layer 2 v2: creation-first pass-rush classification.

Research hierarchy
------------------
1. Pressure creation determines player standing and star status.
2. Pressure finishing is a conditional descriptor.
3. Finishing never modifies or overrides the creation score.
4. At the player level, finishing is measured primarily by shrunk
   hit-or-sack conversion because it is simpler and more stable than
   the previous three-part composite.
5. At the room level, finishing is tested for incremental signal after
   controlling for pressure creation.

Required files
--------------
- Layer_2_Player_Room_Master.csv
- Layer_2_Team_Season_Room_Master.csv
- Layer_2_Player_Pressure_Impact_Master.csv

Outputs
-------
- Layer_2_Creation_Finish_v2_Player_Master.csv
- Layer_2_Creation_Finish_v2_Team_Master.csv
- Layer_2_Creation_Finish_v2_Archetype_Summary.csv
- Layer_2_Creation_Finish_v2_Incremental_Models.csv
- Layer_2_Creation_Finish_v2_Stability.csv
- Layer_2_Creation_Finish_v2_Sanity_Check.csv
- Layer_2_Creation_Finish_v2_Audit.json
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import rankdata, spearmanr


# -------------------------------------------------------------------
# Transparent classification thresholds
# -------------------------------------------------------------------

CREATION_STAR_THRESHOLD = 0.95
PRIMARY_CREATOR_THRESHOLD = 0.90
HIGH_END_CREATOR_THRESHOLD = 0.75
ROTATION_CREATOR_THRESHOLD = 0.50

HIGH_FINISH_THRESHOLD = 0.75
LOW_FINISH_THRESHOLD = 0.25
MIN_PRESSURES_FOR_FINISH_LABEL = 15.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--output-dir", default=".")
    return parser.parse_args()


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def normalize_name(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def percentile_rank(series: pd.Series) -> pd.Series:
    values = numeric(series)
    valid = values.notna()
    result = pd.Series(np.nan, index=series.index, dtype=float)

    if valid.any():
        result.loc[valid] = (
            rankdata(values.loc[valid], method="average") / valid.sum()
        )

    return result


def zscore(series: pd.Series) -> pd.Series:
    values = numeric(series)
    mean = values.mean()
    std = values.std(ddof=0)

    if pd.isna(std) or std == 0:
        return pd.Series(0.0, index=series.index)

    return (values - mean) / std


def creation_tier(score: float) -> str:
    if pd.isna(score):
        return "Creation Unavailable"
    if score >= CREATION_STAR_THRESHOLD:
        return "Creation Star"
    if score >= PRIMARY_CREATOR_THRESHOLD:
        return "Primary Creator"
    if score >= HIGH_END_CREATOR_THRESHOLD:
        return "High-End Creator"
    if score >= ROTATION_CREATOR_THRESHOLD:
        return "Rotation Creator"
    return "Depth Creator"


def finish_tier(percentile: float, pressure_count: float) -> str:
    if pd.isna(percentile) or pd.isna(pressure_count):
        return "Finish Unavailable"
    if pressure_count < MIN_PRESSURES_FOR_FINISH_LABEL:
        return "Finish Sample Limited"
    if percentile >= HIGH_FINISH_THRESHOLD:
        return "High Finisher"
    if percentile < LOW_FINISH_THRESHOLD:
        return "Hurry-Heavy Finisher"
    return "Neutral Finisher"


def prepare_player_master(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)

    required = {
        "season",
        "team",
        "player",
        "player_id",
        "position",
        "segment_share",
        "pass_rush_opp",
        "pressures",
        "quality_z",
        "quality_pct",
        "volume_pct",
        "star_index",
        "rush_snaps",
        "rush_share",
        "pressure_share",
    }

    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            f"Layer_2_Player_Room_Master.csv is missing: {missing}"
        )

    numeric_columns = [
        "season",
        "player_id",
        "segment_share",
        "pass_rush_opp",
        "pressures",
        "quality_z",
        "quality_pct",
        "volume_pct",
        "star_index",
        "rush_snaps",
        "rush_share",
        "pressure_share",
    ]

    for column in numeric_columns:
        frame[column] = numeric(frame[column])

    frame["season"] = frame["season"].astype(int)
    frame["name_norm"] = frame["player"].map(normalize_name)
    frame["id_key"] = frame["player_id"].round().astype("Int64").astype(str)
    frame.loc[frame["player_id"].isna(), "id_key"] = ""

    return frame


def prepare_finish_master(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, low_memory=False)

    required = {
        "season",
        "player",
        "player_id",
        "position",
        "pass_rush_opp",
        "total_pressures",
        "sacks",
        "hits",
        "hurries",
        "shr_contact_conversion",
        "shr_contact_conversion_pct",
        "shr_sack_conversion",
        "shr_sack_conversion_pct",
        "shr_tps_contact_conversion",
        "shr_tps_contact_conversion_pct",
    }

    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(
            "Layer_2_Player_Pressure_Impact_Master.csv is missing: "
            f"{missing}"
        )

    numeric_columns = [
        "season",
        "player_id",
        "pass_rush_opp",
        "total_pressures",
        "sacks",
        "hits",
        "hurries",
        "shr_contact_conversion",
        "shr_contact_conversion_pct",
        "shr_sack_conversion",
        "shr_sack_conversion_pct",
        "shr_tps_contact_conversion",
        "shr_tps_contact_conversion_pct",
    ]

    for column in numeric_columns:
        frame[column] = numeric(frame[column])

    frame["season"] = frame["season"].astype(int)
    frame["name_norm"] = frame["player"].map(normalize_name)
    frame["id_key"] = frame["player_id"].round().astype("Int64").astype(str)
    frame.loc[frame["player_id"].isna(), "id_key"] = ""

    duplicate_rows = (
        frame["id_key"].ne("")
        & frame.duplicated(["season", "id_key"], keep=False)
    )

    if duplicate_rows.any():
        frame = (
            frame.sort_values(
                ["season", "id_key", "pass_rush_opp"],
                ascending=[True, True, False],
            )
            .drop_duplicates(["season", "id_key"], keep="first")
            .copy()
        )

    return frame


def merge_player_layers(
    creation: pd.DataFrame,
    finish: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    finish_columns = [
        "season",
        "id_key",
        "name_norm",
        "position",
        "total_pressures",
        "sacks",
        "hits",
        "hurries",
        "shr_contact_conversion",
        "shr_contact_conversion_pct",
        "shr_sack_conversion",
        "shr_sack_conversion_pct",
        "shr_tps_contact_conversion",
        "shr_tps_contact_conversion_pct",
    ]

    merged = creation.merge(
        finish[finish_columns],
        on=["season", "id_key"],
        how="left",
        suffixes=("", "_finish"),
        validate="many_to_one",
    )

    unmatched = merged["shr_contact_conversion_pct"].isna()
    fallback_matches = 0

    if unmatched.any():
        fallback = (
            finish[
                [
                    "season",
                    "name_norm",
                    "position",
                    "total_pressures",
                    "sacks",
                    "hits",
                    "hurries",
                    "shr_contact_conversion",
                    "shr_contact_conversion_pct",
                    "shr_sack_conversion",
                    "shr_sack_conversion_pct",
                    "shr_tps_contact_conversion",
                    "shr_tps_contact_conversion_pct",
                ]
            ]
            .sort_values(
                ["season", "name_norm", "position", "total_pressures"],
                ascending=[True, True, True, False],
            )
            .drop_duplicates(["season", "name_norm", "position"])
        )

        lookup = merged.loc[
            unmatched,
            ["season", "name_norm", "position"],
        ].merge(
            fallback,
            on=["season", "name_norm", "position"],
            how="left",
            validate="many_to_one",
        )

        fallback_matches = int(
            lookup["shr_contact_conversion_pct"].notna().sum()
        )

        fill_columns = [
            "total_pressures",
            "sacks",
            "hits",
            "hurries",
            "shr_contact_conversion",
            "shr_contact_conversion_pct",
            "shr_sack_conversion",
            "shr_sack_conversion_pct",
            "shr_tps_contact_conversion",
            "shr_tps_contact_conversion_pct",
        ]

        for column in fill_columns:
            merged.loc[unmatched, column] = lookup[column].to_numpy()

    merged["finish_available"] = (
        merged["shr_contact_conversion_pct"].notna().astype(int)
    )

    merged["creation_z"] = merged["quality_z"]
    merged["creation_pct"] = merged["quality_pct"]
    merged["creation_score"] = merged["star_index"]

    merged["creation_tier"] = merged["creation_score"].map(creation_tier)
    merged["is_creation_star"] = (
        merged["creation_score"] >= CREATION_STAR_THRESHOLD
    ).astype(int)

    # Simplified finish measure:
    # shrunk share of pressures that become hits or sacks.
    merged["finish_pct"] = merged["shr_contact_conversion_pct"]
    merged["finish_rate_shrunk"] = merged["shr_contact_conversion"]

    merged["finish_tier"] = [
        finish_tier(percentile, pressures)
        for percentile, pressures in zip(
            merged["finish_pct"],
            merged["total_pressures"],
        )
    ]

    merged["player_creation_finish_profile"] = (
        merged["creation_tier"]
        + " — "
        + merged["finish_tier"]
    )

    # No adjusted or blended star score is created.
    # Sorting should remain creation-first, with finish used only as
    # a secondary key when creation standing is otherwise comparable.
    merged["creation_sort_key"] = merged["creation_score"]
    merged["finish_tiebreak_key"] = merged["finish_pct"]

    audit = {
        "player_segment_rows": int(len(merged)),
        "finish_joined_rows": int(merged["finish_available"].sum()),
        "finish_missing_rows": int((merged["finish_available"] == 0).sum()),
        "finish_join_rate": float(merged["finish_available"].mean()),
        "fallback_name_matches": fallback_matches,
    }

    return merged, audit


def build_stability(player_master: pd.DataFrame) -> pd.DataFrame:
    unique = (
        player_master.sort_values(
            ["season", "player_id", "segment_share"],
            ascending=[True, True, False],
        )
        .drop_duplicates(["season", "player_id"])
        .copy()
    )

    rows = []

    metrics = {
        "finish_pct": "finish_percentile",
        "finish_rate_shrunk": "shrunk_contact_conversion",
        "shr_sack_conversion": "shrunk_sack_conversion",
        "shr_tps_contact_conversion": "shrunk_tps_contact_conversion",
    }

    for minimum_pressures in [0, 10, 15, 20, 30]:
        eligible = unique.loc[
            unique["player_id"].notna()
            & (unique["total_pressures"].fillna(0) >= minimum_pressures)
        ].copy()

        next_year = eligible.copy()
        next_year["season"] = next_year["season"] - 1

        paired = eligible.merge(
            next_year,
            on=["season", "player_id", "position"],
            suffixes=("_year1", "_year2"),
            how="inner",
        )

        for metric, label in metrics.items():
            x = paired[f"{metric}_year1"]
            y = paired[f"{metric}_year2"]
            valid = x.notna() & y.notna()

            rho = (
                float(spearmanr(x.loc[valid], y.loc[valid]).statistic)
                if valid.sum() >= 3
                else np.nan
            )

            rows.append(
                {
                    "minimum_pressures": minimum_pressures,
                    "metric": label,
                    "n_pairs": int(valid.sum()),
                    "year_over_year_spearman": rho,
                }
            )

    return pd.DataFrame(rows)


def build_team_layer(
    player_master: pd.DataFrame,
    team_master_path: Path,
) -> pd.DataFrame:
    teams = pd.read_csv(team_master_path, low_memory=False)
    teams["season"] = numeric(teams["season"]).astype(int)

    players = player_master.copy()

    for source, output in [
        ("total_pressures", "segment_total_pressures"),
        ("sacks", "segment_sacks"),
        ("hits", "segment_hits"),
        ("hurries", "segment_hurries"),
    ]:
        players[output] = numeric(players[source]) * players["segment_share"]

    players["segment_contact_pressures"] = (
        players["segment_sacks"] + players["segment_hits"]
    )

    grouped = (
        players.groupby(["season", "team"], as_index=False)
        .agg(
            allocated_pressures=("segment_total_pressures", "sum"),
            allocated_sacks=("segment_sacks", "sum"),
            allocated_hits=("segment_hits", "sum"),
            allocated_hurries=("segment_hurries", "sum"),
            allocated_contact_pressures=(
                "segment_contact_pressures",
                "sum",
            ),
            finish_covered_rush_snaps=(
                "rush_snaps",
                lambda values: float(
                    players.loc[values.index, "rush_snaps"]
                    .where(
                        players.loc[values.index, "finish_available"] == 1,
                        0,
                    )
                    .sum()
                ),
            ),
            total_room_rush_snaps=("rush_snaps", "sum"),
        )
    )

    grouped["room_contact_conversion"] = np.where(
        grouped["allocated_pressures"] > 0,
        grouped["allocated_contact_pressures"]
        / grouped["allocated_pressures"],
        np.nan,
    )

    grouped["room_sack_conversion"] = np.where(
        grouped["allocated_pressures"] > 0,
        grouped["allocated_sacks"] / grouped["allocated_pressures"],
        np.nan,
    )

    grouped["finish_coverage_share"] = np.where(
        grouped["total_room_rush_snaps"] > 0,
        grouped["finish_covered_rush_snaps"]
        / grouped["total_room_rush_snaps"],
        np.nan,
    )

    grouped["room_finish_pct"] = (
        grouped.groupby("season", group_keys=False)[
            "room_contact_conversion"
        ].transform(percentile_rank)
    )

    grouped["room_finish_z"] = (
        grouped.groupby("season", group_keys=False)[
            "room_contact_conversion"
        ].transform(zscore)
    )

    grouped["room_finish_tier"] = "Neutral-Finishing Room"
    grouped.loc[
        grouped["room_finish_pct"] >= HIGH_FINISH_THRESHOLD,
        "room_finish_tier",
    ] = "High-Finishing Room"
    grouped.loc[
        grouped["room_finish_pct"] < LOW_FINISH_THRESHOLD,
        "room_finish_tier",
    ] = "Hurry-Heavy Room"

    headliners = (
        players.sort_values(
            [
                "season",
                "team",
                "creation_score",
                "finish_tiebreak_key",
                "rush_snaps",
            ],
            ascending=[True, True, False, False, False],
        )
        .drop_duplicates(["season", "team"])
        [
            [
                "season",
                "team",
                "player",
                "player_id",
                "position",
                "creation_score",
                "creation_tier",
                "is_creation_star",
                "finish_pct",
                "finish_tier",
                "player_creation_finish_profile",
            ]
        ]
        .rename(
            columns={
                "player": "headliner_player",
                "player_id": "headliner_player_id",
                "position": "headliner_position",
                "creation_score": "headliner_creation_score",
                "creation_tier": "headliner_creation_tier",
                "is_creation_star": "headliner_is_creation_star",
                "finish_pct": "headliner_finish_pct",
                "finish_tier": "headliner_finish_tier",
                "player_creation_finish_profile": "headliner_profile",
            }
        )
    )

    output = (
        teams.merge(
            grouped,
            on=["season", "team"],
            how="left",
            validate="one_to_one",
        )
        .merge(
            headliners,
            on=["season", "team"],
            how="left",
            validate="one_to_one",
        )
    )

    archetype_column = next(
        (
            column
            for column in [
                "archetype",
                "room_archetype",
                "construction_archetype",
                "room_type",
            ]
            if column in output.columns
        ),
        None,
    )

    if archetype_column:
        output["creation_finish_room_label"] = (
            output[archetype_column].astype(str)
            + " | "
            + output["room_finish_tier"].astype(str)
        )
    else:
        output["creation_finish_room_label"] = output["room_finish_tier"]

    return output


def fit_incremental_models(team_master: pd.DataFrame) -> pd.DataFrame:
    """
    Test whether room finishing adds signal after pressure creation.

    Higher values of the quality-z outcomes represent better defense.
    HC3 robust standard errors are used. Season fixed effects are included.
    """
    frame = team_master.copy()

    outcome_candidates = [
        "epa_quality_z",
        "success_quality_z",
        "explosive_quality_z",
        "dvoa_quality_z",
        "pass_defense_composite",
        "sack_rate",
        "pressure_to_sack",
        "four_man_pressure_z",
    ]

    outcomes = [
        column for column in outcome_candidates if column in frame.columns
    ]

    creation_control = next(
        (
            column
            for column in ["pressure_z", "pressure_rate", "pressure_pct"]
            if column in frame.columns
        ),
        None,
    )

    if creation_control is None:
        return pd.DataFrame(
            [{
                "status": "Skipped",
                "reason": "No pressure-creation control was available.",
            }]
        )

    optional_controls = [
        column
        for column in [
            "snap_hhi",
            "trade_adjusted_rush_share",
        ]
        if column in frame.columns
    ]

    season_dummies = pd.get_dummies(
        frame["season"].astype(str),
        prefix="season",
        drop_first=True,
        dtype=float,
    )

    model_frame = pd.concat([frame, season_dummies], axis=1)
    season_columns = season_dummies.columns.tolist()

    results = []

    for outcome in outcomes:
        if outcome == creation_control:
            continue

        base_features = [
            creation_control,
            *optional_controls,
            *season_columns,
        ]

        finish_features = [
            *base_features,
            "room_finish_z",
        ]

        interaction_name = "pressure_x_finish"
        model_frame[interaction_name] = (
            numeric(model_frame[creation_control])
            * numeric(model_frame["room_finish_z"])
        )

        interaction_features = [
            *finish_features,
            interaction_name,
        ]

        required = [
            outcome,
            *interaction_features,
        ]

        clean = (
            model_frame[required]
            .replace([np.inf, -np.inf], np.nan)
            .dropna()
        )

        if len(clean) < max(40, len(interaction_features) + 12):
            continue

        y = numeric(clean[outcome]).astype(float)

        def fit(features: list[str]):
            x = sm.add_constant(
                clean[features].apply(numeric).astype(float),
                has_constant="add",
            )
            return sm.OLS(y, x).fit(cov_type="HC3")

        base_model = fit(base_features)
        finish_model = fit(finish_features)
        interaction_model = fit(interaction_features)

        results.append(
            {
                "outcome": outcome,
                "n": int(len(clean)),
                "creation_control": creation_control,
                "base_adjusted_r2": float(base_model.rsquared_adj),
                "finish_adjusted_r2": float(finish_model.rsquared_adj),
                "finish_adjusted_r2_delta": float(
                    finish_model.rsquared_adj - base_model.rsquared_adj
                ),
                "finish_coefficient": float(
                    finish_model.params["room_finish_z"]
                ),
                "finish_p_value": float(
                    finish_model.pvalues["room_finish_z"]
                ),
                "finish_ci_low": float(
                    finish_model.conf_int().loc["room_finish_z", 0]
                ),
                "finish_ci_high": float(
                    finish_model.conf_int().loc["room_finish_z", 1]
                ),
                "interaction_adjusted_r2": float(
                    interaction_model.rsquared_adj
                ),
                "interaction_adjusted_r2_delta_vs_base": float(
                    interaction_model.rsquared_adj
                    - base_model.rsquared_adj
                ),
                "interaction_coefficient": float(
                    interaction_model.params[interaction_name]
                ),
                "interaction_p_value": float(
                    interaction_model.pvalues[interaction_name]
                ),
            }
        )

    if not results:
        return pd.DataFrame(
            [{
                "status": "Skipped",
                "reason": "No compatible outcome had enough complete rows.",
            }]
        )

    return pd.DataFrame(results)


def build_archetype_summary(team_master: pd.DataFrame) -> pd.DataFrame:
    group_column = "creation_finish_room_label"

    aggregations = {
        "n": ("team", "size"),
        "median_room_contact_conversion": (
            "room_contact_conversion",
            "median",
        ),
        "median_room_sack_conversion": (
            "room_sack_conversion",
            "median",
        ),
        "median_headliner_creation_score": (
            "headliner_creation_score",
            "median",
        ),
        "median_headliner_finish_pct": (
            "headliner_finish_pct",
            "median",
        ),
        "median_finish_coverage": (
            "finish_coverage_share",
            "median",
        ),
    }

    for column in [
        "pressure_rate",
        "pressure_pct",
        "four_man_pressure_z",
        "epa_quality_z",
        "success_quality_z",
        "explosive_quality_z",
        "pass_defense_composite",
    ]:
        if column in team_master.columns:
            aggregations[f"median_{column}"] = (column, "median")

    return (
        team_master.groupby(group_column, dropna=False)
        .agg(**aggregations)
        .reset_index()
        .sort_values("n", ascending=False)
    )


def build_sanity_check(player_master: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        (2024, "Jalen Carter"),
        (2024, "Zach Allen"),
        (2022, "Micah Parsons"),
        (2022, "Trey Hendrickson"),
    ]

    unique = (
        player_master.sort_values(
            ["season", "player", "segment_share"],
            ascending=[True, True, False],
        )
        .drop_duplicates(["season", "player"])
        .copy()
    )

    rows = []

    for season, player_name in comparisons:
        match = unique.loc[
            (unique["season"] == season)
            & (
                unique["player"].map(normalize_name)
                == normalize_name(player_name)
            )
        ].copy()

        rows.append(match)

    output = pd.concat(rows, ignore_index=True)

    columns = [
        "season",
        "player",
        "position",
        "team",
        "creation_pct",
        "volume_pct",
        "creation_score",
        "creation_tier",
        "is_creation_star",
        "finish_rate_shrunk",
        "finish_pct",
        "finish_tier",
        "player_creation_finish_profile",
        "pass_rush_opp",
        "pressures",
        "total_pressures",
        "sacks",
        "hits",
        "hurries",
    ]

    return output[columns]


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    player_path = data_dir / "Layer_2_Player_Room_Master.csv"
    team_path = data_dir / "Layer_2_Team_Season_Room_Master.csv"
    finish_path = data_dir / "Layer_2_Player_Pressure_Impact_Master.csv"

    creation = prepare_player_master(player_path)
    finish = prepare_finish_master(finish_path)

    player_master, join_audit = merge_player_layers(creation, finish)
    team_master = build_team_layer(player_master, team_path)
    archetype_summary = build_archetype_summary(team_master)
    model_summary = fit_incremental_models(team_master)
    stability_summary = build_stability(player_master)
    sanity_check = build_sanity_check(player_master)

    outputs = {
        "player": (
            output_dir / "Layer_2_Creation_Finish_v2_Player_Master.csv"
        ),
        "team": (
            output_dir / "Layer_2_Creation_Finish_v2_Team_Master.csv"
        ),
        "archetype": (
            output_dir
            / "Layer_2_Creation_Finish_v2_Archetype_Summary.csv"
        ),
        "models": (
            output_dir
            / "Layer_2_Creation_Finish_v2_Incremental_Models.csv"
        ),
        "stability": (
            output_dir / "Layer_2_Creation_Finish_v2_Stability.csv"
        ),
        "sanity": (
            output_dir / "Layer_2_Creation_Finish_v2_Sanity_Check.csv"
        ),
        "audit": (
            output_dir / "Layer_2_Creation_Finish_v2_Audit.json"
        ),
    }

    player_master.to_csv(outputs["player"], index=False)
    team_master.to_csv(outputs["team"], index=False)
    archetype_summary.to_csv(outputs["archetype"], index=False)
    model_summary.to_csv(outputs["models"], index=False)
    stability_summary.to_csv(outputs["stability"], index=False)
    sanity_check.to_csv(outputs["sanity"], index=False)

    unique_player_seasons = (
        player_master.sort_values(
            ["season", "player_id", "segment_share"],
            ascending=[True, True, False],
        )
        .drop_duplicates(["season", "player_id"])
    )

    audit = {
        **join_audit,
        "team_seasons": int(len(team_master)),
        "creation_tier_counts": {
            str(key): int(value)
            for key, value in unique_player_seasons[
                "creation_tier"
            ].value_counts(dropna=False).items()
        },
        "finish_tier_counts": {
            str(key): int(value)
            for key, value in unique_player_seasons[
                "finish_tier"
            ].value_counts(dropna=False).items()
        },
        "room_finish_tier_counts": {
            str(key): int(value)
            for key, value in team_master[
                "room_finish_tier"
            ].value_counts(dropna=False).items()
        },
        "creation_finish_spearman": float(
            unique_player_seasons[
                ["creation_score", "finish_pct"]
            ].corr(method="spearman").iloc[0, 1]
        ),
        "research_decisions": {
            "creation_star_threshold": CREATION_STAR_THRESHOLD,
            "primary_creator_threshold": PRIMARY_CREATOR_THRESHOLD,
            "high_end_creator_threshold": HIGH_END_CREATOR_THRESHOLD,
            "rotation_creator_threshold": ROTATION_CREATOR_THRESHOLD,
            "high_finish_threshold": HIGH_FINISH_THRESHOLD,
            "low_finish_threshold": LOW_FINISH_THRESHOLD,
            "minimum_pressures_for_finish_label": (
                MIN_PRESSURES_FOR_FINISH_LABEL
            ),
            "star_rule": (
                "Pressure creation alone determines star status."
            ),
            "finish_rule": (
                "Finishing is the shrunk percentage of pressures that "
                "become hits or sacks. It is reported separately and "
                "never blended into the creation score."
            ),
            "ranking_rule": (
                "Sort by creation score first. Finish percentile may "
                "be used only as a secondary tie-break."
            ),
        },
        "outputs": {
            key: path.name for key, path in outputs.items() if key != "audit"
        },
    }

    with outputs["audit"].open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2)

    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
