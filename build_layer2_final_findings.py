#!/usr/bin/env python3
"""
Freeze Layer 2 V2 and generate the final findings package.

Frozen methodology
------------------
- Pressure creation determines player standing and star status.
- Creation quality is the existing four-component, season-position
  standardized composite.
- Creation score is the geometric mean of creation percentile and
  volume percentile.
- Finishing is the shrunk share of pressures that become sacks or hits.
- Finishing is descriptive only and is never blended into creation.
- The primary room taxonomy remains:
    * Star + Depth
    * Heliocentric Star
    * Distributed Rotation
    * Thin / Mixed

This script creates final tables, model summaries, graphics, a JSON
findings file, and a readable Markdown report.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf


ARCHETYPE_ORDER = [
    "Star + Depth",
    "Distributed Rotation",
    "Heliocentric Star",
    "Thin / Mixed",
]

CREATION_TIER_ORDER = [
    "Creation Star",
    "Primary Creator",
    "High-End Creator",
    "Rotation Creator",
    "Depth Creator",
]

RANDOM_SEED = 20260722
BOOTSTRAP_ITERATIONS = 5000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=".")
    parser.add_argument("--output-dir", default=".")
    return parser.parse_args()


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def bootstrap_median_ci(
    values: pd.Series,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = RANDOM_SEED,
) -> tuple[float, float, float]:
    clean = numeric(values).dropna().to_numpy(dtype=float)

    if len(clean) == 0:
        return np.nan, np.nan, np.nan

    rng = np.random.default_rng(seed)
    medians = np.empty(iterations, dtype=float)

    for index in range(iterations):
        sample = rng.choice(clean, size=len(clean), replace=True)
        medians[index] = np.median(sample)

    return (
        float(np.median(clean)),
        float(np.quantile(medians, 0.025)),
        float(np.quantile(medians, 0.975)),
    )


def bootstrap_median_difference(
    group_a: pd.Series,
    group_b: pd.Series,
    iterations: int = BOOTSTRAP_ITERATIONS,
    seed: int = RANDOM_SEED,
) -> tuple[float, float, float]:
    a = numeric(group_a).dropna().to_numpy(dtype=float)
    b = numeric(group_b).dropna().to_numpy(dtype=float)

    if len(a) == 0 or len(b) == 0:
        return np.nan, np.nan, np.nan

    rng = np.random.default_rng(seed)
    differences = np.empty(iterations, dtype=float)

    for index in range(iterations):
        sample_a = rng.choice(a, size=len(a), replace=True)
        sample_b = rng.choice(b, size=len(b), replace=True)
        differences[index] = np.median(sample_a) - np.median(sample_b)

    observed = float(np.median(a) - np.median(b))

    return (
        observed,
        float(np.quantile(differences, 0.025)),
        float(np.quantile(differences, 0.975)),
    )


def load_sources(data_dir: Path) -> dict[str, object]:
    paths = {
        "team": data_dir / "Layer_2_Creation_Finish_v2_Team_Master.csv",
        "player": data_dir / "Layer_2_Creation_Finish_v2_Player_Master.csv",
        "stability": data_dir / "Layer_2_Creation_Finish_v2_Stability.csv",
        "models": data_dir / "Layer_2_Creation_Finish_v2_Incremental_Models.csv",
        "sanity": data_dir / "Layer_2_Creation_Finish_v2_Sanity_Check.csv",
        "audit": data_dir / "Layer_2_Creation_Finish_v2_Audit.json",
    }

    missing = [str(path) for path in paths.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing required V2 outputs:\n" + "\n".join(missing)
        )

    with paths["audit"].open("r", encoding="utf-8") as handle:
        audit = json.load(handle)

    return {
        "team": pd.read_csv(paths["team"], low_memory=False),
        "player": pd.read_csv(paths["player"], low_memory=False),
        "stability": pd.read_csv(paths["stability"], low_memory=False),
        "models": pd.read_csv(paths["models"], low_memory=False),
        "sanity": pd.read_csv(paths["sanity"], low_memory=False),
        "audit": audit,
    }


def unique_player_seasons(player: pd.DataFrame) -> pd.DataFrame:
    return (
        player.sort_values(
            ["season", "player_id", "segment_share"],
            ascending=[True, True, False],
        )
        .drop_duplicates(["season", "player_id"])
        .copy()
    )


def build_room_summary(team: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for order, archetype in enumerate(ARCHETYPE_ORDER, start=1):
        group = team.loc[team["archetype"] == archetype].copy()

        pressure_median, pressure_low, pressure_high = bootstrap_median_ci(
            group["pressure_rate"],
            seed=RANDOM_SEED + order,
        )
        composite_median, composite_low, composite_high = bootstrap_median_ci(
            group["pass_defense_composite"],
            seed=RANDOM_SEED + 100 + order,
        )
        epa_median, epa_low, epa_high = bootstrap_median_ci(
            group["epa_quality_z"],
            seed=RANDOM_SEED + 200 + order,
        )

        rows.append(
            {
                "archetype": archetype,
                "n_team_seasons": int(len(group)),
                "median_pressure_rate": pressure_median,
                "pressure_rate_ci_low": pressure_low,
                "pressure_rate_ci_high": pressure_high,
                "median_pressure_percentile": float(
                    group["pressure_pct"].median()
                ),
                "median_four_man_pressure_z": float(
                    group["four_man_pressure_z"].median()
                ),
                "median_epa_quality_z": epa_median,
                "epa_quality_ci_low": epa_low,
                "epa_quality_ci_high": epa_high,
                "median_success_quality_z": float(
                    group["success_quality_z"].median()
                ),
                "median_explosive_quality_z": float(
                    group["explosive_quality_z"].median()
                ),
                "median_dvoa_quality_z": float(
                    group["dvoa_quality_z"].median()
                ),
                "median_pass_defense_composite": composite_median,
                "pass_defense_composite_ci_low": composite_low,
                "pass_defense_composite_ci_high": composite_high,
                "above_average_pass_defense_rate": float(
                    group["above_avg_pass_defense"].mean()
                ),
                "top_quartile_pass_defense_rate": float(
                    group["top_quartile_pass_defense"].mean()
                ),
                "top_10_pass_defense_rate": float(
                    group["top_10_pass_defense"].mean()
                ),
                "median_star_index": float(group["star_index"].median()),
                "median_support_quality_z": float(
                    group["support_quality_z"].median()
                ),
                "median_top2_quality_z": float(
                    group["top2_quality_z"].median()
                ),
                "median_third_plus_quality_z": float(
                    group["third_plus_quality_z"].median()
                ),
                "median_effective_rushers": float(
                    group["effective_rushers"].median()
                ),
                "median_room_finish_rate": float(
                    group["room_contact_conversion"].median()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_pairwise_contrasts(team: pd.DataFrame) -> pd.DataFrame:
    comparisons = [
        ("Star + Depth", "Heliocentric Star"),
        ("Star + Depth", "Distributed Rotation"),
        ("Distributed Rotation", "Thin / Mixed"),
        ("Heliocentric Star", "Thin / Mixed"),
    ]

    outcomes = [
        ("pressure_rate", "Median pressure-rate difference"),
        (
            "pass_defense_composite",
            "Median pass-defense-composite difference",
        ),
        ("epa_quality_z", "Median EPA-quality-z difference"),
    ]

    rows = []

    for comparison_index, (group_a, group_b) in enumerate(
        comparisons,
        start=1,
    ):
        for outcome_index, (column, label) in enumerate(outcomes, start=1):
            observed, low, high = bootstrap_median_difference(
                team.loc[team["archetype"] == group_a, column],
                team.loc[team["archetype"] == group_b, column],
                seed=(
                    RANDOM_SEED
                    + comparison_index * 100
                    + outcome_index
                ),
            )

            rows.append(
                {
                    "group_a": group_a,
                    "group_b": group_b,
                    "outcome": label,
                    "difference_a_minus_b": observed,
                    "ci_low": low,
                    "ci_high": high,
                    "ci_excludes_zero": bool(
                        pd.notna(low)
                        and pd.notna(high)
                        and ((low > 0) or (high < 0))
                    ),
                }
            )

    return pd.DataFrame(rows)


def build_creation_tier_summary(player: pd.DataFrame) -> pd.DataFrame:
    unique = unique_player_seasons(player)

    rows = []

    for tier in CREATION_TIER_ORDER:
        group = unique.loc[unique["creation_tier"] == tier]

        rows.append(
            {
                "creation_tier": tier,
                "player_seasons": int(len(group)),
                "edge_player_seasons": int((group["position"] == "ED").sum()),
                "interior_player_seasons": int(
                    (group["position"] == "DI").sum()
                ),
                "median_creation_score": float(
                    group["creation_score"].median()
                ),
                "median_creation_percentile": float(
                    group["creation_pct"].median()
                ),
                "median_volume_percentile": float(
                    group["volume_pct"].median()
                ),
                "median_pressure_rate": float(
                    (
                        group["pressures"]
                        / group["pass_rush_opp"].replace(0, np.nan)
                    ).median()
                ),
                "median_finish_percentile": float(
                    group["finish_pct"].median()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_top_creators(player: pd.DataFrame) -> pd.DataFrame:
    unique = unique_player_seasons(player)

    columns = [
        "season",
        "player",
        "position",
        "team",
        "creation_score",
        "creation_pct",
        "volume_pct",
        "creation_tier",
        "finish_rate_shrunk",
        "finish_pct",
        "finish_tier",
        "pass_rush_opp",
        "pressures",
        "sacks",
        "hits",
        "hurries",
    ]

    return (
        unique[columns]
        .sort_values(
            ["creation_score", "finish_pct"],
            ascending=[False, False],
        )
        .head(50)
        .reset_index(drop=True)
    )


def build_room_models(team: pd.DataFrame) -> pd.DataFrame:
    frame = team.copy()

    frame["archetype"] = pd.Categorical(
        frame["archetype"],
        categories=[
            "Thin / Mixed",
            "Distributed Rotation",
            "Heliocentric Star",
            "Star + Depth",
        ],
    )

    specifications = [
        (
            "Pressure creation by room architecture",
            "pressure_z",
            (
                'pressure_z ~ '
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                '+ C(season)'
            ),
            False,
        ),
        (
            "Four-man pressure by room architecture",
            "four_man_pressure_z",
            (
                'four_man_pressure_z ~ '
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                '+ C(season)'
            ),
            False,
        ),
        (
            "Pass-defense composite by room architecture",
            "pass_defense_composite",
            (
                'pass_defense_composite ~ '
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                '+ C(season)'
            ),
            False,
        ),
        (
            "Pass-defense composite controlling for pressure",
            "pass_defense_composite",
            (
                'pass_defense_composite ~ pressure_z + '
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                '+ C(season)'
            ),
            True,
        ),
        (
            "EPA quality controlling for pressure",
            "epa_quality_z",
            (
                'epa_quality_z ~ pressure_z + '
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                '+ C(season)'
            ),
            True,
        ),
    ]

    rows = []

    for model_name, outcome, formula, controls_pressure in specifications:
        model = smf.ols(formula, data=frame).fit(cov_type="HC3")

        for archetype in [
            "Distributed Rotation",
            "Heliocentric Star",
            "Star + Depth",
        ]:
            parameter = (
                'C(archetype, Treatment(reference="Thin / Mixed"))'
                f'[T.{archetype}]'
            )

            interval = model.conf_int().loc[parameter]

            rows.append(
                {
                    "model": model_name,
                    "outcome": outcome,
                    "reference_group": "Thin / Mixed",
                    "archetype": archetype,
                    "controls_for_pressure_z": controls_pressure,
                    "coefficient": float(model.params[parameter]),
                    "robust_se": float(model.bse[parameter]),
                    "p_value": float(model.pvalues[parameter]),
                    "ci_low": float(interval.iloc[0]),
                    "ci_high": float(interval.iloc[1]),
                    "adjusted_r2": float(model.rsquared_adj),
                    "n": int(model.nobs),
                }
            )

        if "pressure_z" in model.params.index:
            interval = model.conf_int().loc["pressure_z"]

            rows.append(
                {
                    "model": model_name,
                    "outcome": outcome,
                    "reference_group": "N/A",
                    "archetype": "Pressure z control",
                    "controls_for_pressure_z": controls_pressure,
                    "coefficient": float(model.params["pressure_z"]),
                    "robust_se": float(model.bse["pressure_z"]),
                    "p_value": float(model.pvalues["pressure_z"]),
                    "ci_low": float(interval.iloc[0]),
                    "ci_high": float(interval.iloc[1]),
                    "adjusted_r2": float(model.rsquared_adj),
                    "n": int(model.nobs),
                }
            )

    return pd.DataFrame(rows)


def make_room_pressure_chart(
    room_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = room_summary.set_index("archetype").loc[ARCHETYPE_ORDER]

    figure, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar(
        plot.index,
        plot["median_pressure_rate"] * 100,
    )

    axis.set_title("Pass-Rush Room Architecture and Pressure Creation")
    axis.set_ylabel("Median team pressure rate")
    axis.set_xlabel("")
    axis.set_ylim(0, max(plot["median_pressure_rate"] * 100) * 1.22)
    axis.tick_params(axis="x", rotation=15)

    for bar, value, n in zip(
        bars,
        plot["median_pressure_rate"] * 100,
        plot["n_team_seasons"],
    ):
        axis.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{value:.1f}%\nN={int(n)}",
            ha="center",
            va="bottom",
        )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_room_defense_chart(
    room_summary: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = room_summary.set_index("archetype").loc[ARCHETYPE_ORDER]

    figure, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar(
        plot.index,
        plot["median_pass_defense_composite"],
    )

    axis.axhline(0, linewidth=1)
    axis.set_title("Pass-Rush Room Architecture and Pass-Defense Quality")
    axis.set_ylabel("Median pass-defense composite (z)")
    axis.set_xlabel("")
    axis.tick_params(axis="x", rotation=15)

    for bar, value, n in zip(
        bars,
        plot["median_pass_defense_composite"],
        plot["n_team_seasons"],
    ):
        vertical = "bottom" if value >= 0 else "top"
        offset = 0.03 if value >= 0 else -0.03

        axis.text(
            bar.get_x() + bar.get_width() / 2,
            value + offset,
            f"{value:+.2f}\nN={int(n)}",
            ha="center",
            va=vertical,
        )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_creation_finish_chart(
    player: pd.DataFrame,
    sanity: pd.DataFrame,
    output_path: Path,
) -> None:
    unique = unique_player_seasons(player)
    eligible = unique.loc[unique["total_pressures"] >= 15].copy()

    figure, axis = plt.subplots(figsize=(12, 8))

    axis.scatter(
        eligible["creation_score"],
        eligible["finish_pct"],
        alpha=0.35,
        s=25,
    )

    axis.axvline(0.95, linestyle="--", linewidth=1)
    axis.axhline(0.75, linestyle="--", linewidth=1)
    axis.axhline(0.25, linestyle="--", linewidth=1)

    axis.set_title(
        "Creation Defines Standing; Finishing Describes the Creator"
    )
    axis.set_xlabel("Creation score")
    axis.set_ylabel("Finish percentile")
    axis.set_xlim(
        max(0, eligible["creation_score"].min() - 0.03),
        1.01,
    )
    axis.set_ylim(0, 1.03)

    for row in sanity.itertuples(index=False):
        axis.annotate(
            f"{row.player} {int(row.season)}",
            (row.creation_score, row.finish_pct),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=9,
        )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_stability_chart(
    stability: pd.DataFrame,
    output_path: Path,
) -> None:
    figure, axis = plt.subplots(figsize=(12, 7))

    for metric, group in stability.groupby("metric"):
        ordered = group.sort_values("minimum_pressures")
        axis.plot(
            ordered["minimum_pressures"],
            ordered["year_over_year_spearman"],
            marker="o",
            label=metric.replace("_", " ").title(),
        )

    axis.set_title("Year-over-Year Stability of Pressure Finishing")
    axis.set_xlabel("Minimum pressure threshold")
    axis.set_ylabel("Year-over-year Spearman correlation")
    axis.set_ylim(0, max(0.4, stability["year_over_year_spearman"].max() * 1.15))
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def build_findings_json(
    audit: dict,
    room_summary: pd.DataFrame,
    contrasts: pd.DataFrame,
    stability: pd.DataFrame,
    finish_models: pd.DataFrame,
    room_models: pd.DataFrame,
) -> dict:
    room_lookup = room_summary.set_index("archetype")

    stability_15 = stability.loc[
        (stability["minimum_pressures"] == 15)
        & (stability["metric"] == "shrunk_contact_conversion")
    ].iloc[0]

    finish_incremental = finish_models.loc[
        finish_models["outcome"].isin(
            [
                "epa_quality_z",
                "pass_defense_composite",
                "sack_rate",
                "pressure_to_sack",
            ]
        ),
        [
            "outcome",
            "finish_adjusted_r2_delta",
            "finish_coefficient",
            "finish_p_value",
        ],
    ].to_dict(orient="records")

    star_depth_controlled = room_models.loc[
        (
            room_models["model"]
            == "Pass-defense composite controlling for pressure"
        )
        & (room_models["archetype"] == "Star + Depth")
    ].iloc[0]

    return {
        "status": "Layer 2 V2 frozen",
        "sample": {
            "player_segments": int(audit["player_segment_rows"]),
            "team_seasons": int(audit["team_seasons"]),
            "creation_stars": int(
                audit["creation_tier_counts"]["Creation Star"]
            ),
        },
        "frozen_methodology": {
            "creation_definition": (
                "Season-position creation-quality composite built from "
                "shrunk overall pressure rate, pass-rush win rate, "
                "true-pass-set pressure rate, and true-pass-set win rate."
            ),
            "creation_score": (
                "Geometric mean of creation percentile and volume "
                "percentile."
            ),
            "star_rule": (
                "Pressure creation alone determines star status."
            ),
            "finish_definition": (
                "Shrunk share of pressures that become sacks or hits."
            ),
            "finish_rule": (
                "Finishing is reported separately and is never blended "
                "into creation standing."
            ),
            "room_archetypes": ARCHETYPE_ORDER,
        },
        "headline_findings": {
            "star_plus_depth": {
                "median_pressure_rate": float(
                    room_lookup.loc[
                        "Star + Depth",
                        "median_pressure_rate",
                    ]
                ),
                "median_pass_defense_composite": float(
                    room_lookup.loc[
                        "Star + Depth",
                        "median_pass_defense_composite",
                    ]
                ),
                "top_quartile_pass_defense_rate": float(
                    room_lookup.loc[
                        "Star + Depth",
                        "top_quartile_pass_defense_rate",
                    ]
                ),
            },
            "distributed_rotation": {
                "median_pressure_rate": float(
                    room_lookup.loc[
                        "Distributed Rotation",
                        "median_pressure_rate",
                    ]
                ),
                "median_pass_defense_composite": float(
                    room_lookup.loc[
                        "Distributed Rotation",
                        "median_pass_defense_composite",
                    ]
                ),
            },
            "heliocentric_star": {
                "median_pressure_rate": float(
                    room_lookup.loc[
                        "Heliocentric Star",
                        "median_pressure_rate",
                    ]
                ),
                "median_pass_defense_composite": float(
                    room_lookup.loc[
                        "Heliocentric Star",
                        "median_pass_defense_composite",
                    ]
                ),
            },
            "thin_mixed": {
                "median_pressure_rate": float(
                    room_lookup.loc[
                        "Thin / Mixed",
                        "median_pressure_rate",
                    ]
                ),
                "median_pass_defense_composite": float(
                    room_lookup.loc[
                        "Thin / Mixed",
                        "median_pass_defense_composite",
                    ]
                ),
            },
            "star_plus_depth_incremental_association": {
                "controlled_composite_coefficient_vs_thin_mixed": float(
                    star_depth_controlled["coefficient"]
                ),
                "p_value": float(star_depth_controlled["p_value"]),
                "interpretation": (
                    "Star + Depth remains positively associated with "
                    "pass-defense quality after controlling for total "
                    "pressure creation and season. This is associative, "
                    "not causal."
                ),
            },
            "finish_stability": {
                "minimum_pressures": 15,
                "year_over_year_spearman": float(
                    stability_15["year_over_year_spearman"]
                ),
            },
            "finish_incremental_team_signal": finish_incremental,
        },
        "pairwise_bootstrap_contrasts": contrasts.to_dict(
            orient="records"
        ),
        "limitations": [
            (
                "Pressure timing, protection gravity, and immediate "
                "disruption are not directly measured."
            ),
            (
                "Finishing is affected by quarterback behavior, coverage, "
                "teammates, and scorer attribution."
            ),
            (
                "Room-archetype results are descriptive associations over "
                "128 team-seasons and should not be interpreted causally."
            ),
        ],
    }


def build_markdown(
    findings: dict,
    room_summary: pd.DataFrame,
    room_models: pd.DataFrame,
) -> str:
    room = room_summary.set_index("archetype")

    controlled = room_models.loc[
        room_models["model"]
        == "Pass-defense composite controlling for pressure"
    ]

    star_depth = controlled.loc[
        controlled["archetype"] == "Star + Depth"
    ].iloc[0]

    distributed = controlled.loc[
        controlled["archetype"] == "Distributed Rotation"
    ].iloc[0]

    heliocentric = controlled.loc[
        controlled["archetype"] == "Heliocentric Star"
    ].iloc[0]

    return f"""# Layer 2 Final Findings

## Frozen research design

Layer 2 separates **pressure creation** from **pressure finishing**.

Creation determines player standing. The creation-quality composite combines
shrunk overall pressure rate, pass-rush win rate, true-pass-set pressure rate,
and true-pass-set win rate within season and position. The creation score is the
geometric mean of creation percentile and volume percentile.

Finishing is the shrunk share of pressures that become sacks or hits. It is a
secondary player descriptor and is never blended into creation standing.

The primary room taxonomy is frozen as:

- Star + Depth
- Heliocentric Star
- Distributed Rotation
- Thin / Mixed

## Headline room findings

| Room construction | N | Median pressure rate | Median pass-defense composite | Top-quartile defense rate |
|---|---:|---:|---:|---:|
| Star + Depth | {int(room.loc["Star + Depth", "n_team_seasons"])} | {room.loc["Star + Depth", "median_pressure_rate"]:.1%} | {room.loc["Star + Depth", "median_pass_defense_composite"]:+.2f} | {room.loc["Star + Depth", "top_quartile_pass_defense_rate"]:.1%} |
| Distributed Rotation | {int(room.loc["Distributed Rotation", "n_team_seasons"])} | {room.loc["Distributed Rotation", "median_pressure_rate"]:.1%} | {room.loc["Distributed Rotation", "median_pass_defense_composite"]:+.2f} | {room.loc["Distributed Rotation", "top_quartile_pass_defense_rate"]:.1%} |
| Heliocentric Star | {int(room.loc["Heliocentric Star", "n_team_seasons"])} | {room.loc["Heliocentric Star", "median_pressure_rate"]:.1%} | {room.loc["Heliocentric Star", "median_pass_defense_composite"]:+.2f} | {room.loc["Heliocentric Star", "top_quartile_pass_defense_rate"]:.1%} |
| Thin / Mixed | {int(room.loc["Thin / Mixed", "n_team_seasons"])} | {room.loc["Thin / Mixed", "median_pressure_rate"]:.1%} | {room.loc["Thin / Mixed", "median_pass_defense_composite"]:+.2f} | {room.loc["Thin / Mixed", "top_quartile_pass_defense_rate"]:.1%} |

**Star + Depth is the strongest construction in the sample.** It pairs the
highest median pressure rate with the best median pass-defense composite.

**Distributed Rotation is the strongest non-star pathway.** It meaningfully
outperforms Thin / Mixed rooms in pressure creation and overall pass-defense
quality.

**A heliocentric star is not sufficient by itself.** Heliocentric rooms are
better than Thin / Mixed rooms at generating pressure, but their downstream
defensive results are much closer to average than Star + Depth rooms.

## Incremental room-model results

With Thin / Mixed as the reference group and controlling for total pressure
creation plus season:

- Star + Depth: composite coefficient {star_depth["coefficient"]:+.3f},
  p={star_depth["p_value"]:.3f}
- Distributed Rotation: composite coefficient {distributed["coefficient"]:+.3f},
  p={distributed["p_value"]:.3f}
- Heliocentric Star: composite coefficient {heliocentric["coefficient"]:+.3f},
  p={heliocentric["p_value"]:.3f}

The Star + Depth association remains positive after controlling for aggregate
pressure creation. This supports the interpretation that credible support may
matter beyond simply reaching the same pressure rate, although the model is
associative rather than causal.

## Finishing result

Shrunk hit-or-sack conversion has moderate year-over-year stability
(Spearman approximately {findings["headline_findings"]["finish_stability"]["year_over_year_spearman"]:.3f}
with a 15-pressure minimum), so it is reasonable to describe a player's
finishing profile.

At the room level, finishing does not meaningfully improve the explanation of
EPA quality, pass-defense composite, sack rate, or pressure-to-sack conversion
after pressure creation is included. Finishing should remain a descriptive
secondary layer rather than a primary room-construction axis.

## Final Layer 2 conclusion

Pressure creation is the foundational star attribute. The strongest rooms do
not merely employ an elite creator; they pair that creator with enough support
to preserve quality beyond the first rusher. A distributed rotation is a viable
alternative pathway. Concentrating the rush around one star without credible
depth leaves meaningful value unrealized.

## Limitations

- Pressure timing and protection gravity are not directly observed.
- Sack and hit conversion retain quarterback, coverage, teammate, and scorer
  context.
- The room results describe 128 team-seasons and should not be interpreted as
  causal estimates.
"""


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    sources = load_sources(data_dir)

    team = sources["team"]
    player = sources["player"]
    stability = sources["stability"]
    finish_models = sources["models"]
    sanity = sources["sanity"]
    audit = sources["audit"]

    room_summary = build_room_summary(team)
    contrasts = build_pairwise_contrasts(team)
    tier_summary = build_creation_tier_summary(player)
    top_creators = build_top_creators(player)
    room_models = build_room_models(team)

    findings = build_findings_json(
        audit=audit,
        room_summary=room_summary,
        contrasts=contrasts,
        stability=stability,
        finish_models=finish_models,
        room_models=room_models,
    )

    markdown = build_markdown(
        findings=findings,
        room_summary=room_summary,
        room_models=room_models,
    )

    outputs = {
        "room_summary": output_dir
        / "Layer_2_Final_Room_Archetype_Summary.csv",
        "contrasts": output_dir
        / "Layer_2_Final_Pairwise_Contrasts.csv",
        "tier_summary": output_dir
        / "Layer_2_Final_Creation_Tier_Summary.csv",
        "top_creators": output_dir
        / "Layer_2_Final_Top_Creators.csv",
        "room_models": output_dir
        / "Layer_2_Final_Room_Models.csv",
        "findings": output_dir / "Layer_2_Final_Findings.json",
        "report": output_dir / "Layer_2_Final_Findings.md",
        "pressure_chart": output_dir
        / "Layer_2_Final_Room_Pressure_Rate.png",
        "defense_chart": output_dir
        / "Layer_2_Final_Room_Pass_Defense.png",
        "creation_finish_chart": output_dir
        / "Layer_2_Final_Creation_vs_Finishing.png",
        "stability_chart": output_dir
        / "Layer_2_Final_Finish_Stability.png",
    }

    room_summary.to_csv(outputs["room_summary"], index=False)
    contrasts.to_csv(outputs["contrasts"], index=False)
    tier_summary.to_csv(outputs["tier_summary"], index=False)
    top_creators.to_csv(outputs["top_creators"], index=False)
    room_models.to_csv(outputs["room_models"], index=False)

    with outputs["findings"].open("w", encoding="utf-8") as handle:
        json.dump(findings, handle, indent=2)

    outputs["report"].write_text(markdown, encoding="utf-8")

    make_room_pressure_chart(room_summary, outputs["pressure_chart"])
    make_room_defense_chart(room_summary, outputs["defense_chart"])
    make_creation_finish_chart(
        player,
        sanity,
        outputs["creation_finish_chart"],
    )
    make_stability_chart(stability, outputs["stability_chart"])

    print(
        json.dumps(
            {
                "status": "Layer 2 final findings complete",
                "output_dir": str(output_dir),
                "outputs": {
                    key: path.name for key, path in outputs.items()
                },
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
