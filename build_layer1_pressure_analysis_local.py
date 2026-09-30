#!/usr/bin/env python3
"""Build the Layer 1 pressure-threshold analysis.

This script recreates the published Layer 1 outputs:

* Layer_1_Team_Season_Master.csv
* Layer_1_Pressure_Threshold_Analysis.xlsx

The default mode uses the already-published team-season master CSV so the
workbook and reported findings reproduce the existing analysis exactly.

A raw-data rebuild mode is also included. It reads the four pressure XLSX
files directly (without pandas/openpyxl), joins the four FTN season-outcome
CSVs, and reconstructs the team-season table using the documented Layer 1
logic. Use ``--rebuild-master`` to run that path.

Example
-------
python build_layer1_pressure_analysis.py \
    --data-dir /mnt/data \
    --output-dir /mnt/data

Raw rebuild:
python build_layer1_pressure_analysis.py \
    --data-dir /mnt/data \
    --output-dir /mnt/data \
    --rebuild-master

Dependencies
------------
Python standard library, numpy, scipy, statsmodels, openpyxl.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence, Tuple
from xml.etree import ElementTree as ET

import numpy as np
from scipy.stats import pearsonr, rankdata, spearmanr
import statsmodels.api as sm



# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEASONS = (2022, 2023, 2024, 2025)

PRESSURE_FILES = {
    2022: "2022 Pressure for Shaan Donohue(1).xlsx",
    2023: "2023 Pressure for Shaan Donohue(1).xlsx",
    2024: "2024 Pressure for Shaan Donohue(1).xlsx",
    2025: "2025 Pressure for Shaan Donohue(1).xlsx",
}

OUTCOME_FILES = {
    2022: "NFL Stats - Advanced NFL Statistics (30).csv",
    2023: "NFL Stats - Advanced NFL Statistics (29).csv",
    2024: "NFL Stats - Advanced NFL Statistics (28).csv",
    2025: "NFL Stats - Advanced NFL Statistics (27).csv",
}

TEAM_MAP = {
    "ARZ": "ARI",
    "BLT": "BAL",
    "CLV": "CLE",
    "HST": "HOU",
    "LA": "LAR",
}

MASTER_COLUMNS = [
    "season", "team", "dropbacks", "pressures", "pressure_rate",
    "pressure_z", "pressure_pct", "pressure_quintile", "pressure_quartile",
    "rush_3_or_less_db", "rush_3_or_less_usage", "rush_3_or_less_pressure_rate",
    "rush_4_db", "rush_4_usage", "rush_4_pressure_rate",
    "four_man_pressure_z", "four_man_pressure_pct",
    "rush_5_plus_db", "rush_5_plus_usage", "rush_5_plus_pressure_rate",
    "five_plus_pressure_z", "five_plus_pressure_pct",
    "rush_6_plus_db", "rush_6_plus_usage", "rush_6_plus_pressure_rate",
    "blitz_dependency", "avg_rushers", "avg_blockers",
    "sacks", "sack_rate", "pressure_to_sack", "scrambles",
    "epa_db", "epa_quality_z", "epa_quality_pct",
    "success_rate_allowed", "success_quality_z", "success_quality_pct",
    "explosive_rate_allowed", "explosive_quality_z", "explosive_quality_pct",
    "dvoa", "dvoa_quality_z", "dvoa_quality_pct",
    "pass_defense_composite", "pass_defense_composite_pct",
    "above_avg_pass_defense", "top_quartile_pass_defense", "top_10_pass_defense",
]


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def safe_int(value: Any) -> int | None:
    number = safe_float(value)
    return None if number is None else int(number)


def mean(values: Sequence[float]) -> float:
    return float(sum(values) / len(values)) if values else float("nan")


def population_z(values: Sequence[float]) -> List[float]:
    arr = np.asarray(values, dtype=float)
    mu = float(arr.mean())
    sd = float(arr.std(ddof=0))
    if sd == 0:
        return [0.0] * len(arr)
    return [float((x - mu) / sd) for x in arr]


def percentile_rank(values: Sequence[float]) -> List[float]:
    """Excel/Pandas-style percentile rank: (average_rank - 1)/(n - 1)."""
    arr = np.asarray(values, dtype=float)
    if len(arr) <= 1:
        return [1.0] * len(arr)
    ranks = rankdata(arr, method="average")
    return [float((r - 1.0) / (len(arr) - 1.0)) for r in ranks]


def rank_bucket(values: Sequence[float], buckets: int) -> List[int]:
    """Assign equal-count rank buckets from low (1) to high (buckets)."""
    arr = np.asarray(values, dtype=float)
    order = np.argsort(arr, kind="mergesort")
    out = np.zeros(len(arr), dtype=int)
    for position, index in enumerate(order):
        out[index] = min(buckets, int(position * buckets / len(arr)) + 1)
    return [int(x) for x in out]


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def read_master_csv(path: Path) -> List[Dict[str, Any]]:
    numeric = set(MASTER_COLUMNS) - {"team"}
    integer_fields = {
        "season", "pressure_quintile", "pressure_quartile",
        "above_avg_pass_defense", "top_quartile_pass_defense", "top_10_pass_defense",
    }
    rows: List[Dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for raw in csv.DictReader(handle):
            row: Dict[str, Any] = dict(raw)
            for key in numeric:
                if key not in row or row[key] == "":
                    row[key] = None
                elif key in integer_fields:
                    row[key] = int(float(row[key]))
                else:
                    row[key] = float(row[key])
            rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Minimal XLSX reader for the pressure files
# ---------------------------------------------------------------------------

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
NS = {"a": MAIN_NS, "r": REL_NS, "pr": PKG_REL_NS}


def column_index(reference: str) -> int:
    letters = re.match(r"([A-Z]+)", reference)
    if not letters:
        raise ValueError(f"Invalid cell reference: {reference}")
    result = 0
    for char in letters.group(1):
        result = result * 26 + ord(char) - 64
    return result - 1


def read_pressure_xlsx(path: Path) -> List[Dict[str, Any]]:
    """Read the first worksheet from an XLSX file with only stdlib XML tools."""
    with zipfile.ZipFile(path) as archive:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in root.findall("a:si", NS):
                pieces = [node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")]
                shared_strings.append("".join(pieces))

        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root}

        first_sheet = workbook_root.find("a:sheets", NS)[0]
        rel_id = first_sheet.attrib[f"{{{REL_NS}}}id"]
        target = relationships[rel_id]
        if target.startswith("/"):
            target = target.lstrip("/")
        elif not target.startswith("xl/"):
            target = f"xl/{target}"
        target = os.path.normpath(target)

        sheet_root = ET.fromstring(archive.read(target))
        sparse_rows: List[Dict[int, Any]] = []
        maximum_column = 0

        for row_node in sheet_root.findall(".//a:sheetData/a:row", NS):
            row_values: Dict[int, Any] = {}
            for cell in row_node.findall("a:c", NS):
                index = column_index(cell.attrib["r"])
                maximum_column = max(maximum_column, index)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("a:v", NS)
                value: Any = None

                if cell_type == "inlineStr":
                    value = "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
                elif value_node is not None:
                    raw_value = value_node.text or ""
                    if cell_type == "s":
                        value = shared_strings[int(raw_value)]
                    elif cell_type == "b":
                        value = raw_value == "1"
                    else:
                        try:
                            numeric = float(raw_value)
                            value = int(numeric) if numeric.is_integer() else numeric
                        except ValueError:
                            value = raw_value
                row_values[index] = value
            sparse_rows.append(row_values)

    dense_rows: List[List[Any]] = []
    for sparse in sparse_rows:
        row = [None] * (maximum_column + 1)
        for index, value in sparse.items():
            row[index] = value
        dense_rows.append(row)

    header_index = next(
        i for i, row in enumerate(dense_rows)
        if "YEAR" in row and "DEFENSE" in row and "RUSH" in row
    )
    headers = [str(value).strip() if value is not None else "" for value in dense_rows[header_index]]

    records: List[Dict[str, Any]] = []
    for row in dense_rows[header_index + 1:]:
        if not any(value not in (None, "") for value in row):
            continue
        record = {
            headers[index]: row[index]
            for index in range(min(len(headers), len(row)))
            if headers[index]
        }
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Raw team-season master construction
# ---------------------------------------------------------------------------

def read_outcome_csv(path: Path) -> Dict[str, Dict[str, float]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.reader(handle))
    headers = rows[1]
    results: Dict[str, Dict[str, float]] = {}
    for values in rows[2:]:
        if len(values) < 2 or not values[1]:
            continue
        row = {headers[i]: values[i] for i in range(min(len(headers), len(values)))}
        team = TEAM_MAP.get(row["Tm"], row["Tm"])
        results[team] = {
            "epa_db": float(safe_float(row["EPA/DB"])),
            "success_rate_allowed": float(safe_float(row["SUC%"])) / 100.0,
            "explosive_rate_allowed": float(safe_float(row["EXP%"])) / 100.0,
            "dvoa": float(safe_float(row["DVOA"])),
        }
    return results


def build_pressure_team_seasons(season: int, records: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    pressure_field = "PRESSURE Y/N" if season == 2022 else "QBP"
    counts: Dict[str, Counter] = defaultdict(Counter)
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for record in records:
        team = str(record.get("DEFENSE", "")).strip()
        rushers = safe_int(record.get("RUSH"))
        blockers = safe_int(record.get("BLOCK"))
        if not team or rushers is None or blockers is None:
            continue

        pressured = 1 if safe_int(record.get(pressure_field)) == 1 else 0
        description = str(record.get("DESCRIPTION") or "").lower()
        scrambled = 1 if str(record.get("PLTYPE") or "").lower() == "rushed" else 0
        sack = 1 if "sacked" in description else 0

        counter = counts[team]
        counter["dropbacks"] += 1
        counter["pressures"] += pressured
        counter["sacks"] += sack
        counter["scrambles"] += scrambled
        totals[team]["rushers"] += rushers
        totals[team]["blockers"] += blockers

        if rushers <= 3:
            counter["rush_3_or_less_db"] += 1
            counter["rush_3_or_less_pressures"] += pressured
        if rushers == 4:
            counter["rush_4_db"] += 1
            counter["rush_4_pressures"] += pressured
        if rushers >= 5:
            counter["rush_5_plus_db"] += 1
            counter["rush_5_plus_pressures"] += pressured
        if rushers >= 6:
            counter["rush_6_plus_db"] += 1
            counter["rush_6_plus_pressures"] += pressured

    output: List[Dict[str, Any]] = []
    for team in sorted(counts):
        c = counts[team]
        dropbacks = c["dropbacks"]
        pressures = c["pressures"]
        r3 = c["rush_3_or_less_db"]
        r4 = c["rush_4_db"]
        r5 = c["rush_5_plus_db"]
        r6 = c["rush_6_plus_db"]

        output.append({
            "season": season,
            "team": team,
            "dropbacks": float(dropbacks),
            "pressures": float(pressures),
            "pressure_rate": pressures / dropbacks,
            "rush_3_or_less_db": float(r3),
            "rush_3_or_less_usage": r3 / dropbacks,
            "rush_3_or_less_pressure_rate": c["rush_3_or_less_pressures"] / r3 if r3 else None,
            "rush_4_db": float(r4),
            "rush_4_usage": r4 / dropbacks,
            "rush_4_pressure_rate": c["rush_4_pressures"] / r4 if r4 else None,
            "rush_5_plus_db": float(r5),
            "rush_5_plus_usage": r5 / dropbacks,
            "rush_5_plus_pressure_rate": c["rush_5_plus_pressures"] / r5 if r5 else None,
            "rush_6_plus_db": float(r6),
            "rush_6_plus_usage": r6 / dropbacks,
            "rush_6_plus_pressure_rate": c["rush_6_plus_pressures"] / r6 if r6 else None,
            "blitz_dependency": c["rush_5_plus_pressures"] / pressures if pressures else None,
            "avg_rushers": totals[team]["rushers"] / dropbacks,
            "avg_blockers": totals[team]["blockers"] / dropbacks,
            "sacks": float(c["sacks"]),
            "sack_rate": c["sacks"] / dropbacks,
            "pressure_to_sack": c["sacks"] / pressures if pressures else None,
            "scrambles": float(c["scrambles"]),
        })
    return output


def add_season_normalization(rows: List[Dict[str, Any]]) -> None:
    for season in SEASONS:
        season_rows = [row for row in rows if int(row["season"]) == season]

        def attach(source: str, z_name: str, pct_name: str, reverse: bool = False) -> None:
            values = [float(row[source]) for row in season_rows]
            oriented = [-value for value in values] if reverse else values
            z_values = population_z(oriented)
            percentiles = percentile_rank(oriented)
            for row, z_value, percentile in zip(season_rows, z_values, percentiles):
                row[z_name] = z_value
                row[pct_name] = percentile

        attach("pressure_rate", "pressure_z", "pressure_pct")
        attach("rush_4_pressure_rate", "four_man_pressure_z", "four_man_pressure_pct")
        attach("rush_5_plus_pressure_rate", "five_plus_pressure_z", "five_plus_pressure_pct")
        attach("epa_db", "epa_quality_z", "epa_quality_pct", reverse=True)
        attach("success_rate_allowed", "success_quality_z", "success_quality_pct", reverse=True)
        attach("explosive_rate_allowed", "explosive_quality_z", "explosive_quality_pct", reverse=True)
        attach("dvoa", "dvoa_quality_z", "dvoa_quality_pct", reverse=True)

        pressure_values = [float(row["pressure_rate"]) for row in season_rows]
        quintiles = rank_bucket(pressure_values, 5)
        quartiles = rank_bucket(pressure_values, 4)
        for row, quintile, quartile in zip(season_rows, quintiles, quartiles):
            row["pressure_quintile"] = quintile
            row["pressure_quartile"] = quartile
            row["pass_defense_composite"] = mean([
                float(row["epa_quality_z"]),
                float(row["success_quality_z"]),
                float(row["explosive_quality_z"]),
            ])

        composites = [float(row["pass_defense_composite"]) for row in season_rows]
        composite_pct = percentile_rank(composites)
        descending_order = sorted(range(len(season_rows)), key=lambda i: composites[i], reverse=True)
        top_ten_indices = set(descending_order[:10])
        for index, (row, percentile) in enumerate(zip(season_rows, composite_pct)):
            row["pass_defense_composite_pct"] = percentile
            row["above_avg_pass_defense"] = int(row["pass_defense_composite"] > 0)
            row["top_quartile_pass_defense"] = int(percentile >= 0.75)
            row["top_10_pass_defense"] = int(index in top_ten_indices)


def build_master_from_raw(data_dir: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for season in SEASONS:
        pressure_path = data_dir / PRESSURE_FILES[season]
        if not pressure_path.exists():
            fallback = data_dir / f"{season} Pressure for Shaan Donohue.xlsx"
            pressure_path = fallback if fallback.exists() else pressure_path
        records = read_pressure_xlsx(pressure_path)
        outcomes = read_outcome_csv(data_dir / OUTCOME_FILES[season])
        for row in build_pressure_team_seasons(season, records):
            if row["team"] not in outcomes:
                raise KeyError(f"No outcome row for {season} {row['team']}")
            row.update(outcomes[row["team"]])
            rows.append(row)

    add_season_normalization(rows)
    rows.sort(key=lambda row: (int(row["season"]), str(row["team"])))
    return rows


# ---------------------------------------------------------------------------
# Analysis summaries
# ---------------------------------------------------------------------------

def correlation_rows(master: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    pairs = [
        ("Pressure rate", "pressure_z", "EPA quality", "epa_quality_z"),
        ("Pressure rate", "pressure_z", "Success quality", "success_quality_z"),
        ("Pressure rate", "pressure_z", "Explosive prevention", "explosive_quality_z"),
        ("Pressure rate", "pressure_z", "Pass-defense composite", "pass_defense_composite"),
        ("Four-man pressure", "four_man_pressure_z", "EPA quality", "epa_quality_z"),
        ("Five-plus pressure", "five_plus_pressure_z", "EPA quality", "epa_quality_z"),
        ("Five-plus usage", "rush_5_plus_usage", "EPA quality", "epa_quality_z"),
        ("Pressure rate", "pressure_z", "DVOA quality", "dvoa_quality_z"),
    ]
    output = []
    for predictor_label, predictor, outcome_label, outcome in pairs:
        x = np.asarray([float(row[predictor]) for row in master], dtype=float)
        y = np.asarray([float(row[outcome]) for row in master], dtype=float)
        p = pearsonr(x, y)
        s = spearmanr(x, y)
        output.append({
            "predictor": predictor_label,
            "outcome": outcome_label,
            "pearson_r": float(p.statistic),
            "pearson_p": float(p.pvalue),
            "spearman_rho": float(s.statistic),
            "spearman_p": float(s.pvalue),
        })
    return output


def fit_ols(master: Sequence[Mapping[str, Any]], outcome: str, predictors: Sequence[str], label: str) -> Dict[str, Any]:
    y = np.asarray([float(row[outcome]) for row in master], dtype=float)
    x = np.asarray([[float(row[p]) for p in predictors] for row in master], dtype=float)
    x = sm.add_constant(x)
    model = sm.OLS(y, x).fit(cov_type="HC3")
    result: Dict[str, Any] = {
        "model": label,
        "outcome": outcome,
        "n": int(model.nobs),
        "r_squared": float(model.rsquared),
        "adj_r_squared": float(model.rsquared_adj),
    }
    names = ["intercept", *predictors]
    for name, coef, pvalue in zip(names, model.params, model.pvalues):
        result[f"coef_{name}"] = float(coef)
        result[f"p_{name}"] = float(pvalue)
    return result


def model_rows(master: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = [
        fit_ols(master, "epa_quality_z", ["pressure_z"], "EPA quality ~ overall pressure"),
        fit_ols(master, "success_quality_z", ["pressure_z"], "Success quality ~ overall pressure"),
        fit_ols(master, "explosive_quality_z", ["pressure_z"], "Explosive prevention ~ overall pressure"),
        fit_ols(master, "pass_defense_composite", ["pressure_z"], "Composite ~ overall pressure"),
        fit_ols(
            master,
            "epa_quality_z",
            ["four_man_pressure_z", "five_plus_pressure_z", "rush_5_plus_usage"],
            "EPA quality ~ four-man + five-plus efficiency + five-plus usage",
        ),
    ]

    y = np.asarray([int(row["top_quartile_pass_defense"]) for row in master], dtype=float)
    x = sm.add_constant(np.asarray([float(row["pressure_z"]) for row in master], dtype=float))
    logistic = sm.Logit(y, x).fit(disp=False)
    output.append({
        "model": "Top-quartile defense ~ overall pressure (logit)",
        "outcome": "top_quartile_pass_defense",
        "n": int(logistic.nobs),
        "r_squared": float(logistic.prsquared),
        "adj_r_squared": None,
        "coef_intercept": float(logistic.params[0]),
        "p_intercept": float(logistic.pvalues[0]),
        "coef_pressure_z": float(logistic.params[1]),
        "p_pressure_z": float(logistic.pvalues[1]),
        "odds_ratio_pressure_z": float(math.exp(logistic.params[1])),
    })
    return output


def grouped_pressure_summary(master: Sequence[Mapping[str, Any]], field: str) -> List[Dict[str, Any]]:
    groups: Dict[int, List[Mapping[str, Any]]] = defaultdict(list)
    for row in master:
        groups[int(row[field])].append(row)
    output = []
    for group in sorted(groups):
        rows = groups[group]
        output.append({
            field: group,
            "team_seasons": len(rows),
            "avg_pressure_rate": mean([float(row["pressure_rate"]) for row in rows]),
            "avg_epa_db": mean([float(row["epa_db"]) for row in rows]),
            "avg_success_rate_allowed": mean([float(row["success_rate_allowed"]) for row in rows]),
            "avg_explosive_rate_allowed": mean([float(row["explosive_rate_allowed"]) for row in rows]),
            "avg_pass_defense_composite": mean([float(row["pass_defense_composite"]) for row in rows]),
            "above_avg_rate": mean([int(row["above_avg_pass_defense"]) for row in rows]),
            "top_quartile_rate": mean([int(row["top_quartile_pass_defense"]) for row in rows]),
            "top_10_rate": mean([int(row["top_10_pass_defense"]) for row in rows]),
        })
    return output


def threshold_summary(master: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for threshold in (0.25, 0.40, 0.50, 0.60, 0.70, 0.75):
        rows = [row for row in master if float(row["pressure_pct"]) >= threshold]
        output.append({
            "pressure_percentile_threshold": threshold,
            "team_seasons": len(rows),
            "minimum_raw_pressure_rate": min(float(row["pressure_rate"]) for row in rows),
            "average_raw_pressure_rate": mean([float(row["pressure_rate"]) for row in rows]),
            "above_avg_rate": mean([int(row["above_avg_pass_defense"]) for row in rows]),
            "top_quartile_rate": mean([int(row["top_quartile_pass_defense"]) for row in rows]),
            "top_10_rate": mean([int(row["top_10_pass_defense"]) for row in rows]),
        })
    return output


def leave_one_season_out(master: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for omitted in SEASONS:
        rows = [row for row in master if int(row["season"]) != omitted]
        x = np.asarray([float(row["pressure_z"]) for row in rows], dtype=float)
        for outcome in ("epa_quality_z", "success_quality_z", "explosive_quality_z", "pass_defense_composite"):
            y = np.asarray([float(row[outcome]) for row in rows], dtype=float)
            output.append({
                "omitted_season": omitted,
                "outcome": outcome,
                "n": len(rows),
                "pearson_r": float(pearsonr(x, y).statistic),
                "spearman_rho": float(spearmanr(x, y).statistic),
            })
    return output


def season_environment(master: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    output = []
    for season in SEASONS:
        rows = [row for row in master if int(row["season"]) == season]
        output.append({
            "season": season,
            "team_seasons": len(rows),
            "dropbacks": int(sum(float(row["dropbacks"]) for row in rows)),
            "league_pressure_rate": mean([float(row["pressure_rate"]) for row in rows]),
            "league_four_man_pressure_rate": mean([float(row["rush_4_pressure_rate"]) for row in rows]),
            "league_five_plus_pressure_rate": mean([float(row["rush_5_plus_pressure_rate"]) for row in rows]),
            "league_epa_db_allowed": mean([float(row["epa_db"]) for row in rows]),
            "league_success_rate_allowed": mean([float(row["success_rate_allowed"]) for row in rows]),
            "league_explosive_rate_allowed": mean([float(row["explosive_rate_allowed"]) for row in rows]),
        })
    return output


def findings(master: Sequence[Mapping[str, Any]], correlations: Sequence[Mapping[str, Any]], models: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    lookup = {(row["predictor"], row["outcome"]): row for row in correlations}
    quartiles = grouped_pressure_summary(master, "pressure_quartile")
    q1, q4 = quartiles[0], quartiles[-1]
    logit = next(row for row in models if "logit" in row["model"])
    return {
        "n_team_seasons": len(master),
        "n_dropbacks": int(sum(float(row["dropbacks"]) for row in master)),
        "pressure_epa_pearson": lookup[("Pressure rate", "EPA quality")]["pearson_r"],
        "pressure_success_pearson": lookup[("Pressure rate", "Success quality")]["pearson_r"],
        "pressure_explosive_pearson": lookup[("Pressure rate", "Explosive prevention")]["pearson_r"],
        "pressure_sd_odds_top_quartile": logit["odds_ratio_pressure_z"],
        "top_quartile_above_avg_rate": q4["above_avg_rate"],
        "bottom_quartile_above_avg_rate": q1["above_avg_rate"],
        "top_quartile_top_quartile_rate": q4["top_quartile_rate"],
        "bottom_quartile_top_quartile_rate": q1["top_quartile_rate"],
    }


# ---------------------------------------------------------------------------
# Workbook creation (local/openpyxl version)
# ---------------------------------------------------------------------------

from openpyxl import Workbook as OpenpyxlWorkbook
from openpyxl.chart import BarChart, Reference
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


def excel_column(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def rectangular(rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> List[List[Any]]:
    return [[row.get(column) for column in columns] for row in rows]


def _write_matrix(ws: Any, start_row: int, start_col: int, matrix: Sequence[Sequence[Any]]) -> None:
    for r_offset, row in enumerate(matrix):
        for c_offset, value in enumerate(row):
            ws.cell(start_row + r_offset, start_col + c_offset, value=value)


def _merge_title(ws: Any, cell_range: str, value: str, fill: str, font_color: str, size: int) -> None:
    ws.merge_cells(cell_range)
    cell = ws[cell_range.split(":")[0]]
    cell.value = value
    cell.fill = PatternFill("solid", fgColor=fill.replace("#", ""))
    cell.font = Font(bold=True, color=font_color.replace("#", ""), size=size)
    cell.alignment = Alignment(vertical="center")


def _style_header(ws: Any, row: int, start_col: int, end_col: int, fill: str, font_color: str) -> None:
    for col in range(start_col, end_col + 1):
        cell = ws.cell(row, col)
        cell.fill = PatternFill("solid", fgColor=fill.replace("#", ""))
        cell.font = Font(bold=True, color=font_color.replace("#", ""))
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _style_section(ws: Any, row: int, start_col: int, end_col: int, title: str, fill: str, font_color: str) -> None:
    ws.merge_cells(start_row=row, start_column=start_col, end_row=row, end_column=end_col)
    cell = ws.cell(row, start_col, title)
    cell.fill = PatternFill("solid", fgColor=fill.replace("#", ""))
    cell.font = Font(bold=True, color=font_color.replace("#", ""), size=12)
    cell.alignment = Alignment(vertical="center")


def _write_section(
    ws: Any,
    title: str,
    start_row: int,
    rows: Sequence[Mapping[str, Any]],
    section_fill: str,
    header_fill: str,
    white: str,
) -> int:
    columns = list(rows[0].keys())
    _style_section(ws, start_row, 1, len(columns), title, section_fill, white)
    matrix = [columns] + rectangular(rows, columns)
    _write_matrix(ws, start_row + 1, 1, matrix)
    _style_header(ws, start_row + 1, 1, len(columns), header_fill, white)
    return start_row + len(matrix) + 2


def create_workbook(
    master: Sequence[Mapping[str, Any]],
    correlations: Sequence[Mapping[str, Any]],
    models: Sequence[Mapping[str, Any]],
    quintiles: Sequence[Mapping[str, Any]],
    quartiles: Sequence[Mapping[str, Any]],
    thresholds: Sequence[Mapping[str, Any]],
    loso: Sequence[Mapping[str, Any]],
    seasons: Sequence[Mapping[str, Any]],
    result_findings: Mapping[str, Any],
    output_path: Path,
) -> None:
    wb = OpenpyxlWorkbook()
    dashboard = wb.active
    dashboard.title = "Dashboard"
    master_sheet = wb.create_sheet("Team Season Master")
    bands_sheet = wb.create_sheet("Pressure Bands")
    models_sheet = wb.create_sheet("Models and Correlations")
    robust_sheet = wb.create_sheet("Robustness")
    method_sheet = wb.create_sheet("Methodology")

    navy = "#17324D"
    blue = "#2F6B9A"
    light_blue = "#DCEAF5"
    green = "#DCEFE7"
    light_gold = "#F5EBCB"
    light_red = "#F5DEDE"
    gray = "#5F6B75"
    light_gray = "#EEF2F5"
    white = "#FFFFFF"
    dark = "#1F2933"

    # Dashboard
    _merge_title(dashboard, "A1:K2", "Layer 1: How Much Pressure Does a Defense Need?", navy, white, 18)
    dashboard.merge_cells("A3:K3")
    dashboard["A3"] = "2022–2025 team-season analysis. Higher standardized quality values mean better defense."
    dashboard["A3"].fill = PatternFill("solid", fgColor=light_blue.replace("#", ""))
    dashboard["A3"].font = Font(italic=True, color=dark.replace("#", ""))
    dashboard["A3"].alignment = Alignment(vertical="center")

    kpis = [
        ("Team-seasons", result_findings["n_team_seasons"], "Complete 32-team panel", "0"),
        ("Defensive dropbacks", result_findings["n_dropbacks"], "Pressure-sheet opportunities", "#,##0"),
        ("Pressure vs EPA quality", result_findings["pressure_epa_pearson"], "Pearson r", "0.000"),
        ("Top-defense odds", result_findings["pressure_sd_odds_top_quartile"], "Odds per +1 SD pressure", "0.00x"),
    ]
    start_columns = [1, 4, 7, 10]
    for (label, value, note, number_format), start_col in zip(kpis, start_columns):
        end_col = start_col + 1
        dashboard.merge_cells(start_row=5, start_column=start_col, end_row=5, end_column=end_col)
        dashboard.merge_cells(start_row=6, start_column=start_col, end_row=7, end_column=end_col)
        dashboard.merge_cells(start_row=8, start_column=start_col, end_row=8, end_column=end_col)
        header = dashboard.cell(5, start_col, label)
        header.fill = PatternFill("solid", fgColor=blue.replace("#", ""))
        header.font = Font(bold=True, color=white.replace("#", ""))
        header.alignment = Alignment(horizontal="center", vertical="center")
        value_cell = dashboard.cell(6, start_col, value)
        value_cell.fill = PatternFill("solid", fgColor=light_blue.replace("#", ""))
        value_cell.font = Font(bold=True, color=navy.replace("#", ""), size=18)
        value_cell.alignment = Alignment(horizontal="center", vertical="center")
        value_cell.number_format = number_format
        note_cell = dashboard.cell(8, start_col, note)
        note_cell.fill = PatternFill("solid", fgColor=light_gray.replace("#", ""))
        note_cell.font = Font(italic=True, color=gray.replace("#", ""))
        note_cell.alignment = Alignment(horizontal="center", vertical="center")

    _style_section(dashboard, 10, 1, 11, "First-pass findings", blue, white)
    finding_table = [
        ["Signal", "Result", "Interpretation"],
        ["Overall pressure", f"r = {result_findings['pressure_epa_pearson']:.3f}",
         "Pressure has a strong and stable relationship with season-long EPA/dropback quality."],
        ["Down-to-down consistency", f"r = {result_findings['pressure_success_pearson']:.3f}",
         "Pressure is also associated with a lower offensive success rate."],
        ["Explosive prevention", f"r = {result_findings['pressure_explosive_pearson']:.3f}",
         "Pressure alone does not meaningfully explain explosive-pass prevention."],
        ["Pressure floor", "No clean breakpoint",
         "The first pass supports a probability gradient rather than one universal minimum cutoff."],
        ["Top pressure quartile", f"{result_findings['top_quartile_above_avg_rate']:.1%} above average",
         f"Only {result_findings['bottom_quartile_above_avg_rate']:.1%} of bottom-quartile pressure teams were above average."],
        ["High-end defense", f"{result_findings['top_quartile_top_quartile_rate']:.1%} top quartile",
         f"Bottom-quartile pressure teams reached the top defensive quartile only {result_findings['bottom_quartile_top_quartile_rate']:.1%} of the time."],
        ["How pressure comes", "Four-man and 5+ efficiency matter",
         "Efficiency at both rusher counts carries signal; simply sending five or more more often does not."],
    ]
    _write_matrix(dashboard, 11, 1, finding_table)
    _style_header(dashboard, 11, 1, 3, navy, white)
    for row in range(12, 19):
        for col in range(1, 4):
            dashboard.cell(row, col).alignment = Alignment(vertical="top", wrap_text=True)
    dashboard.column_dimensions["A"].width = 24
    dashboard.column_dimensions["B"].width = 24
    dashboard.column_dimensions["C"].width = 60

    _style_section(dashboard, 20, 1, 5, "Pressure-quartile outcomes", blue, white)
    quartile_dashboard = [[
        "Pressure quartile", "Avg pressure rate", "Avg EPA/DB allowed",
        "Above-average defense", "Top-quartile defense",
    ]] + [[
        row["pressure_quartile"], row["avg_pressure_rate"], row["avg_epa_db"],
        row["above_avg_rate"], row["top_quartile_rate"],
    ] for row in quartiles]
    _write_matrix(dashboard, 21, 1, quartile_dashboard)
    _style_header(dashboard, 21, 1, 5, navy, white)
    for r in range(22, 26):
        dashboard.cell(r, 2).number_format = "0.0%"
        dashboard.cell(r, 3).number_format = "0.000"
        dashboard.cell(r, 4).number_format = "0.0%"
        dashboard.cell(r, 5).number_format = "0.0%"
    dashboard.conditional_formatting.add(
        "B22:E25",
        ColorScaleRule(start_type="min", start_color=light_red.replace("#", ""),
                       mid_type="percentile", mid_value=50, mid_color=light_gold.replace("#", ""),
                       end_type="max", end_color=green.replace("#", "")),
    )

    _style_section(dashboard, 28, 1, 11, "Interpretation", blue, white)
    dashboard.merge_cells("A29:K32")
    dashboard["A29"] = (
        "Layer 1 establishes pressure as a meaningful requirement, especially for EPA efficiency and down-to-down success. "
        "It does not establish one hard league-wide cutoff. Low-pressure defenses face a materially steeper path to good "
        "outcomes, while top-quartile pressure meaningfully increases the odds of a top-quartile pass defense. Layer 2 can "
        "now ask which room constructions reach that pressure range."
    )
    dashboard["A29"].fill = PatternFill("solid", fgColor=light_gold.replace("#", ""))
    dashboard["A29"].font = Font(color=dark.replace("#", ""))
    dashboard["A29"].alignment = Alignment(vertical="center", wrap_text=True)
    dashboard.freeze_panes = "A4"

    # Outcome-rate chart
    chart = BarChart()
    chart.type = "col"
    chart.style = 10
    chart.title = "Defensive Outcomes by Pressure Quartile"
    chart.y_axis.title = "Rate"
    chart.x_axis.title = "Pressure Quartile"
    data = Reference(dashboard, min_col=4, max_col=5, min_row=21, max_row=25)
    cats = Reference(dashboard, min_col=1, min_row=22, max_row=25)
    chart.add_data(data, titles_from_data=True)
    chart.set_categories(cats)
    chart.height = 8
    chart.width = 13
    dashboard.add_chart(chart, "G20")

    # Team-season master
    master_matrix = [MASTER_COLUMNS] + rectangular(master, MASTER_COLUMNS)
    _write_matrix(master_sheet, 1, 1, master_matrix)
    _style_header(master_sheet, 1, 1, len(MASTER_COLUMNS), navy, white)
    master_sheet.freeze_panes = "C2"
    master_end_col = excel_column(len(MASTER_COLUMNS))
    table = Table(displayName="TeamSeasonTable", ref=f"A1:{master_end_col}{len(master_matrix)}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showFirstColumn=False,
                                          showLastColumn=False, showRowStripes=True, showColumnStripes=False)
    master_sheet.add_table(table)
    master_sheet.column_dimensions["A"].width = 11
    master_sheet.column_dimensions["B"].width = 11
    for col in range(3, len(MASTER_COLUMNS) + 1):
        master_sheet.column_dimensions[excel_column(col)].width = 14

    header_positions = {name: index + 1 for index, name in enumerate(MASTER_COLUMNS)}
    percent_fields = {
        "pressure_rate", "pressure_pct", "rush_3_or_less_usage", "rush_3_or_less_pressure_rate",
        "rush_4_usage", "rush_4_pressure_rate", "four_man_pressure_pct",
        "rush_5_plus_usage", "rush_5_plus_pressure_rate", "five_plus_pressure_pct",
        "rush_6_plus_usage", "rush_6_plus_pressure_rate", "blitz_dependency", "sack_rate",
        "pressure_to_sack", "success_rate_allowed", "success_quality_pct",
        "explosive_rate_allowed", "explosive_quality_pct", "epa_quality_pct",
        "dvoa_quality_pct", "pass_defense_composite_pct",
    }
    for field in percent_fields:
        col = header_positions[field]
        for row in range(2, len(master_matrix) + 1):
            master_sheet.cell(row, col).number_format = "0.0%"
    for field in ("pressure_pct", "epa_quality_pct", "success_quality_pct", "explosive_quality_pct", "pass_defense_composite_pct"):
        col_letter = excel_column(header_positions[field])
        master_sheet.conditional_formatting.add(
            f"{col_letter}2:{col_letter}{len(master_matrix)}",
            ColorScaleRule(start_type="min", start_color=light_red.replace("#", ""),
                           mid_type="percentile", mid_value=50, mid_color=light_gold.replace("#", ""),
                           end_type="max", end_color=green.replace("#", "")),
        )

    # Pressure bands
    _merge_title(bands_sheet, "A1:J2", "Pressure Bands and Practical Thresholds", navy, white, 18)
    next_row = _write_section(bands_sheet, "Quintile summary", 4, quintiles, blue, navy, white)
    next_row = _write_section(bands_sheet, "Quartile summary", next_row, quartiles, blue, navy, white)
    _write_section(bands_sheet, "Candidate percentile thresholds", next_row, thresholds, blue, navy, white)
    bands_sheet.freeze_panes = "A5"
    for col in range(1, 11):
        bands_sheet.column_dimensions[excel_column(col)].width = 18

    # Models and correlations
    _merge_title(models_sheet, "A1:L2", "Models and Correlations", navy, white, 18)
    next_row = _write_section(models_sheet, "Correlation matrix", 4, correlations, blue, navy, white)
    _write_section(models_sheet, "Regression summaries", next_row, models, blue, navy, white)
    models_sheet.freeze_panes = "A5"
    for col in range(1, 13):
        models_sheet.column_dimensions[excel_column(col)].width = 18

    # Robustness
    _merge_title(robust_sheet, "A1:I2", "Robustness and Season Environment", navy, white, 18)
    next_row = _write_section(robust_sheet, "League environment by season", 4, seasons, blue, navy, white)
    _write_section(robust_sheet, "Leave-one-season-out correlations", next_row, loso, blue, navy, white)
    robust_sheet.freeze_panes = "A5"
    for col in range(1, 10):
        robust_sheet.column_dimensions[excel_column(col)].width = 20

    # Methodology
    _merge_title(method_sheet, "A1:H2", "Layer 1 Methodology and Data Dictionary", navy, white, 18)
    _style_section(method_sheet, 4, 1, 8, "Research question", blue, white)
    method_sheet.merge_cells("A5:H6")
    method_sheet["A5"] = "How much pressure does a defense need to consistently produce good season-long pass-defense outcomes?"
    method_sheet["A5"].fill = PatternFill("solid", fgColor=light_blue.replace("#", ""))
    method_sheet["A5"].font = Font(bold=True, color=dark.replace("#", ""))
    method_sheet["A5"].alignment = Alignment(vertical="center", wrap_text=True)
    methodology = [
        ["Component", "Definition / decision"],
        ["Unit of analysis", "One defense-season; 32 teams across 2022–2025 (128 rows)."],
        ["Pressure denominator", "All valid rows in the pressure sheets with a defense, rusher count, and blocker count."],
        ["Team pressure event", "Binary play-level event. Multiple credited defenders still count as one team pressure."],
        ["Overall pressure rate", "Pressured defensive pass plays divided by eligible defensive pass plays."],
        ["Four-man pressure rate", "Pressures on exactly four-rusher plays divided by exactly four-rusher opportunities."],
        ["Five-plus pressure rate", "Pressures on plays with five or more rushers divided by five-plus opportunities."],
        ["Primary outcome", "Season-long EPA allowed per dropback; lower raw values are better."],
        ["Validation outcomes", "Offensive success rate allowed and explosive-pass rate allowed per attempt."],
        ["Opponent-adjusted check", "Pass-defense DVOA is retained as a robustness outcome."],
        ["Cross-season normalization", "Pressure and outcomes are standardized and ranked within season before pooled modeling."],
        ["Pass-defense composite", "Equal-weight mean of season-standardized EPA, success, and explosive prevention."],
        ["Threshold interpretation", "Practical bands and probabilities are reported; a hard cutoff is not forced."],
        ["Layer boundary", "Player concentration, star gravity, room depth, cap allocation, and draft capital belong to Layers 2 and 3."],
    ]
    _write_matrix(method_sheet, 8, 1, methodology)
    _style_header(method_sheet, 8, 1, 2, navy, white)
    for row in range(9, 8 + len(methodology)):
        for col in range(1, 3):
            method_sheet.cell(row, col).alignment = Alignment(vertical="top", wrap_text=True)
    method_sheet.column_dimensions["A"].width = 28
    method_sheet.column_dimensions["B"].width = 85
    method_sheet.freeze_panes = "A5"

    # General font and row height cleanup.
    for ws in wb.worksheets:
        ws.sheet_view.showGridLines = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value is not None and cell.font.name is None:
                    cell.font = Font(name="Aptos", size=10, bold=cell.font.bold,
                                     italic=cell.font.italic, color=cell.font.color)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("/mnt/data"))
    parser.add_argument("--output-dir", type=Path, default=Path("/mnt/data"))
    parser.add_argument(
        "--source-master",
        type=Path,
        default=None,
        help="Use a prebuilt team-season master. Defaults to <data-dir>/Layer_1_Team_Season_Master.csv.",
    )
    parser.add_argument(
        "--rebuild-master",
        action="store_true",
        help="Rebuild the team-season master from the raw pressure and season-outcome files.",
    )
    parser.add_argument(
        "--workbook-name",
        default="Layer_1_Pressure_Threshold_Analysis.xlsx",
    )
    parser.add_argument(
        "--master-name",
        default="Layer_1_Team_Season_Master.csv",
    )
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    master_output = args.output_dir / args.master_name
    workbook_output = args.output_dir / args.workbook_name

    source_master = args.source_master or (args.data_dir / "Layer_1_Team_Season_Master.csv")
    if args.rebuild_master:
        master = build_master_from_raw(args.data_dir)
        write_csv(master_output, master, MASTER_COLUMNS)
    else:
        if not source_master.exists():
            raise FileNotFoundError(
                f"Published master not found at {source_master}. Use --rebuild-master to construct it from raw data."
            )
        master = read_master_csv(source_master)
        if source_master.resolve() != master_output.resolve():
            write_csv(master_output, master, MASTER_COLUMNS)

    correlations = correlation_rows(master)
    models = model_rows(master)
    quintiles = grouped_pressure_summary(master, "pressure_quintile")
    quartiles = grouped_pressure_summary(master, "pressure_quartile")
    thresholds = threshold_summary(master)
    loso = leave_one_season_out(master)
    seasons = season_environment(master)
    result_findings = findings(master, correlations, models)

    create_workbook(
        master=master,
        correlations=correlations,
        models=models,
        quintiles=quintiles,
        quartiles=quartiles,
        thresholds=thresholds,
        loso=loso,
        seasons=seasons,
        result_findings=result_findings,
        output_path=workbook_output,
    )

    print(json.dumps({
        "master_csv": str(master_output),
        "workbook": str(workbook_output),
        "team_seasons": len(master),
        "dropbacks": result_findings["n_dropbacks"],
        "pressure_epa_pearson": result_findings["pressure_epa_pearson"],
        "pressure_success_pearson": result_findings["pressure_success_pearson"],
        "pressure_explosive_pearson": result_findings["pressure_explosive_pearson"],
        "pressure_sd_odds_top_quartile": result_findings["pressure_sd_odds_top_quartile"],
    }, indent=2))


if __name__ == "__main__":
    main()
