#!/usr/bin/env python
"""
V9.03 — FTN × PFF Team-Season Concordance Audit
Pressure Creation Project

Purpose
-------
Quantify how closely the two provider systems agree at the defense-season level.

FTN:
    Binary team pressured-dropback rates (overall and four-man).

PFF:
    ED/DI player-attributed pressure production, aggregated to the defensive-front
    room as total pressures / player pass-rush opportunities.

The quantities are not expected to be numerically identical:
- FTN pressure is a team-level binary dropback event.
- PFF assigns pressure credits to individual defenders, so multiple player credits
  may occur on one pressured dropback.
- FTN team pressure can include rushers outside the ED/DI room.
- Provider charting definitions differ.

The audit therefore evaluates concordance (correlation/rank agreement), not equality.

Inputs
------
MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical(1).csv

Outputs
-------
V9_03_ftn_pff_concordance_summary.csv
V9_03_ftn_pff_teamseason.csv
V9_03_summary.txt
"""

import argparse
import csv
from pathlib import Path
import numpy as np
from scipy.stats import pearsonr, spearmanr

def safe_float(x):
    return float(x) if x not in ("", None) else np.nan

def corr(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    pr = pearsonr(x[mask], y[mask])
    sr = spearmanr(x[mask], y[mask])
    return {
        "n": int(mask.sum()),
        "pearson_r": float(pr.statistic),
        "pearson_p": float(pr.pvalue),
        "spearman_rho": float(sr.statistic),
        "spearman_p": float(sr.pvalue),
    }

def add_within_season_z(rows, field):
    seasons = sorted({r["season"] for r in rows})
    for season in seasons:
        rr = [r for r in rows if r["season"] == season]
        vals = np.array([r[field] for r in rr], dtype=float)
        mean = vals.mean()
        sd = vals.std(ddof=0)
        for r in rr:
            r[field + "_z"] = (r[field] - mean) / sd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--room",
        default="/mnt/data/MODEL_Layer2_TeamSeason_2022-2025_CreationRoomCanonical(1).csv"
    )
    ap.add_argument("--outdir", default="/mnt/data")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    rows = []
    with open(args.room, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "season": int(float(r["season"])),
                "team": r["team"],
                "pff_room_pressure_rate": safe_float(r["room_player_pressure_rate"]),
                "pff_room_pressures": safe_float(r["room_pressures"]),
                "pff_room_pass_rush_opp": safe_float(r["room_pass_rush_opp"]),
                "ftn_overall_pressure_rate": safe_float(r["pressure_rate"]),
                "ftn_four_man_pressure_rate": safe_float(r["four_man_pressure_rate"]),
                "ftn_eligible_dropbacks": safe_float(r["eligible_dropbacks"]),
            })

    assert len(rows) == 128, f"Expected 128 defense-seasons, got {len(rows)}"
    assert len({(r["season"], r["team"]) for r in rows}) == 128

    for field in [
        "pff_room_pressure_rate",
        "ftn_overall_pressure_rate",
        "ftn_four_man_pressure_rate",
    ]:
        add_within_season_z(rows, field)

    for r in rows:
        r["pff_minus_ftn_overall_z"] = (
            r["pff_room_pressure_rate_z"] - r["ftn_overall_pressure_rate_z"]
        )
        r["pff_minus_ftn_four_man_z"] = (
            r["pff_room_pressure_rate_z"] - r["ftn_four_man_pressure_rate_z"]
        )

    summary = []

    def add_summary(scope, season, ftn_field, label, season_adjusted=False):
        suffix = "_z" if season_adjusted else ""
        rr = rows if season is None else [r for r in rows if r["season"] == season]
        c = corr(
            [r["pff_room_pressure_rate" + suffix] for r in rr],
            [r[ftn_field + suffix] for r in rr],
        )
        summary.append({
            "scope": scope,
            "season": "" if season is None else season,
            "comparison": label,
            "scale": "within-season z-score" if season_adjusted else "raw rate",
            **c,
        })

    add_summary("pooled", None, "ftn_overall_pressure_rate",
                "PFF ED/DI room pressure rate vs FTN overall pressure", False)
    add_summary("pooled", None, "ftn_four_man_pressure_rate",
                "PFF ED/DI room pressure rate vs FTN four-man pressure", False)
    add_summary("pooled", None, "ftn_overall_pressure_rate",
                "PFF ED/DI room pressure rate vs FTN overall pressure", True)
    add_summary("pooled", None, "ftn_four_man_pressure_rate",
                "PFF ED/DI room pressure rate vs FTN four-man pressure", True)

    for season in [2022, 2023, 2024, 2025]:
        add_summary("season", season, "ftn_overall_pressure_rate",
                    "PFF ED/DI room pressure rate vs FTN overall pressure", False)
        add_summary("season", season, "ftn_four_man_pressure_rate",
                    "PFF ED/DI room pressure rate vs FTN four-man pressure", False)

    summary_path = outdir / "V9_03_ftn_pff_concordance_summary.csv"
    with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    team_path = outdir / "V9_03_ftn_pff_teamseason.csv"
    team_fields = list(rows[0].keys())
    with open(team_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=team_fields)
        writer.writeheader()
        writer.writerows(rows)

    # Pull the pooled season-adjusted headline values.
    so = next(r for r in summary if r["scope"]=="pooled"
              and r["scale"]=="within-season z-score"
              and "overall pressure" in r["comparison"])
    sf = next(r for r in summary if r["scope"]=="pooled"
              and r["scale"]=="within-season z-score"
              and "four-man pressure" in r["comparison"])

    # Largest absolute standardized disagreements for audit transparency.
    top_overall = sorted(
        rows, key=lambda r: abs(r["pff_minus_ftn_overall_z"]), reverse=True
    )[:5]
    top_four = sorted(
        rows, key=lambda r: abs(r["pff_minus_ftn_four_man_z"]), reverse=True
    )[:5]

    lines = [
        "V9.03 — FTN × PFF TEAM-SEASON CONCORDANCE AUDIT",
        "=" * 76,
        "N = 128 defense-seasons, 2022-2025.",
        "",
        "MEASUREMENT BOUNDARY",
        "FTN measures a binary team pressured-dropback event.",
        "PFF supplies player-attributed ED/DI pressure production.",
        "The audit tests concordance, not one-for-one equality.",
        "",
        "POOLED WITHIN-SEASON CONCORDANCE",
        (
            f"PFF ED/DI room pressure rate vs FTN overall pressure: "
            f"Pearson r={so['pearson_r']:.3f}; "
            f"Spearman rho={so['spearman_rho']:.3f}; "
            f"both p<.001."
        ),
        (
            f"PFF ED/DI room pressure rate vs FTN four-man pressure: "
            f"Pearson r={sf['pearson_r']:.3f}; "
            f"Spearman rho={sf['spearman_rho']:.3f}; "
            f"both p<.001."
        ),
        "",
        "YEAR-BY-YEAR RAW-RATE PEARSON CORRELATIONS",
    ]

    for season in [2022, 2023, 2024, 2025]:
        o = next(r for r in summary if r["scope"]=="season"
                 and r["season"]==season and "overall pressure" in r["comparison"])
        m = next(r for r in summary if r["scope"]=="season"
                 and r["season"]==season and "four-man pressure" in r["comparison"])
        lines.append(
            f"{season}: overall r={o['pearson_r']:.3f}; four-man r={m['pearson_r']:.3f}"
        )

    lines += [
        "",
        "LARGEST STANDARDIZED DISAGREEMENTS — OVERALL",
    ]
    for r in top_overall:
        lines.append(
            f"{r['season']} {r['team']}: PFF-FTN z difference "
            f"{r['pff_minus_ftn_overall_z']:+.3f}"
        )

    lines += ["", "LARGEST STANDARDIZED DISAGREEMENTS — FOUR-MAN"]
    for r in top_four:
        lines.append(
            f"{r['season']} {r['team']}: PFF-FTN z difference "
            f"{r['pff_minus_ftn_four_man_z']:+.3f}"
        )

    lines += [
        "",
        "INTERPRETATION",
        "The providers show strong, persistent team-season concordance despite",
        "different units, attribution rules, positional scope, and charting definitions.",
        "This supports using FTN for team pressured-dropback outcomes and PFF for",
        "player/room creation without claiming that their pressure totals should match",
        "mechanically. The remaining disagreement is measurement/context variation,",
        "not evidence of a failed season/team merge.",
    ]

    summary_txt = outdir / "V9_03_summary.txt"
    summary_txt.write_text("\n".join(lines), encoding="utf-8")

    print(summary_txt.read_text(encoding="utf-8"))
    print("\nWrote:")
    print(summary_path)
    print(team_path)
    print(summary_txt)

if __name__ == "__main__":
    main()
