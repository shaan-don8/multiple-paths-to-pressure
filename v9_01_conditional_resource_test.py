#!/usr/bin/env python
"""
V9.01 — Conditional Resource Test
Pressure Creation Project

Purpose
-------
Test whether total defensive-front resource commitment provides incremental
information about subsequent pressure once demonstrated prior room quality is
known, and whether the resource association changes across the observed room-
quality distribution.

Primary sample: frozen Layer 3 N=82 team-seasons, 2023-2025.
Inference: OLS with season fixed effects and team-clustered standard errors.

Outputs
-------
V9_01_conditional_resource_model_results.csv
V9_01_resource_marginal_effects.csv
V9_01_summary.txt
"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import norm

def fit_clustered(formula, data):
    return smf.ols(formula, data=data).fit(
        cov_type="cluster",
        cov_kwds={"groups": data["team_key"]}
    )

def extract_terms(model, outcome_name, model_name, terms):
    ci = model.conf_int()
    rows = []
    for term in terms:
        if term not in model.params.index:
            continue
        rows.append({
            "outcome": outcome_name,
            "model": model_name,
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
    return rows

def marginal_resource_effect(model, quality_10, quality_mean_10):
    interaction = "total_resource_index:quality_centered_10"
    q_center = quality_10 - quality_mean_10
    est = (
        model.params["total_resource_index"]
        + q_center * model.params[interaction]
    )
    cov = model.cov_params()
    var = (
        cov.loc["total_resource_index", "total_resource_index"]
        + q_center**2 * cov.loc[interaction, interaction]
        + 2 * q_center * cov.loc["total_resource_index", interaction]
    )
    se = float(np.sqrt(var))
    z = est / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return est, se, est - 1.96 * se, est + 1.96 * se, p

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
    ap.add_argument("--outdir", default="/mnt/data")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    analytic = pd.read_csv(args.analytic)
    player = pd.read_csv(args.player_resource)

    assert len(analytic) == 82, f"Expected frozen Layer 3 N=82, got {len(analytic)}"
    assert not analytic.duplicated(["season", "team_key"]).any()

    # Frozen prior-room-quality construction:
    # equal-weight mean prior quality percentile among current resource-bearing
    # ED/DI players. Unavailable priors are already neutralized to 0.50 in the
    # canonical player-resource file.
    rb = player.loc[player["player_resource_units"] > 0].copy()
    room_q = (
        rb.groupby(["season", "team_key"], as_index=False)["prior_quality_pct"]
        .mean()
        .rename(columns={"prior_quality_pct": "prior_room_quality_pct"})
    )

    df = analytic.merge(
        room_q, on=["season", "team_key"], how="left", validate="one_to_one"
    )
    assert df["prior_room_quality_pct"].notna().all()

    df["prior_room_quality_10"] = df["prior_room_quality_pct"] * 10.0
    quality_mean_10 = df["prior_room_quality_10"].mean()
    df["quality_centered_10"] = (
        df["prior_room_quality_10"] - quality_mean_10
    )

    # The stored resource_quality_alignment is the resource-weighted prior
    # quality level. The final manuscript/Table 2 alignment term is the
    # difference between resource-weighted and equal-weight prior room quality.
    df["alignment_diff_10"] = (
        df["resource_quality_alignment"] - df["prior_room_quality_pct"]
    ) * 10.0

    outcomes = {
        "overall_pressure": "layer2_overall_pressure_rate_pp",
        "four_man_pressure": "layer2_four_man_pressure_rate_pp",
    }

    model_rows = []
    marginal_rows = []

    for outcome_name, y in outcomes.items():
        formulas = {
            "conditional_M2": (
                f"{y} ~ total_resource_index + prior_room_quality_10 "
                "+ top1_resource_share_10 + players_2_3_resource_share_10 "
                "+ C(season)"
            ),
            "conditional_M4": (
                f"{y} ~ total_resource_index + prior_room_quality_10 "
                "+ top1_resource_share_10 + players_2_3_resource_share_10 "
                "+ returning_prior_rush_share_10 + unproven_resource_share_10 "
                "+ alignment_diff_10 + C(season)"
            ),
            "interaction_M2": (
                f"{y} ~ total_resource_index * quality_centered_10 "
                "+ top1_resource_share_10 + players_2_3_resource_share_10 "
                "+ C(season)"
            ),
            "interaction_M4": (
                f"{y} ~ total_resource_index * quality_centered_10 "
                "+ top1_resource_share_10 + players_2_3_resource_share_10 "
                "+ returning_prior_rush_share_10 + unproven_resource_share_10 "
                "+ alignment_diff_10 + C(season)"
            ),
        }

        fitted = {}
        for model_name, formula in formulas.items():
            model = fit_clustered(formula, df)
            fitted[model_name] = model
            model_rows.extend(
                extract_terms(
                    model,
                    outcome_name,
                    model_name,
                    [
                        "total_resource_index",
                        "prior_room_quality_10",
                        "quality_centered_10",
                        "total_resource_index:quality_centered_10",
                    ],
                )
            )

        # Primary marginal-effects readout: full-control interaction model.
        model = fitted["interaction_M4"]
        for q_label, q in {
            "25th_percentile": df["prior_room_quality_10"].quantile(0.25),
            "50th_percentile": df["prior_room_quality_10"].quantile(0.50),
            "75th_percentile": df["prior_room_quality_10"].quantile(0.75),
        }.items():
            est, se, lo, hi, p = marginal_resource_effect(
                model, q, quality_mean_10
            )
            marginal_rows.append({
                "outcome": outcome_name,
                "model": "interaction_M4",
                "quality_level": q_label,
                "prior_room_quality_10": q,
                "marginal_effect_resource_index": est,
                "std_error": se,
                "ci_low": lo,
                "ci_high": hi,
                "p_value": p,
                "n": int(model.nobs),
            })

    model_df = pd.DataFrame(model_rows)
    marginal_df = pd.DataFrame(marginal_rows)

    model_path = outdir / "V9_01_conditional_resource_model_results.csv"
    marginal_path = outdir / "V9_01_resource_marginal_effects.csv"
    summary_path = outdir / "V9_01_summary.txt"

    model_df.to_csv(model_path, index=False)
    marginal_df.to_csv(marginal_path, index=False)

    def term_row(outcome, model, term):
        r = model_df.query(
            "outcome == @outcome and model == @model and term == @term"
        ).iloc[0]
        return r

    lines = [
        "V9.01 — CONDITIONAL RESOURCE TEST",
        "=" * 72,
        "Frozen Layer 3 sample: N=82 team-seasons, 2023-2025.",
        "Season fixed effects; team-clustered standard errors.",
        "",
        "PRIMARY CONDITIONAL RESULTS",
    ]

    for outcome in ["overall_pressure", "four_man_pressure"]:
        r = term_row(outcome, "conditional_M4", "total_resource_index")
        q = term_row(outcome, "conditional_M4", "prior_room_quality_10")
        i = term_row(
            outcome,
            "interaction_M4",
            "total_resource_index:quality_centered_10",
        )
        lines += [
            f"{outcome}:",
            (
                f"  Resource index conditional on demonstrated quality: "
                f"{r.estimate:+.3f} pp "
                f"[95% CI {r.ci_low:+.3f}, {r.ci_high:+.3f}], "
                f"p={r.p_value:.3f}"
            ),
            (
                f"  Prior room quality (+10 percentile points): "
                f"{q.estimate:+.3f} pp "
                f"[95% CI {q.ci_low:+.3f}, {q.ci_high:+.3f}], "
                f"p={q.p_value:.4f}"
            ),
            (
                f"  Resource x quality interaction: "
                f"{i.estimate:+.3f}, "
                f"[95% CI {i.ci_low:+.3f}, {i.ci_high:+.3f}], "
                f"p={i.p_value:.3f}"
            ),
        ]

        sub = marginal_df.query("outcome == @outcome")
        for _, mr in sub.iterrows():
            lines.append(
                f"  Resource marginal effect at {mr.quality_level}: "
                f"{mr.marginal_effect_resource_index:+.3f} pp "
                f"[95% CI {mr.ci_low:+.3f}, {mr.ci_high:+.3f}], "
                f"p={mr.p_value:.3f}"
            )
        lines.append("")

    lines += [
        "INTERPRETATION BOUNDARY",
        "The analysis tests incremental association, not a causal return to spending.",
        "The resource-quality interaction is not statistically distinguishable from zero",
        "for either outcome, so the data do not establish a literal quality threshold",
        "above which resources cease to matter. The supported result is narrower:",
        "once demonstrated room quality and the frozen room-construction controls are",
        "accounted for, greater total resource commitment does not show a reliable",
        "positive incremental association with subsequent pressure in this sample.",
    ]
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    print(summary_path.read_text(encoding="utf-8"))
    print("\nWrote:")
    print(model_path)
    print(marginal_path)
    print(summary_path)

if __name__ == "__main__":
    main()
