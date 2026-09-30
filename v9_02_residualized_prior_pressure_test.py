#!/usr/bin/env python
"""
V9.02 — Residualized Prior-Pressure Test
Pressure Creation Project

Purpose
-------
Address autocorrelation / double-counting concerns when previous team pressure
and prior player ability are entered together.

For each prior season (2022-2024), expected team pressure is estimated from that
season's demonstrated headliner and support quality. Predictions are generated
leave-one-team-out within season, so each team's residual is based on a model
that excludes that team and uses no future-season outcomes.

Residual prior pressure = observed prior team pressure - expected prior team
pressure given demonstrated player-room quality.

The residual is then shifted one season and joined to the frozen Layer 3 N=82
panel.

Outputs
-------
V9_02_residualized_prior_pressure_teamseason.csv
V9_02_persistence_model_results.csv
V9_02_summary.txt
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

def fit_clustered(formula, data):
    return smf.ols(formula, data=data).fit(
        cov_type="cluster",
        cov_kwds={"groups": data["team_key"]}
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--analytic",
        default="/mnt/data/MODEL_Layer3_Analytic_TeamSeason_2023-2025_v1.csv"
    )
    ap.add_argument(
        "--player-resource",
        default="/mnt/data/MODEL_Layer3_PlayerResourceAllocation_2022-2025_v1.csv"
    )
    ap.add_argument(
        "--layer2-room",
        default="/mnt/data/MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical(1).csv"
    )
    ap.add_argument("--outdir", default="/mnt/data")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    analytic = pd.read_csv(args.analytic)
    player = pd.read_csv(args.player_resource)
    room = pd.read_csv(args.layer2_room)

    assert len(analytic) == 82
    assert not analytic.duplicated(["season", "team_key"]).any()
    assert len(room) == 128
    assert not room.duplicated(["season", "team"]).any()

    # Reconstruct frozen prior room quality.
    rb = player.loc[player["player_resource_units"] > 0].copy()
    room_q = (
        rb.groupby(["season", "team_key"], as_index=False)["prior_quality_pct"]
        .mean()
        .rename(columns={"prior_quality_pct": "prior_room_quality_pct"})
    )
    df = analytic.merge(
        room_q, on=["season", "team_key"], how="left", validate="one_to_one"
    )
    df["prior_room_quality_10"] = df["prior_room_quality_pct"] * 10.0
    df["alignment_diff_10"] = (
        df["resource_quality_alignment"] - df["prior_room_quality_pct"]
    ) * 10.0

    # Reconstruct the final Layer 2 continuous quality dimensions exactly:
    # within-season z-score of headliner/star creation quality and support quality.
    room = room.copy()
    room["headliner_quality_z"] = room.groupby("season")["star_quality_z"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0)
    )
    room["support_quality_z_std"] = room.groupby("season")["support_quality_z"].transform(
        lambda s: (s - s.mean()) / s.std(ddof=0)
    )
    room["overall_pressure_pp"] = room["pressure_rate"] * 100.0
    room["four_man_pressure_pp"] = room["four_man_pressure_rate"] * 100.0

    # Leave-one-team-out expected prior pressure, estimated separately within
    # each prior season. This prevents the held-out team's outcome from helping
    # define its own expected pressure and avoids future-season information.
    residual_rows = []
    for season in [2022, 2023, 2024]:
        rs = room.loc[room["season"] == season].copy()
        assert len(rs) == 32

        for _, row in rs.iterrows():
            train = rs.loc[rs["team"] != row["team"]].copy()
            new = pd.DataFrame([{
                "headliner_quality_z": row["headliner_quality_z"],
                "support_quality_z_std": row["support_quality_z_std"],
            }])

            for outcome in ["overall_pressure_pp", "four_man_pressure_pp"]:
                model = smf.ols(
                    f"{outcome} ~ headliner_quality_z + support_quality_z_std",
                    data=train
                ).fit()
                expected = float(model.predict(new).iloc[0])
                residual_rows.append({
                    "season": season,
                    "team": row["team"],
                    "outcome": outcome,
                    "observed_pressure_pp": row[outcome],
                    "expected_from_room_quality_pp": expected,
                    "residual_pressure_pp": row[outcome] - expected,
                })

    residual_long = pd.DataFrame(residual_rows)
    residual_wide = residual_long.pivot(
        index=["season", "team"],
        columns="outcome",
        values=[
            "observed_pressure_pp",
            "expected_from_room_quality_pp",
            "residual_pressure_pp",
        ],
    ).reset_index()

    residual_wide.columns = [
        "season", "team"
    ] + [f"{metric}_{outcome}" for metric, outcome in residual_wide.columns.tolist()[2:]]

    residual_path = outdir / "V9_02_residualized_prior_pressure_teamseason.csv"
    residual_wide.to_csv(residual_path, index=False)

    # Shift prior-season residuals onto current Layer 3 rows.
    prior = residual_wide.copy()
    prior["season"] = prior["season"] + 1
    prior = prior.rename(columns={"team": "team_key"})

    df = df.merge(
        prior, on=["season", "team_key"], how="left", validate="one_to_one"
    )

    required = [
        "residual_pressure_pp_overall_pressure_pp",
        "residual_pressure_pp_four_man_pressure_pp",
    ]
    assert df[required].notna().all().all()

    df["prior_raw_overall_pressure_pp"] = (
        df["observed_pressure_pp_overall_pressure_pp"]
    )
    df["prior_residual_overall_pressure_pp"] = (
        df["residual_pressure_pp_overall_pressure_pp"]
    )
    df["prior_raw_four_man_pressure_pp"] = (
        df["observed_pressure_pp_four_man_pressure_pp"]
    )
    df["prior_residual_four_man_pressure_pp"] = (
        df["residual_pressure_pp_four_man_pressure_pp"]
    )

    outcomes = {
        "overall_pressure": {
            "y": "layer2_overall_pressure_rate_pp",
            "raw": "prior_raw_overall_pressure_pp",
            "resid": "prior_residual_overall_pressure_pp",
        },
        "four_man_pressure": {
            "y": "layer2_four_man_pressure_rate_pp",
            "raw": "prior_raw_four_man_pressure_pp",
            "resid": "prior_residual_four_man_pressure_pp",
        },
    }

    rows = []

    for outcome_name, v in outcomes.items():
        y, raw, resid = v["y"], v["raw"], v["resid"]

        formulas = {
            "prior_raw_only": f"{y} ~ {raw} + C(season)",
            "room_quality_only": f"{y} ~ prior_room_quality_10 + C(season)",
            "room_quality_plus_raw_prior_pressure": (
                f"{y} ~ prior_room_quality_10 + {raw} + C(season)"
            ),
            "room_quality_plus_residual_prior_pressure": (
                f"{y} ~ prior_room_quality_10 + {resid} + C(season)"
            ),
            "full_room_plus_raw_prior_pressure": (
                f"{y} ~ total_resource_index + top1_resource_share_10 "
                "+ players_2_3_resource_share_10 + prior_room_quality_10 "
                "+ returning_prior_rush_share_10 + unproven_resource_share_10 "
                f"+ alignment_diff_10 + {raw} + C(season)"
            ),
            "full_room_plus_residual_prior_pressure": (
                f"{y} ~ total_resource_index + top1_resource_share_10 "
                "+ players_2_3_resource_share_10 + prior_room_quality_10 "
                "+ returning_prior_rush_share_10 + unproven_resource_share_10 "
                f"+ alignment_diff_10 + {resid} + C(season)"
            ),
        }

        for model_name, formula in formulas.items():
            model = fit_clustered(formula, df)
            ci = model.conf_int()

            prior_term = None
            if raw in model.params.index:
                prior_term = raw
            elif resid in model.params.index:
                prior_term = resid

            for term_role, term in [
                ("prior_room_quality", "prior_room_quality_10"),
                ("prior_pressure_control", prior_term),
            ]:
                if term is None or term not in model.params.index:
                    continue
                rows.append({
                    "outcome": outcome_name,
                    "model": model_name,
                    "term_role": term_role,
                    "term": term,
                    "estimate": model.params[term],
                    "std_error": model.bse[term],
                    "ci_low": ci.loc[term, 0],
                    "ci_high": ci.loc[term, 1],
                    "p_value": model.pvalues[term],
                    "n": int(model.nobs),
                    "r2": model.rsquared,
                    "adj_r2": model.rsquared_adj,
                })

            # Keep a model-level row even when quality is absent.
            if model_name == "prior_raw_only":
                pass

    results = pd.DataFrame(rows)
    results_path = outdir / "V9_02_persistence_model_results.csv"
    results.to_csv(results_path, index=False)

    summary_path = outdir / "V9_02_summary.txt"

    def get(outcome, model, role):
        return results.query(
            "outcome == @outcome and model == @model and term_role == @role"
        ).iloc[0]

    lines = [
        "V9.02 — RESIDUALIZED PRIOR-PRESSURE TEST",
        "=" * 72,
        "Frozen Layer 3 sample: N=82 team-seasons, 2023-2025.",
        "Residual construction: leave-one-team-out within each prior season.",
        "Expected prior pressure is based on demonstrated headliner + support quality.",
        "Persistence models use season fixed effects and team-clustered standard errors.",
        "",
    ]

    for outcome in ["overall_pressure", "four_man_pressure"]:
        lines.append(outcome.upper())

        for model_name in [
            "room_quality_plus_raw_prior_pressure",
            "room_quality_plus_residual_prior_pressure",
            "full_room_plus_raw_prior_pressure",
            "full_room_plus_residual_prior_pressure",
        ]:
            q = get(outcome, model_name, "prior_room_quality")
            p = get(outcome, model_name, "prior_pressure_control")
            lines += [
                f"  {model_name}:",
                (
                    f"    Prior room quality (+10 pct pts): "
                    f"{q.estimate:+.3f} pp "
                    f"[{q.ci_low:+.3f}, {q.ci_high:+.3f}], "
                    f"p={q.p_value:.4f}"
                ),
                (
                    f"    Prior-pressure control: "
                    f"{p.estimate:+.3f} "
                    f"[{p.ci_low:+.3f}, {p.ci_high:+.3f}], "
                    f"p={p.p_value:.4f}"
                ),
                f"    Adjusted R2: {q.adj_r2:.3f}",
            ]
        lines.append("")

    lines += [
        "INTERPRETATION",
        "Residualization strengthens the distinction between persistent player-room",
        "ability and prior team/system pressure. Prior room quality remains strongly",
        "positive after replacing raw prior pressure with pressure unexplained by the",
        "prior season's demonstrated headliner/support quality.",
        "",
        "For four-man pressure, residual prior pressure is not independently significant",
        "once room quality is included, while room quality remains strongly positive.",
        "For overall pressure, the residual prior-pressure term retains some independent",
        "signal, consistent with broader system/context persistence beyond the ED/DI room.",
    ]

    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(summary_path.read_text(encoding="utf-8"))
    print("\nWrote:")
    print(residual_path)
    print(results_path)
    print(summary_path)

if __name__ == "__main__":
    main()
