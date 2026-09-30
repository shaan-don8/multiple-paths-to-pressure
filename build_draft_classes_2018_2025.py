#!/usr/bin/env python3
"""
Download and standardize NFL draft classes for 2018-2025.

Primary source
--------------
nflverse draft-picks release, which is maintained from Pro Football
Reference draft data:

https://github.com/nflverse/nflverse-data/releases/download/draft_picks/draft_picks.csv

Outputs
-------
- draft_classes_2018_2021.csv
- draft_classes_2018_2025.csv
- draft_classes_2018_2025_audit.json

If an existing draft_classes_2022_2025.csv is present, the script also
compares the overlapping seasons and reports key mismatches.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


DRAFT_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "draft_picks/draft_picks.csv"
)

OUTPUT_COLUMNS = [
    "draft_year",
    "draft_team",
    "round",
    "overall_pick",
    "player_name",
    "position",
    "college",
    "gsis_id",
    "pfr_player_id",
    "draft_club",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default=".",
        help="Folder containing the existing 2022-2025 file and outputs.",
    )
    return parser.parse_args()


def normalize_team(series: pd.Series) -> pd.Series:
    """
    Normalize known historical/current abbreviation differences to the
    same style used in the existing project files.
    """
    mapping = {
        "GNB": "GB",
        "KAN": "KC",
        "LVR": "LV",
        "NWE": "NE",
        "NOR": "NO",
        "SFO": "SF",
        "TAM": "TB",
    }

    return (
        series.astype("string")
        .str.strip()
        .str.upper()
        .replace(mapping)
    )


def standardize_draft_picks(raw: pd.DataFrame) -> pd.DataFrame:
    required = {
        "season",
        "team",
        "round",
        "pick",
        "pfr_player_name",
        "position",
        "college",
        "gsis_id",
        "pfr_player_id",
    }

    missing = sorted(required - set(raw.columns))
    if missing:
        raise ValueError(
            "The nflverse draft file is missing expected columns: "
            f"{missing}"
        )

    output = pd.DataFrame(
        {
            "draft_year": pd.to_numeric(
                raw["season"],
                errors="coerce",
            ),
            "draft_team": normalize_team(raw["team"]),
            "round": pd.to_numeric(
                raw["round"],
                errors="coerce",
            ),
            "overall_pick": pd.to_numeric(
                raw["pick"],
                errors="coerce",
            ),
            "player_name": (
                raw["pfr_player_name"]
                .astype("string")
                .str.strip()
            ),
            "position": (
                raw["position"]
                .astype("string")
                .str.strip()
                .str.upper()
            ),
            "college": (
                raw["college"]
                .astype("string")
                .str.strip()
            ),
            "gsis_id": (
                raw["gsis_id"]
                .astype("string")
                .str.strip()
            ),
            "pfr_player_id": (
                raw["pfr_player_id"]
                .astype("string")
                .str.strip()
            ),
        }
    )

    output["draft_club"] = output["draft_team"]

    output = output.loc[
        output["draft_year"].between(2018, 2025)
        & output["overall_pick"].notna()
        & output["player_name"].notna()
    ].copy()

    output["draft_year"] = output["draft_year"].astype(int)
    output["round"] = output["round"].astype("Int64")
    output["overall_pick"] = output["overall_pick"].astype(int)

    # Convert pandas string missing markers back to true missing values.
    for column in [
        "player_name",
        "position",
        "college",
        "gsis_id",
        "pfr_player_id",
    ]:
        output[column] = output[column].replace(
            {
                "<NA>": pd.NA,
                "nan": pd.NA,
                "None": pd.NA,
                "": pd.NA,
            }
        )

    output = (
        output[OUTPUT_COLUMNS]
        .sort_values(
            ["draft_year", "overall_pick"],
            ascending=[True, True],
        )
        .drop_duplicates(
            ["draft_year", "overall_pick"],
            keep="first",
        )
        .reset_index(drop=True)
    )

    return output


def compare_overlap(
    fresh: pd.DataFrame,
    existing_path: Path,
) -> dict:
    if not existing_path.exists():
        return {
            "existing_file_found": False,
            "comparison_performed": False,
        }

    existing = pd.read_csv(existing_path, low_memory=False)

    required = {
        "draft_year",
        "overall_pick",
        "player_name",
        "draft_team",
        "gsis_id",
        "pfr_player_id",
    }

    missing = sorted(required - set(existing.columns))
    if missing:
        return {
            "existing_file_found": True,
            "comparison_performed": False,
            "reason": f"Existing file missing columns: {missing}",
        }

    fresh_overlap = fresh.loc[
        fresh["draft_year"].between(2022, 2025)
    ].copy()

    existing_overlap = existing.loc[
        pd.to_numeric(
            existing["draft_year"],
            errors="coerce",
        ).between(2022, 2025)
    ].copy()

    existing_overlap["draft_year"] = pd.to_numeric(
        existing_overlap["draft_year"],
        errors="coerce",
    ).astype(int)

    existing_overlap["overall_pick"] = pd.to_numeric(
        existing_overlap["overall_pick"],
        errors="coerce",
    ).astype("Int64")

    comparison = fresh_overlap.merge(
        existing_overlap[
            [
                "draft_year",
                "overall_pick",
                "player_name",
                "draft_team",
                "gsis_id",
                "pfr_player_id",
            ]
        ],
        on=["draft_year", "overall_pick"],
        how="outer",
        suffixes=("_fresh", "_existing"),
        indicator=True,
    )

    both = comparison["_merge"] == "both"

    name_mismatch = (
        both
        & (
            comparison["player_name_fresh"]
            .astype("string")
            .str.lower()
            != comparison["player_name_existing"]
            .astype("string")
            .str.lower()
        )
    )

    team_mismatch = (
        both
        & (
            normalize_team(comparison["draft_team_fresh"])
            != normalize_team(comparison["draft_team_existing"])
        )
    )

    gsis_mismatch = (
        both
        & comparison["gsis_id_fresh"].notna()
        & comparison["gsis_id_existing"].notna()
        & (
            comparison["gsis_id_fresh"].astype("string")
            != comparison["gsis_id_existing"].astype("string")
        )
    )

    pfr_mismatch = (
        both
        & comparison["pfr_player_id_fresh"].notna()
        & comparison["pfr_player_id_existing"].notna()
        & (
            comparison["pfr_player_id_fresh"].astype("string")
            != comparison["pfr_player_id_existing"].astype("string")
        )
    )

    return {
        "existing_file_found": True,
        "comparison_performed": True,
        "fresh_overlap_rows": int(len(fresh_overlap)),
        "existing_overlap_rows": int(len(existing_overlap)),
        "fresh_only_rows": int(
            (comparison["_merge"] == "left_only").sum()
        ),
        "existing_only_rows": int(
            (comparison["_merge"] == "right_only").sum()
        ),
        "name_mismatches": int(name_mismatch.sum()),
        "team_mismatches": int(team_mismatch.sum()),
        "gsis_id_mismatches_when_both_present": int(
            gsis_mismatch.sum()
        ),
        "pfr_id_mismatches_when_both_present": int(
            pfr_mismatch.sum()
        ),
    }


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading nflverse draft picks...")
    raw = pd.read_csv(DRAFT_URL, low_memory=False)

    draft = standardize_draft_picks(raw)

    early = draft.loc[
        draft["draft_year"].between(2018, 2021)
    ].copy()

    complete = draft.loc[
        draft["draft_year"].between(2018, 2025)
    ].copy()

    early_path = data_dir / "draft_classes_2018_2021.csv"
    complete_path = data_dir / "draft_classes_2018_2025.csv"
    audit_path = data_dir / "draft_classes_2018_2025_audit.json"

    early.to_csv(early_path, index=False)
    complete.to_csv(complete_path, index=False)

    season_audit = (
        complete.groupby("draft_year", as_index=False)
        .agg(
            selections=("overall_pick", "size"),
            first_pick=("overall_pick", "min"),
            final_pick=("overall_pick", "max"),
            missing_gsis_id=(
                "gsis_id",
                lambda values: int(values.isna().sum()),
            ),
            missing_pfr_id=(
                "pfr_player_id",
                lambda values: int(values.isna().sum()),
            ),
            duplicate_overall_picks=(
                "overall_pick",
                lambda values: int(values.duplicated().sum()),
            ),
        )
    )

    overlap_audit = compare_overlap(
        fresh=complete,
        existing_path=data_dir / "draft_classes_2022_2025.csv",
    )

    audit = {
        "source": DRAFT_URL,
        "output_2018_2021": str(early_path),
        "output_2018_2025": str(complete_path),
        "rows_2018_2021": int(len(early)),
        "rows_2018_2025": int(len(complete)),
        "season_audit": season_audit.to_dict(orient="records"),
        "overlap_comparison": overlap_audit,
    }

    with audit_path.open("w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2)

    print("\nCreated:")
    print(early_path)
    print(complete_path)
    print(audit_path)

    print("\nSeason audit:")
    print(season_audit.to_string(index=False))

    print("\nOverlap comparison:")
    print(json.dumps(overlap_audit, indent=2))


if __name__ == "__main__":
    main()
