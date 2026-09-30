#!/usr/bin/env python3
"""
Build Layer 3: pass-rush resource investment, allocation, and efficiency.

This layer joins:
1. Frozen Layer 2 player-room and team-room files
2. Spotrac player cap hits
3. NFL draft classes (2018-2025)
4. Public draft-pick value curves from the nfldata repository

Primary design
--------------
- Cap investment is measured as room cap hit divided by the league salary cap.
- Because the supplied Spotrac file does not match every modeled player,
  both observed and rush-share coverage-adjusted cap investment are retained.
- Draft investment counts only homegrown players during active rookie control.
- Primary rookie-control definition: contract years 1-4.
- Fifth-year option treatment is retained as a sensitivity for first-rounders.
- Draft capital is annualized across the relevant control window.
- Primary draft curve: Fitzgerald-Spielberger/OTC.
- Primary Resource Investment Index:
      50% season-standardized cap investment
    + 50% season-standardized active draft investment
  The combined score is re-standardized within season.
- Allocation/concentration metrics remain separate from total investment.
- Primary inferential models require at least 80% cap coverage by rush share.

Outputs
-------
Layer_3_Player_Resource_Bridge.csv
Layer_3_Team_Resource_Master.csv
Layer_3_Archetype_Resource_Summary.csv
Layer_3_Resource_Models.csv
Layer_3_Resource_Sensitivity.csv
Layer_3_Identity_Audit.csv
Layer_3_Findings.json
Layer_3_Methodology.md
Four PNG graphics
"""

from __future__ import annotations

import argparse
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None


DRAFT_VALUE_URL = (
    "https://raw.githubusercontent.com/leesharpe/nfldata/"
    "master/data/draft_values.csv"
)

SALARY_CAP = {
    2022: 208_200_000.0,
    2023: 224_800_000.0,
    2024: 255_400_000.0,
    2025: 279_200_000.0,
}

TEAM_MAP = {
    "GNB": "GB",
    "KAN": "KC",
    "LVR": "LV",
    "NWE": "NE",
    "NOR": "NO",
    "SFO": "SF",
    "TAM": "TB",
    "JAC": "JAX",
    "LA": "LAR",
    "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV",
}

ROOM_ARCHETYPE_ORDER = [
    "Star + Depth",
    "Distributed Rotation",
    "Heliocentric Star",
    "Thin / Mixed",
]

CAP_COVERAGE_MODEL_THRESHOLD = 0.80
FUZZY_CAP_THRESHOLD = 92
FUZZY_DRAFT_THRESHOLD = 94
FUZZY_MARGIN = 5

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Canonical identity aliases. These are identity bridges, not subjective
# player evaluations. The map is deliberately explicit and auditable.
NAME_ALIASES = {
    "josh allen": "josh hines allen",
    "joshua hines allen": "josh hines allen",
    "matthew judon": "matt judon",
    "michael danna": "mike danna",
    "patrick jones": "pat jones",
    "sebastian joseph": "sebastian joseph day",
    "matthew ioannidis": "matt ioannidis",
    "ogbonnia okoronkwo": "ogbo okoronkwo",
    "tedarrell slaton": "tj slaton",
    "johnny newton": "jerzhan newton",
    "carlos basham": "boogie basham",
    "foley fatukasi": "folorunso fatukasi",
    "cameron sample": "cam sample",
    "jake martin": "jacob martin",
    "jeff simmons": "jeffery simmons",
    "mike pennel": "michael pennel",
    "greg rousseau": "gregory rousseau",
    "bobby brown": "robert brown",
    "bj hill": "b j hill",
    "dj reader": "d j reader",
    "aj epenesa": "a j epenesa",
    "tj watt": "t j watt",
    "jj watt": "j j watt",
    "dj wonnum": "d j wonnum",
    "dj jones": "d j jones",
    "ojulari azeez": "azeez ojulari",
}

FRONT_DRAFT_POSITIONS = {
    "DE", "DL", "DT", "NT", "EDGE", "ED", "OLB", "LB", "ILB"
}

CAP_COMPATIBLE_POSITIONS = {
    "ED": {"ED", "LB", "DL", "DE", "OLB"},
    "DI": {"DL", "DT", "NT", "DE", "ED"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Folder containing Layer 2, cap, and draft inputs.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output folder. Defaults to data-dir/outputs/layer_3_resources.",
    )
    parser.add_argument(
        "--draft-values",
        default=None,
        help="Optional local draft_values.csv. Downloads public file if omitted.",
    )
    return parser.parse_args()


def resolve_input(data_dir: Path, candidates: list[str]) -> Path:
    for name in candidates:
        path = data_dir / name
        if path.exists():
            return path
    raise FileNotFoundError(
        "Could not find any of the required input candidates:\n"
        + "\n".join(str(data_dir / name) for name in candidates)
    )


def normalize_team(value: Any) -> str | None:
    if pd.isna(value):
        return None
    team = str(value).strip().upper()
    return TEAM_MAP.get(team, team)


def normalize_name(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    text = re.sub(r"\bunavailable\b", " ", text)
    text = text.replace("'", "")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9 ]+", " ", text)

    tokens = [token for token in text.split() if token not in SUFFIXES]

    # Merge adjacent initials: ["d", "j", "reader"] -> ["dj", "reader"].
    merged: list[str] = []
    initials: list[str] = []

    for token in tokens:
        if len(token) == 1 and token.isalpha():
            initials.append(token)
        else:
            if initials:
                merged.append("".join(initials))
                initials = []
            merged.append(token)

    if initials:
        merged.append("".join(initials))

    return " ".join(merged) if merged else None


def canonical_name(value: Any) -> str | None:
    name = normalize_name(value)
    if name is None:
        return None

    # Repeatedly apply aliases so initials and nicknames resolve.
    prior = None
    current = name

    while prior != current:
        prior = current
        current = NAME_ALIASES.get(current, current)

    return current


def parse_spotrac_name(value: Any) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    pieces = re.split(r"\s{2,}", text)

    # Spotrac export convention is "Last Name  Full Name".
    if len(pieces) >= 2:
        text = pieces[1]

    return canonical_name(text)


def last_name_token(name: str | None) -> str | None:
    if not name:
        return None
    return name.split()[-1]


def similarity(left: str, right: str) -> float:
    if fuzz is not None:
        return float(max(
            fuzz.ratio(left, right),
            fuzz.token_sort_ratio(left, right),
        ))

    # Fallback used only when rapidfuzz is unavailable.
    from difflib import SequenceMatcher
    return 100.0 * SequenceMatcher(None, left, right).ratio()


def cap_position_compatible(
    room_position: Any,
    cap_position: Any,
) -> bool:
    room_pos = str(room_position).upper()
    cap_pos = str(cap_position).upper()
    return cap_pos in CAP_COMPATIBLE_POSITIONS.get(room_pos, {cap_pos})


def draft_position_compatible(
    room_position: Any,
    draft_position: Any,
) -> bool:
    room_pos = str(room_position).upper()
    draft_pos = str(draft_position).upper()

    if room_pos == "DI":
        return draft_pos in {"DL", "DT", "NT", "DE"}
    if room_pos == "ED":
        return draft_pos in {"DE", "EDGE", "ED", "OLB", "LB"}

    return draft_pos in FRONT_DRAFT_POSITIONS


def load_draft_values(
    data_dir: Path,
    explicit_path: str | None,
) -> tuple[pd.DataFrame, str]:
    candidates = []

    if explicit_path:
        candidates.append(Path(explicit_path))

    candidates.append(data_dir / "draft_values.csv")

    for path in candidates:
        if path.exists():
            values = pd.read_csv(path, low_memory=False)
            return values, str(path)

    values = pd.read_csv(DRAFT_VALUE_URL, low_memory=False)
    cache_path = data_dir / "draft_values.csv"
    values.to_csv(cache_path, index=False)
    return values, DRAFT_VALUE_URL


def standardize_within_season(
    frame: pd.DataFrame,
    column: str,
) -> pd.Series:
    def transform(group: pd.Series) -> pd.Series:
        values = pd.to_numeric(group, errors="coerce")
        std = values.std(ddof=0)

        if pd.isna(std) or std == 0:
            return pd.Series(0.0, index=group.index)

        return (values - values.mean()) / std

    return frame.groupby("season")[column].transform(transform)


def percentile_within_season(
    frame: pd.DataFrame,
    column: str,
) -> pd.Series:
    return frame.groupby("season")[column].rank(
        pct=True,
        method="average",
    )


def hhi(values: pd.Series) -> float:
    clean = pd.to_numeric(values, errors="coerce").fillna(0.0)
    clean = clean.clip(lower=0.0)
    total = clean.sum()

    if total <= 0:
        return np.nan

    shares = clean / total
    return float(np.square(shares).sum())


def top_share(values: pd.Series, n: int) -> float:
    clean = (
        pd.to_numeric(values, errors="coerce")
        .fillna(0.0)
        .clip(lower=0.0)
    )
    total = clean.sum()

    if total <= 0:
        return np.nan

    return float(clean.nlargest(n).sum() / total)


def prepare_cap(cap: pd.DataFrame) -> pd.DataFrame:
    output = cap.copy().reset_index(drop=True)
    output["cap_row_id"] = np.arange(len(output), dtype=int)
    output["season"] = pd.to_numeric(
        output["season"],
        errors="coerce",
    ).astype("Int64")
    output["team_norm"] = output["team"].map(normalize_team)
    output["cap_name_canonical"] = output["player_name"].map(
        parse_spotrac_name
    )
    output["cap_hit"] = pd.to_numeric(
        output["cap_hit"],
        errors="coerce",
    )
    output["cap_position_norm"] = (
        output["position"].astype("string").str.upper().str.strip()
    )
    return output


def prepare_draft(
    draft: pd.DataFrame,
    draft_values: pd.DataFrame,
) -> pd.DataFrame:
    output = draft.copy().reset_index(drop=True)
    output["draft_row_id"] = np.arange(len(output), dtype=int)
    output["draft_year"] = pd.to_numeric(
        output["draft_year"],
        errors="coerce",
    ).astype("Int64")
    output["round"] = pd.to_numeric(
        output["round"],
        errors="coerce",
    ).astype("Int64")
    output["overall_pick"] = pd.to_numeric(
        output["overall_pick"],
        errors="coerce",
    ).astype("Int64")
    output["draft_team_norm"] = output["draft_team"].map(
        normalize_team
    )
    output["draft_name_canonical"] = output["player_name"].map(
        canonical_name
    )
    output["draft_position_norm"] = (
        output["position"].astype("string").str.upper().str.strip()
    )

    values = draft_values.copy()
    values["pick"] = pd.to_numeric(
        values["pick"],
        errors="coerce",
    ).astype("Int64")

    retain = [
        column
        for column in ["pick", "stuart", "johnson", "hill", "otc", "pff"]
        if column in values.columns
    ]

    output = output.merge(
        values[retain],
        left_on="overall_pick",
        right_on="pick",
        how="left",
        validate="many_to_one",
    )

    return output


def match_cap_row(
    room_row: pd.Series,
    cap: pd.DataFrame,
) -> dict[str, Any]:
    season = int(room_row["season"])
    team = room_row["team"]
    name = room_row["player_name_canonical"]
    position = room_row["position"]

    pool = cap.loc[
        (cap["season"] == season)
        & (cap["team_norm"] == team)
    ].copy()

    exact = pool.loc[
        pool["cap_name_canonical"] == name
    ].copy()

    if len(exact) > 1:
        compatible = exact.loc[
            exact["cap_position_norm"].map(
                lambda value: cap_position_compatible(position, value)
            )
        ]

        if len(compatible) == 1:
            exact = compatible
        elif len(compatible) > 1:
            exact = compatible.sort_values(
                "cap_hit",
                ascending=False,
            ).head(1)
        else:
            exact = exact.sort_values(
                "cap_hit",
                ascending=False,
            ).head(1)

    if len(exact) == 1:
        matched = exact.iloc[0]
        return {
            "cap_row_id": int(matched["cap_row_id"]),
            "cap_hit": float(matched["cap_hit"]),
            "cap_position": matched["cap_position_norm"],
            "cap_match_method": "canonical_exact",
            "cap_match_score": 100.0,
            "cap_match_status": "matched",
            "cap_source_name": matched["player_name"],
        }

    compatible_pool = pool.loc[
        pool["cap_position_norm"].map(
            lambda value: cap_position_compatible(position, value)
        )
    ].copy()

    scored: list[tuple[float, int]] = []

    for index, candidate in compatible_pool.iterrows():
        candidate_name = candidate["cap_name_canonical"]

        if not candidate_name or not name:
            continue

        same_last = last_name_token(name) == last_name_token(
            candidate_name
        )

        score = similarity(name, candidate_name)

        # A fuzzy cap bridge must preserve surname identity.
        if same_last:
            scored.append((score, index))

    scored.sort(reverse=True)

    if scored:
        best_score, best_index = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - runner_up

        if (
            best_score >= FUZZY_CAP_THRESHOLD
            and margin >= FUZZY_MARGIN
        ):
            matched = cap.loc[best_index]

            return {
                "cap_row_id": int(matched["cap_row_id"]),
                "cap_hit": float(matched["cap_hit"]),
                "cap_position": matched["cap_position_norm"],
                "cap_match_method": "same_team_fuzzy",
                "cap_match_score": float(best_score),
                "cap_match_status": "matched",
                "cap_source_name": matched["player_name"],
            }

    same_season_elsewhere = cap.loc[
        (cap["season"] == season)
        & (cap["cap_name_canonical"] == name)
    ]

    status = (
        "same_season_other_team"
        if not same_season_elsewhere.empty
        else "not_found"
    )

    return {
        "cap_row_id": pd.NA,
        "cap_hit": np.nan,
        "cap_position": pd.NA,
        "cap_match_method": "unmatched",
        "cap_match_score": np.nan,
        "cap_match_status": status,
        "cap_source_name": pd.NA,
    }


def match_draft_row(
    room_row: pd.Series,
    draft: pd.DataFrame,
) -> dict[str, Any]:
    season = int(room_row["season"])
    name = room_row["player_name_canonical"]
    position = room_row["position"]

    eligible_pool = draft.loc[
        (draft["draft_year"] <= season)
        & (draft["draft_year"] >= season - 7)
        & draft["draft_position_norm"].map(
            lambda value: draft_position_compatible(position, value)
        )
    ].copy()

    exact = eligible_pool.loc[
        eligible_pool["draft_name_canonical"] == name
    ].copy()

    if len(exact) > 1:
        exact = exact.sort_values(
            ["draft_year", "overall_pick"],
            ascending=[False, True],
        ).head(1)

    if len(exact) == 1:
        matched = exact.iloc[0]
        return draft_match_payload(
            matched,
            method="canonical_exact",
            score=100.0,
        )

    scored: list[tuple[float, int]] = []

    for index, candidate in eligible_pool.iterrows():
        candidate_name = candidate["draft_name_canonical"]

        if not candidate_name or not name:
            continue

        if last_name_token(name) != last_name_token(candidate_name):
            continue

        score = similarity(name, candidate_name)
        scored.append((score, index))

    scored.sort(reverse=True)

    if scored:
        best_score, best_index = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        margin = best_score - runner_up

        if (
            best_score >= FUZZY_DRAFT_THRESHOLD
            and margin >= FUZZY_MARGIN
        ):
            matched = draft.loc[best_index]
            return draft_match_payload(
                matched,
                method="position_year_fuzzy",
                score=best_score,
            )

    return {
        "draft_row_id": pd.NA,
        "draft_match_status": "not_matched",
        "draft_match_method": "unmatched",
        "draft_match_score": np.nan,
        "draft_year": pd.NA,
        "draft_team": pd.NA,
        "draft_round": pd.NA,
        "overall_pick": pd.NA,
        "draft_source_name": pd.NA,
        "draft_position": pd.NA,
        "gsis_id": pd.NA,
        "pfr_player_id": pd.NA,
        "stuart": np.nan,
        "johnson": np.nan,
        "hill": np.nan,
        "otc": np.nan,
        "pff": np.nan,
    }


def draft_match_payload(
    row: pd.Series,
    method: str,
    score: float,
) -> dict[str, Any]:
    return {
        "draft_row_id": int(row["draft_row_id"]),
        "draft_match_status": "matched",
        "draft_match_method": method,
        "draft_match_score": float(score),
        "draft_year": int(row["draft_year"]),
        "draft_team": row["draft_team_norm"],
        "draft_round": int(row["round"]),
        "overall_pick": int(row["overall_pick"]),
        "draft_source_name": row["player_name"],
        "draft_position": row["draft_position_norm"],
        "gsis_id": row.get("gsis_id", pd.NA),
        "pfr_player_id": row.get("pfr_player_id", pd.NA),
        "stuart": row.get("stuart", np.nan),
        "johnson": row.get("johnson", np.nan),
        "hill": row.get("hill", np.nan),
        "otc": row.get("otc", np.nan),
        "pff": row.get("pff", np.nan),
    }


def create_player_bridge(
    players: pd.DataFrame,
    cap: pd.DataFrame,
    draft: pd.DataFrame,
) -> pd.DataFrame:
    bridge = players.copy()
    bridge["team"] = bridge["team"].map(normalize_team)
    bridge["player_name_canonical"] = bridge["player"].map(
        canonical_name
    )

    cap_matches = bridge.apply(
        match_cap_row,
        axis=1,
        result_type="expand",
        cap=cap,
    )

    draft_matches = bridge.apply(
        match_draft_row,
        axis=1,
        result_type="expand",
        draft=draft,
    )

    bridge = pd.concat(
        [
            bridge.reset_index(drop=True),
            cap_matches.reset_index(drop=True),
            draft_matches.reset_index(drop=True),
        ],
        axis=1,
    )

    bridge["cap_matched"] = bridge["cap_match_status"].eq("matched")
    bridge["cap_hit"] = pd.to_numeric(
        bridge["cap_hit"],
        errors="coerce",
    )
    bridge["cap_hit_m"] = bridge["cap_hit"] / 1_000_000.0
    bridge["salary_cap"] = bridge["season"].map(SALARY_CAP)
    bridge["player_cap_pct"] = (
        bridge["cap_hit"] / bridge["salary_cap"]
    )

    bridge["contract_year"] = (
        bridge["season"]
        - pd.to_numeric(bridge["draft_year"], errors="coerce")
        + 1
    )

    team_equals_draft_team = (
        bridge["team"].astype("string")
        == bridge["draft_team"].astype("string")
    ).fillna(False)

    bridge["homegrown"] = (
        bridge["draft_match_status"].eq("matched")
        & team_equals_draft_team
    ).fillna(False)

    bridge["active_rookie_strict"] = (
        bridge["draft_match_status"].eq("matched")
        & bridge["contract_year"].between(1, 4)
    )

    bridge["active_rookie_5yr"] = (
        bridge["active_rookie_strict"]
        | (
            bridge["draft_round"].eq(1)
            & bridge["contract_year"].eq(5)
        )
    )

    bridge["homegrown_active_rookie_strict"] = (
        bridge["homegrown"]
        & bridge["active_rookie_strict"]
    )

    bridge["homegrown_active_rookie_5yr"] = (
        bridge["homegrown"]
        & bridge["active_rookie_5yr"]
    )

    bridge["acquired_active_rookie_strict"] = (
        bridge["active_rookie_strict"]
        & ~bridge["homegrown"]
    )

    for curve in ["otc", "hill", "johnson", "stuart", "pff"]:
        bridge[curve] = pd.to_numeric(
            bridge[curve],
            errors="coerce",
        )

        bridge[f"draft_{curve}_annual_strict"] = np.where(
            bridge["homegrown_active_rookie_strict"],
            bridge[curve] / 4.0,
            0.0,
        )

        control_years = np.where(
            bridge["draft_round"].eq(1),
            5.0,
            4.0,
        )

        bridge[f"draft_{curve}_annual_5yr"] = np.where(
            bridge["homegrown_active_rookie_5yr"],
            bridge[curve] / control_years,
            0.0,
        )

    return bridge


def aggregate_team_resources(
    bridge: pd.DataFrame,
    team_master: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for (season, team), group in bridge.groupby(
        ["season", "team"],
        sort=True,
    ):
        rush_total = pd.to_numeric(
            group["pass_rush_opp"],
            errors="coerce",
        ).sum()

        pressure_total = pd.to_numeric(
            group["pressures"],
            errors="coerce",
        ).sum()

        matched = group["cap_matched"]

        matched_rush = pd.to_numeric(
            group.loc[matched, "pass_rush_opp"],
            errors="coerce",
        ).sum()

        matched_pressures = pd.to_numeric(
            group.loc[matched, "pressures"],
            errors="coerce",
        ).sum()

        observed_cap_hit = pd.to_numeric(
            group.loc[matched, "cap_hit"],
            errors="coerce",
        ).sum()

        cap_rush_coverage = (
            matched_rush / rush_total
            if rush_total > 0
            else np.nan
        )

        cap_pressure_coverage = (
            matched_pressures / pressure_total
            if pressure_total > 0
            else np.nan
        )

        cap_player_coverage = float(matched.mean())

        adjusted_cap_hit = (
            observed_cap_hit / cap_rush_coverage
            if pd.notna(cap_rush_coverage)
            and cap_rush_coverage > 0
            else np.nan
        )

        strict_homegrown = group[
            "homegrown_active_rookie_strict"
        ]
        strict_acquired = group[
            "acquired_active_rookie_strict"
        ]

        strict_homegrown_rush_share = (
            pd.to_numeric(
                group.loc[strict_homegrown, "pass_rush_opp"],
                errors="coerce",
            ).sum()
            / rush_total
            if rush_total > 0
            else np.nan
        )

        strict_homegrown_pressure_share = (
            pd.to_numeric(
                group.loc[strict_homegrown, "pressures"],
                errors="coerce",
            ).sum()
            / pressure_total
            if pressure_total > 0
            else np.nan
        )

        strict_acquired_rush_share = (
            pd.to_numeric(
                group.loc[strict_acquired, "pass_rush_opp"],
                errors="coerce",
            ).sum()
            / rush_total
            if rush_total > 0
            else np.nan
        )

        row = {
            "season": int(season),
            "team": team,
            "room_player_segments": int(len(group)),
            "salary_cap": SALARY_CAP[int(season)],
            "observed_room_cap_hit": float(observed_cap_hit),
            "observed_room_cap_hit_m": float(
                observed_cap_hit / 1_000_000.0
            ),
            "observed_room_cap_pct": float(
                observed_cap_hit / SALARY_CAP[int(season)]
            ),
            "coverage_adjusted_room_cap_hit": float(
                adjusted_cap_hit
            ),
            "coverage_adjusted_room_cap_hit_m": float(
                adjusted_cap_hit / 1_000_000.0
            ),
            "coverage_adjusted_room_cap_pct": float(
                adjusted_cap_hit / SALARY_CAP[int(season)]
            ),
            "cap_player_coverage": cap_player_coverage,
            "cap_rush_coverage": float(cap_rush_coverage),
            "cap_pressure_coverage": float(
                cap_pressure_coverage
            ),
            "cap_high_coverage": int(
                cap_rush_coverage >= CAP_COVERAGE_MODEL_THRESHOLD
            ),
            "matched_room_cap_hhi": hhi(
                group.loc[matched, "cap_hit"]
            ),
            "matched_top1_cap_share": top_share(
                group.loc[matched, "cap_hit"],
                1,
            ),
            "matched_top2_cap_share": top_share(
                group.loc[matched, "cap_hit"],
                2,
            ),
            "homegrown_active_rookie_count_strict": int(
                strict_homegrown.sum()
            ),
            "acquired_active_rookie_count_strict": int(
                strict_acquired.sum()
            ),
            "homegrown_rookie_rush_share_strict": float(
                strict_homegrown_rush_share
            ),
            "homegrown_rookie_pressure_share_strict": float(
                strict_homegrown_pressure_share
            ),
            "acquired_rookie_rush_share_strict": float(
                strict_acquired_rush_share
            ),
        }

        for curve in ["otc", "hill", "johnson", "stuart", "pff"]:
            row[f"active_draft_{curve}_strict"] = float(
                pd.to_numeric(
                    group[f"draft_{curve}_annual_strict"],
                    errors="coerce",
                ).sum()
            )

            row[f"active_draft_{curve}_5yr"] = float(
                pd.to_numeric(
                    group[f"draft_{curve}_annual_5yr"],
                    errors="coerce",
                ).sum()
            )

            row[f"active_draft_{curve}_hhi_strict"] = hhi(
                group.loc[
                    group[f"draft_{curve}_annual_strict"] > 0,
                    f"draft_{curve}_annual_strict",
                ]
            )

            row[f"active_draft_{curve}_top1_share_strict"] = (
                top_share(
                    group.loc[
                        group[f"draft_{curve}_annual_strict"] > 0,
                        f"draft_{curve}_annual_strict",
                    ],
                    1,
                )
            )

        rows.append(row)

    resources = pd.DataFrame(rows)

    team_master = team_master.copy()
    team_master["team"] = team_master["team"].map(normalize_team)

    resources = resources.merge(
        team_master,
        on=["season", "team"],
        how="left",
        validate="one_to_one",
        suffixes=("", "_layer2"),
    )

    # Primary cap component: coverage-adjusted estimate.
    resources["cap_investment_z"] = standardize_within_season(
        resources,
        "coverage_adjusted_room_cap_pct",
    )

    resources["cap_observed_z"] = standardize_within_season(
        resources,
        "observed_room_cap_pct",
    )

    for curve in ["otc", "hill", "johnson", "stuart", "pff"]:
        resources[f"draft_{curve}_z_strict"] = (
            standardize_within_season(
                resources,
                f"active_draft_{curve}_strict",
            )
        )

        resources[f"draft_{curve}_z_5yr"] = (
            standardize_within_season(
                resources,
                f"active_draft_{curve}_5yr",
            )
        )

    def add_resource_index(
        cap_column: str,
        draft_column: str,
        output_column: str,
        cap_weight: float,
    ) -> None:
        raw = (
            cap_weight * resources[cap_column]
            + (1.0 - cap_weight) * resources[draft_column]
        )

        resources[f"{output_column}_raw"] = raw
        resources[output_column] = resources.groupby(
            "season"
        )[f"{output_column}_raw"].transform(
            lambda values: (
                (values - values.mean())
                / values.std(ddof=0)
                if values.std(ddof=0) > 0
                else 0.0
            )
        )

    add_resource_index(
        "cap_investment_z",
        "draft_otc_z_strict",
        "resource_index",
        0.50,
    )

    add_resource_index(
        "cap_observed_z",
        "draft_otc_z_strict",
        "resource_index_observed_cap",
        0.50,
    )

    add_resource_index(
        "cap_investment_z",
        "draft_otc_z_strict",
        "resource_index_60_cap",
        0.60,
    )

    add_resource_index(
        "cap_investment_z",
        "draft_otc_z_strict",
        "resource_index_40_cap",
        0.40,
    )

    add_resource_index(
        "cap_investment_z",
        "draft_otc_z_5yr",
        "resource_index_otc_5yr",
        0.50,
    )

    for curve in ["hill", "johnson", "stuart", "pff"]:
        add_resource_index(
            "cap_investment_z",
            f"draft_{curve}_z_strict",
            f"resource_index_{curve}",
            0.50,
        )

    resources["acquisition_mix"] = (
        resources["cap_investment_z"]
        - resources["draft_otc_z_strict"]
    )

    resources["resource_percentile"] = (
        percentile_within_season(
            resources,
            "resource_index",
        )
    )

    resources["resource_tier"] = pd.cut(
        resources["resource_percentile"],
        bins=[-np.inf, 0.25, 0.75, np.inf],
        labels=[
            "Low Investment",
            "Average Investment",
            "High Investment",
        ],
        include_lowest=True,
    ).astype("string")

    resources["acquisition_mix_percentile"] = (
        percentile_within_season(
            resources,
            "acquisition_mix",
        )
    )

    resources["acquisition_mode"] = np.select(
        [
            resources["acquisition_mix_percentile"] >= 0.75,
            resources["acquisition_mix_percentile"] <= 0.25,
        ],
        [
            "Cap-Heavy",
            "Draft-Heavy",
        ],
        default="Balanced",
    )

    return resources


def add_efficiency_residuals(
    resources: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = resources.copy()

    model_frame = output.loc[
        output["cap_high_coverage"].eq(1)
    ].copy()

    specs = [
        (
            "pressure_z",
            "resource_adjusted_pressure",
            "pressure_z ~ resource_index + C(season)",
        ),
        (
            "four_man_pressure_z",
            "resource_adjusted_four_man_pressure",
            "four_man_pressure_z ~ resource_index + C(season)",
        ),
        (
            "pass_defense_composite",
            "resource_adjusted_pass_defense",
            (
                "pass_defense_composite ~ "
                "resource_index + C(season)"
            ),
        ),
        (
            "pass_defense_composite",
            "resource_and_pressure_adjusted_pass_defense",
            (
                "pass_defense_composite ~ "
                "resource_index + pressure_z + C(season)"
            ),
        ),
    ]

    model_rows: list[dict[str, Any]] = []

    for outcome, residual_column, formula in specs:
        model = smf.ols(
            formula,
            data=model_frame,
        ).fit(cov_type="HC3")

        output[residual_column] = (
            output[outcome] - model.predict(output)
        )

        for parameter in model.params.index:
            if parameter == "Intercept" or parameter.startswith(
                "C(season)"
            ):
                continue

            interval = model.conf_int().loc[parameter]

            model_rows.append(
                {
                    "model_group": "resource_efficiency",
                    "model": formula,
                    "outcome": outcome,
                    "parameter": parameter,
                    "coefficient": float(model.params[parameter]),
                    "robust_se": float(model.bse[parameter]),
                    "p_value": float(model.pvalues[parameter]),
                    "ci_low": float(interval.iloc[0]),
                    "ci_high": float(interval.iloc[1]),
                    "adjusted_r2": float(model.rsquared_adj),
                    "n": int(model.nobs),
                }
            )

    return output, pd.DataFrame(model_rows)


def fit_archetype_models(
    resources: pd.DataFrame,
) -> pd.DataFrame:
    model_frame = resources.loc[
        resources["cap_high_coverage"].eq(1)
    ].copy()

    model_frame["archetype"] = pd.Categorical(
        model_frame["archetype"],
        categories=[
            "Thin / Mixed",
            "Distributed Rotation",
            "Heliocentric Star",
            "Star + Depth",
        ],
    )

    specifications = [
        (
            "Pressure creation from resources and architecture",
            "pressure_z",
            (
                "pressure_z ~ resource_index + "
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                "+ C(season)"
            ),
        ),
        (
            "Four-man pressure from resources and architecture",
            "four_man_pressure_z",
            (
                "four_man_pressure_z ~ resource_index + "
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                "+ C(season)"
            ),
        ),
        (
            "Pass defense from resources and architecture",
            "pass_defense_composite",
            (
                "pass_defense_composite ~ resource_index + "
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                "+ C(season)"
            ),
        ),
        (
            "Pass defense from resources, pressure, and architecture",
            "pass_defense_composite",
            (
                "pass_defense_composite ~ resource_index + "
                "pressure_z + "
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                "+ C(season)"
            ),
        ),
        (
            "Pressure from separate cap and draft components",
            "pressure_z",
            (
                "pressure_z ~ cap_investment_z + "
                "draft_otc_z_strict + "
                'C(archetype, Treatment(reference="Thin / Mixed")) '
                "+ C(season)"
            ),
        ),
        (
            "Pressure from investment and allocation shape",
            "pressure_z",
            (
                "pressure_z ~ resource_index + "
                "matched_room_cap_hhi + "
                "active_draft_otc_hhi_strict + "
                "support_quality_z + C(season)"
            ),
        ),
    ]

    rows: list[dict[str, Any]] = []

    for model_name, outcome, formula in specifications:
        model = smf.ols(
            formula,
            data=model_frame,
        ).fit(cov_type="HC3")

        for parameter in model.params.index:
            if parameter == "Intercept" or parameter.startswith(
                "C(season)"
            ):
                continue

            interval = model.conf_int().loc[parameter]

            rows.append(
                {
                    "model_group": "layer_3_primary",
                    "model_name": model_name,
                    "formula": formula,
                    "outcome": outcome,
                    "parameter": parameter,
                    "coefficient": float(model.params[parameter]),
                    "robust_se": float(model.bse[parameter]),
                    "p_value": float(model.pvalues[parameter]),
                    "ci_low": float(interval.iloc[0]),
                    "ci_high": float(interval.iloc[1]),
                    "adjusted_r2": float(model.rsquared_adj),
                    "n": int(model.nobs),
                }
            )

    return pd.DataFrame(rows)


def build_archetype_summary(
    resources: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for archetype in ROOM_ARCHETYPE_ORDER:
        group = resources.loc[
            resources["archetype"] == archetype
        ].copy()

        high = group.loc[
            group["cap_high_coverage"].eq(1)
        ]

        rows.append(
            {
                "archetype": archetype,
                "team_seasons": int(len(group)),
                "high_coverage_team_seasons": int(len(high)),
                "median_observed_room_cap_pct": float(
                    group["observed_room_cap_pct"].median()
                ),
                "median_adjusted_room_cap_pct": float(
                    group["coverage_adjusted_room_cap_pct"].median()
                ),
                "median_active_draft_otc_strict": float(
                    group["active_draft_otc_strict"].median()
                ),
                "median_resource_index": float(
                    group["resource_index"].median()
                ),
                "median_acquisition_mix": float(
                    group["acquisition_mix"].median()
                ),
                "median_cap_hhi": float(
                    group["matched_room_cap_hhi"].median()
                ),
                "median_draft_hhi": float(
                    group["active_draft_otc_hhi_strict"].median()
                ),
                "median_homegrown_rookie_rush_share": float(
                    group[
                        "homegrown_rookie_rush_share_strict"
                    ].median()
                ),
                "median_homegrown_rookie_pressure_share": float(
                    group[
                        "homegrown_rookie_pressure_share_strict"
                    ].median()
                ),
                "median_pressure_z": float(
                    group["pressure_z"].median()
                ),
                "median_four_man_pressure_z": float(
                    group["four_man_pressure_z"].median()
                ),
                "median_pass_defense_composite": float(
                    group["pass_defense_composite"].median()
                ),
                "median_resource_adjusted_pressure": float(
                    high["resource_adjusted_pressure"].median()
                ),
                "median_resource_adjusted_four_man_pressure": float(
                    high[
                        "resource_adjusted_four_man_pressure"
                    ].median()
                ),
                "median_resource_adjusted_pass_defense": float(
                    high[
                        "resource_adjusted_pass_defense"
                    ].median()
                ),
                "median_cap_rush_coverage": float(
                    group["cap_rush_coverage"].median()
                ),
            }
        )

    return pd.DataFrame(rows)


def build_sensitivity(
    resources: pd.DataFrame,
) -> pd.DataFrame:
    variants = [
        "resource_index",
        "resource_index_observed_cap",
        "resource_index_60_cap",
        "resource_index_40_cap",
        "resource_index_otc_5yr",
        "resource_index_hill",
        "resource_index_johnson",
        "resource_index_stuart",
        "resource_index_pff",
    ]

    model_frame = resources.loc[
        resources["cap_high_coverage"].eq(1)
    ].copy()

    rows = []

    for variant in variants:
        spearman = resources[
            ["resource_index", variant]
        ].corr(method="spearman").iloc[0, 1]

        formula = f"pressure_z ~ {variant} + C(season)"
        model = smf.ols(
            formula,
            data=model_frame,
        ).fit(cov_type="HC3")

        interval = model.conf_int().loc[variant]

        rows.append(
            {
                "variant": variant,
                "spearman_vs_primary": float(spearman),
                "pressure_coefficient": float(
                    model.params[variant]
                ),
                "pressure_robust_se": float(
                    model.bse[variant]
                ),
                "pressure_p_value": float(
                    model.pvalues[variant]
                ),
                "pressure_ci_low": float(interval.iloc[0]),
                "pressure_ci_high": float(interval.iloc[1]),
                "pressure_adjusted_r2": float(
                    model.rsquared_adj
                ),
                "model_n": int(model.nobs),
            }
        )

    return pd.DataFrame(rows)


def build_identity_audit(
    bridge: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []

    for season in sorted(bridge["season"].unique()):
        group = bridge.loc[bridge["season"] == season]
        matched = group["cap_matched"]

        rows.append(
            {
                "audit_type": "season_cap_coverage",
                "season": int(season),
                "team": "ALL",
                "player": "ALL",
                "detail": "cap match coverage",
                "value_1": float(matched.mean()),
                "value_2": float(
                    group.loc[
                        matched,
                        "pass_rush_opp",
                    ].sum()
                    / group["pass_rush_opp"].sum()
                ),
                "value_3": float(
                    group.loc[
                        matched,
                        "pressures",
                    ].sum()
                    / group["pressures"].sum()
                ),
            }
        )

    unmatched = (
        bridge.loc[~bridge["cap_matched"]]
        .sort_values("pass_rush_opp", ascending=False)
        .head(100)
    )

    for row in unmatched.itertuples(index=False):
        rows.append(
            {
                "audit_type": "high_volume_unmatched_cap",
                "season": int(row.season),
                "team": row.team,
                "player": row.player,
                "detail": row.cap_match_status,
                "value_1": float(row.pass_rush_opp),
                "value_2": float(row.pressures),
                "value_3": np.nan,
            }
        )

    ambiguous_draft = bridge.loc[
        bridge["draft_match_method"].eq("position_year_fuzzy")
    ].sort_values(
        "draft_match_score",
        ascending=True,
    )

    for row in ambiguous_draft.itertuples(index=False):
        rows.append(
            {
                "audit_type": "fuzzy_draft_match",
                "season": int(row.season),
                "team": row.team,
                "player": row.player,
                "detail": (
                    f"{row.draft_source_name} | "
                    f"{row.draft_year} pick {row.overall_pick}"
                ),
                "value_1": float(row.draft_match_score),
                "value_2": float(row.pass_rush_opp),
                "value_3": np.nan,
            }
        )

    return pd.DataFrame(rows)


def make_resource_by_archetype_chart(
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = (
        summary.set_index("archetype")
        .loc[ROOM_ARCHETYPE_ORDER]
    )

    figure, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar(
        plot.index,
        plot["median_resource_index"],
    )

    axis.axhline(0, linewidth=1)
    axis.set_title(
        "Resource Investment by Pass-Rush Room Construction"
    )
    axis.set_ylabel("Median Resource Investment Index")
    axis.tick_params(axis="x", rotation=15)

    for bar, value in zip(
        bars,
        plot["median_resource_index"],
    ):
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


def make_resource_pressure_chart(
    resources: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = resources.loc[
        resources["cap_high_coverage"].eq(1)
    ].copy()

    figure, axis = plt.subplots(figsize=(12, 8))

    for archetype in ROOM_ARCHETYPE_ORDER:
        group = plot.loc[plot["archetype"] == archetype]
        axis.scatter(
            group["resource_index"],
            group["pressure_z"],
            alpha=0.65,
            label=archetype,
        )

    fit = np.polyfit(
        plot["resource_index"],
        plot["pressure_z"],
        deg=1,
    )
    grid = np.linspace(
        plot["resource_index"].min(),
        plot["resource_index"].max(),
        100,
    )
    axis.plot(grid, fit[0] * grid + fit[1], linewidth=1)

    axis.axhline(0, linewidth=1)
    axis.axvline(0, linewidth=1)
    axis.set_title(
        "Pass-Rush Resources and Pressure Creation"
    )
    axis.set_xlabel("Resource Investment Index")
    axis.set_ylabel("Team pressure z-score")
    axis.legend(loc="best")

    label_rows = pd.concat(
        [
            plot.nlargest(4, "resource_adjusted_pressure"),
            plot.nsmallest(4, "resource_adjusted_pressure"),
        ]
    ).drop_duplicates(["season", "team"])

    for row in label_rows.itertuples(index=False):
        axis.annotate(
            f"{row.team} {int(row.season)}",
            (row.resource_index, row.pressure_z),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
        )

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def make_efficiency_by_archetype_chart(
    summary: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = (
        summary.set_index("archetype")
        .loc[ROOM_ARCHETYPE_ORDER]
    )

    figure, axis = plt.subplots(figsize=(12, 7))
    bars = axis.bar(
        plot.index,
        plot["median_resource_adjusted_pressure"],
    )

    axis.axhline(0, linewidth=1)
    axis.set_title(
        "Pressure Creation Above or Below Resource Expectation"
    )
    axis.set_ylabel("Median resource-adjusted pressure")
    axis.tick_params(axis="x", rotation=15)

    for bar, value in zip(
        bars,
        plot["median_resource_adjusted_pressure"],
    ):
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


def make_cap_draft_mix_chart(
    resources: pd.DataFrame,
    output_path: Path,
) -> None:
    plot = resources.loc[
        resources["cap_high_coverage"].eq(1)
    ].copy()

    figure, axis = plt.subplots(figsize=(12, 8))

    for archetype in ROOM_ARCHETYPE_ORDER:
        group = plot.loc[plot["archetype"] == archetype]
        axis.scatter(
            group["draft_otc_z_strict"],
            group["cap_investment_z"],
            alpha=0.65,
            label=archetype,
        )

    axis.axhline(0, linewidth=1)
    axis.axvline(0, linewidth=1)
    axis.set_title("How Teams Fund Their Pass-Rush Rooms")
    axis.set_xlabel("Active homegrown draft investment z-score")
    axis.set_ylabel("Cap investment z-score")
    axis.legend(loc="best")

    figure.tight_layout()
    figure.savefig(output_path, dpi=200, bbox_inches="tight")
    plt.close(figure)


def build_findings(
    bridge: pd.DataFrame,
    resources: pd.DataFrame,
    summary: pd.DataFrame,
    models: pd.DataFrame,
    sensitivity: pd.DataFrame,
    source_paths: dict[str, str],
) -> dict[str, Any]:
    summary_lookup = summary.set_index("archetype")

    primary_model = models.loc[
        (
            models["model_name"]
            == "Pressure creation from resources and architecture"
        )
        & (models["parameter"] == "resource_index")
    ]

    pressure_resource = (
        primary_model.iloc[0].to_dict()
        if not primary_model.empty
        else {}
    )

    star_depth = models.loc[
        (
            models["model_name"]
            == "Pressure creation from resources and architecture"
        )
        & models["parameter"].str.contains(
            "Star \\+ Depth",
            regex=True,
            na=False,
        )
    ]

    star_depth_result = (
        star_depth.iloc[0].to_dict()
        if not star_depth.empty
        else {}
    )

    high_coverage = resources.loc[
        resources["cap_high_coverage"].eq(1)
    ]

    top_efficiency = (
        high_coverage.nlargest(
            10,
            "resource_adjusted_pressure",
        )[
            [
                "season",
                "team",
                "archetype",
                "resource_index",
                "pressure_z",
                "resource_adjusted_pressure",
            ]
        ].to_dict(orient="records")
    )

    bottom_efficiency = (
        high_coverage.nsmallest(
            10,
            "resource_adjusted_pressure",
        )[
            [
                "season",
                "team",
                "archetype",
                "resource_index",
                "pressure_z",
                "resource_adjusted_pressure",
            ]
        ].to_dict(orient="records")
    )

    return {
        "status": "Layer 3 resource investment build complete",
        "source_paths": source_paths,
        "sample": {
            "player_segments": int(len(bridge)),
            "team_seasons": int(len(resources)),
            "high_cap_coverage_team_seasons": int(
                resources["cap_high_coverage"].sum()
            ),
            "overall_cap_player_match_rate": float(
                bridge["cap_matched"].mean()
            ),
            "overall_cap_rush_coverage": float(
                bridge.loc[
                    bridge["cap_matched"],
                    "pass_rush_opp",
                ].sum()
                / bridge["pass_rush_opp"].sum()
            ),
            "overall_cap_pressure_coverage": float(
                bridge.loc[
                    bridge["cap_matched"],
                    "pressures",
                ].sum()
                / bridge["pressures"].sum()
            ),
        },
        "primary_v1_methodology": {
            "cap_component": (
                "Coverage-adjusted room cap hit divided by the "
                "league salary cap, standardized within season."
            ),
            "draft_component": (
                "Annualized Fitzgerald-Spielberger/OTC value of "
                "homegrown players in contract years 1-4, "
                "standardized within season."
            ),
            "resource_index": (
                "Equal-weight cap and draft components, then "
                "re-standardized within season."
            ),
            "model_sample_rule": (
                "Primary inference requires cap match coverage of "
                f"at least {CAP_COVERAGE_MODEL_THRESHOLD:.0%} by "
                "pass-rush opportunity."
            ),
            "allocation_rule": (
                "Cap and draft concentration remain separate from "
                "total resource investment."
            ),
        },
        "archetype_resource_summary": {
            archetype: {
                "team_seasons": int(
                    summary_lookup.loc[
                        archetype,
                        "team_seasons",
                    ]
                ),
                "median_resource_index": float(
                    summary_lookup.loc[
                        archetype,
                        "median_resource_index",
                    ]
                ),
                "median_adjusted_room_cap_pct": float(
                    summary_lookup.loc[
                        archetype,
                        "median_adjusted_room_cap_pct",
                    ]
                ),
                "median_active_draft_otc_strict": float(
                    summary_lookup.loc[
                        archetype,
                        "median_active_draft_otc_strict",
                    ]
                ),
                "median_resource_adjusted_pressure": float(
                    summary_lookup.loc[
                        archetype,
                        "median_resource_adjusted_pressure",
                    ]
                ),
            }
            for archetype in ROOM_ARCHETYPE_ORDER
        },
        "primary_pressure_model": pressure_resource,
        "star_depth_pressure_association_after_resources": (
            star_depth_result
        ),
        "sensitivity": sensitivity.to_dict(orient="records"),
        "top_resource_pressure_efficiency": top_efficiency,
        "bottom_resource_pressure_efficiency": bottom_efficiency,
        "limitations": [
            (
                "The supplied Spotrac file does not match every "
                "modeled pass rusher. Coverage-adjusted estimates "
                "and high-coverage model restrictions reduce but "
                "do not eliminate this limitation."
            ),
            (
                "Draft capital represents original homegrown "
                "acquisition cost during active rookie control; "
                "trade compensation is not observed."
            ),
            (
                "The Resource Investment Index is season-relative "
                "and should not be interpreted as a dollar-valued "
                "return measure."
            ),
            (
                "All room-construction and resource findings are "
                "associative rather than causal."
            ),
        ],
    }


def build_methodology_markdown(
    findings: dict[str, Any],
) -> str:
    sample = findings["sample"]

    return f"""# Layer 3: Pass-Rush Resource Investment

## Objective

Layer 3 measures how much current cap and active draft capital each team has
committed to its pass-rush room, how those resources are distributed, and how
much pressure and pass-defense value the room generates relative to that
investment.

## Primary V1 resource metric

### Cap component

Room cap investment is the sum of matched player cap hits divided by the NFL
salary cap for that season. Because the supplied Spotrac export does not match
every modeled player, the primary cap estimate scales observed cap investment
by matched pass-rush-opportunity coverage.

The observed, unadjusted cap percentage and all coverage metrics remain in the
team master.

### Draft component

Draft investment counts only players who:

- were drafted by their current team;
- remain in contract years 1 through 4; and
- appear in the modeled pass-rush room.

The Fitzgerald-Spielberger/OTC pick value is annualized across four rookie
control years. First-round fifth-year control is tested separately as a
sensitivity.

### Composite

The primary Resource Investment Index is:

1. season-standardized cap investment;
2. season-standardized active draft investment;
3. an equal-weight average of those components;
4. re-standardization of the combined score within season.

A score of zero is league average for that season. Positive values indicate
above-average current resource commitment.

## Allocation metrics

Allocation shape is deliberately kept separate from total investment:

- matched room cap HHI;
- top-one and top-two cap shares;
- active draft-capital HHI;
- cap-heavy versus draft-heavy acquisition mix;
- homegrown rookie rush and pressure shares.

## Model sample

The complete player bridge contains {sample["player_segments"]:,} player
segments and {sample["team_seasons"]} team-seasons.

The supplied cap data matched:

- {sample["overall_cap_player_match_rate"]:.1%} of player segments;
- {sample["overall_cap_rush_coverage"]:.1%} of pass-rush opportunities;
- {sample["overall_cap_pressure_coverage"]:.1%} of pressures.

Primary inferential models use only the
{sample["high_cap_coverage_team_seasons"]} team-seasons with at least
{CAP_COVERAGE_MODEL_THRESHOLD:.0%} cap coverage by pass-rush opportunity.

## Interpretation boundary

The Resource Investment Index measures current, season-relative organizational
commitment. It does not estimate exact economic surplus, trade compensation,
or causal return on investment. Resource-adjusted outcomes are residuals from
descriptive models and should be interpreted as performance above or below the
sample expectation for similarly resourced rooms.
"""


def main() -> None:
    args = parse_args()

    data_dir = Path(args.data_dir)
    output_dir = (
        Path(args.output_dir)
        if args.output_dir
        else data_dir / "outputs" / "layer_3_resources"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    player_path = resolve_input(
        data_dir,
        [
            "Layer_2_Creation_Finish_v2_Player_Master.csv",
            "Layer_2_Player_Room_Master.csv",
            "Layer_2_Player_Room_Master(1).csv",
        ],
    )

    team_path = resolve_input(
        data_dir,
        [
            "Layer_2_Creation_Finish_v2_Team_Master.csv",
            "Layer_2_Team_Season_Room_Master.csv",
        ],
    )

    cap_path = resolve_input(
        data_dir,
        [
            "spotrac_player_cap_hits_2022_2025.csv",
            "spotrac_player_cap_hits_2022_2025(1).csv",
        ],
    )

    draft_path = resolve_input(
        data_dir,
        [
            "draft_classes_2018_2025.csv",
        ],
    )

    players = pd.read_csv(player_path, low_memory=False)
    team_master = pd.read_csv(team_path, low_memory=False)
    cap_raw = pd.read_csv(cap_path, low_memory=False)
    draft_raw = pd.read_csv(draft_path, low_memory=False)
    draft_values, draft_value_source = load_draft_values(
        data_dir,
        args.draft_values,
    )

    cap = prepare_cap(cap_raw)
    draft = prepare_draft(draft_raw, draft_values)

    bridge = create_player_bridge(players, cap, draft)
    resources = aggregate_team_resources(
        bridge,
        team_master,
    )

    resources, efficiency_models = add_efficiency_residuals(
        resources
    )
    primary_models = fit_archetype_models(resources)
    models = pd.concat(
        [primary_models, efficiency_models],
        ignore_index=True,
        sort=False,
    )

    archetype_summary = build_archetype_summary(resources)
    sensitivity = build_sensitivity(resources)
    identity_audit = build_identity_audit(bridge)

    source_paths = {
        "player_master": str(player_path),
        "team_master": str(team_path),
        "cap_file": str(cap_path),
        "draft_file": str(draft_path),
        "draft_values": draft_value_source,
    }

    findings = build_findings(
        bridge=bridge,
        resources=resources,
        summary=archetype_summary,
        models=primary_models,
        sensitivity=sensitivity,
        source_paths=source_paths,
    )

    methodology = build_methodology_markdown(findings)

    outputs = {
        "player_bridge": (
            output_dir / "Layer_3_Player_Resource_Bridge.csv"
        ),
        "team_master": (
            output_dir / "Layer_3_Team_Resource_Master.csv"
        ),
        "archetype_summary": (
            output_dir / "Layer_3_Archetype_Resource_Summary.csv"
        ),
        "models": (
            output_dir / "Layer_3_Resource_Models.csv"
        ),
        "sensitivity": (
            output_dir / "Layer_3_Resource_Sensitivity.csv"
        ),
        "identity_audit": (
            output_dir / "Layer_3_Identity_Audit.csv"
        ),
        "findings": (
            output_dir / "Layer_3_Findings.json"
        ),
        "methodology": (
            output_dir / "Layer_3_Methodology.md"
        ),
        "resource_chart": (
            output_dir
            / "Layer_3_Resource_Investment_by_Archetype.png"
        ),
        "pressure_chart": (
            output_dir
            / "Layer_3_Resource_vs_Pressure.png"
        ),
        "efficiency_chart": (
            output_dir
            / "Layer_3_Resource_Adjusted_Pressure_by_Archetype.png"
        ),
        "mix_chart": (
            output_dir / "Layer_3_Cap_Draft_Mix.png"
        ),
    }

    bridge.to_csv(outputs["player_bridge"], index=False)
    resources.to_csv(outputs["team_master"], index=False)
    archetype_summary.to_csv(
        outputs["archetype_summary"],
        index=False,
    )
    models.to_csv(outputs["models"], index=False)
    sensitivity.to_csv(outputs["sensitivity"], index=False)
    identity_audit.to_csv(
        outputs["identity_audit"],
        index=False,
    )

    with outputs["findings"].open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(findings, handle, indent=2, default=str)

    outputs["methodology"].write_text(
        methodology,
        encoding="utf-8",
    )

    make_resource_by_archetype_chart(
        archetype_summary,
        outputs["resource_chart"],
    )
    make_resource_pressure_chart(
        resources,
        outputs["pressure_chart"],
    )
    make_efficiency_by_archetype_chart(
        archetype_summary,
        outputs["efficiency_chart"],
    )
    make_cap_draft_mix_chart(
        resources,
        outputs["mix_chart"],
    )

    print(
        json.dumps(
            {
                "status": "Layer 3 resource build complete",
                "output_dir": str(output_dir),
                "high_coverage_team_seasons": int(
                    resources["cap_high_coverage"].sum()
                ),
                "cap_player_match_rate": float(
                    bridge["cap_matched"].mean()
                ),
                "cap_rush_coverage": float(
                    bridge.loc[
                        bridge["cap_matched"],
                        "pass_rush_opp",
                    ].sum()
                    / bridge["pass_rush_opp"].sum()
                ),
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
