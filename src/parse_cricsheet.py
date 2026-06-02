"""
Parse Cricsheet IPL ball-by-ball JSON files into a flat DataFrame.
Outputs: data/processed/ball_by_ball.parquet
"""

import json
import glob
import os
from pathlib import Path

import pandas as pd
from tqdm import tqdm

RAW_DIR = Path("data/raw/ipl_json")
PROCESSED_DIR = Path("data/processed")


def _season_year(info: dict) -> int:
    """Derive 4-digit season year from match dates (handles split labels like 2007/08)."""
    return int(info["dates"][0][:4])


def _match_stage(info: dict) -> str:
    """Normalize event stage to a clean label."""
    stage = info.get("event", {}).get("stage", "")
    if not stage:
        return "league"
    s = stage.lower()
    if "qualifier 1" in s or "qualifier1" in s:
        return "qualifier_1"
    if "qualifier 2" in s or "qualifier2" in s:
        return "qualifier_2"
    if "elimination final" in s:
        return "eliminator"
    if "eliminator" in s:
        return "eliminator"
    if "semi final" in s or "semifinal" in s:
        return "semi_final"
    if "3rd place" in s:
        return "third_place"
    if "final" in s:
        return "final"
    return "league"


def _phase(over_0idx: int) -> str:
    """over_0idx is 0-based (0=first over). PP=0-5, Middle=6-14, Death=15-19."""
    if over_0idx <= 5:
        return "powerplay"
    if over_0idx <= 14:
        return "middle"
    return "death"


def parse_match(filepath: str) -> list[dict]:
    """Parse one match JSON into a list of ball-level row dicts."""
    with open(filepath) as f:
        data = json.load(f)

    info = data["info"]
    match_id = Path(filepath).stem
    season = _season_year(info)
    date = info["dates"][0]
    stage = _match_stage(info)
    outcome = info.get("outcome", {})
    winner = outcome.get("winner")
    is_dls = outcome.get("method") == "D/L"

    teams = info.get("teams", [])

    rows = []
    for inn_idx, innings in enumerate(data.get("innings", [])):
        batting_team = innings.get("team", "")
        bowling_team = next((t for t in teams if t != batting_team), "")
        inn_num = inn_idx + 1

        # Derive batting_position: order of arrival at the crease this innings.
        # Register both striker and non_striker so a non-striking batter who
        # enters before facing a ball (e.g. an opener whose partner is dismissed
        # first) keeps their true position rather than being pushed down.
        position_map: dict[str, int] = {}
        next_pos = 1

        for over_data in innings.get("overs", []):
            over_0idx = over_data["over"]  # 0-based in Cricsheet JSON

            for ball_idx, delivery in enumerate(over_data.get("deliveries", [])):
                batter = delivery["batter"]
                bowler = delivery["bowler"]
                runs = delivery.get("runs", {})
                wickets = delivery.get("wickets", [])

                for player in (batter, delivery.get("non_striker")):
                    if player and player not in position_map:
                        position_map[player] = next_pos
                        next_pos += 1

                is_wicket = len(wickets) > 0
                wicket_kind = wickets[0]["kind"] if is_wicket else None

                extras_dict = delivery.get("extras", {})
                if "wides" in extras_dict:
                    extras_type = "wide"
                elif "noballs" in extras_dict:
                    extras_type = "noball"
                elif "byes" in extras_dict:
                    extras_type = "bye"
                elif "legbyes" in extras_dict:
                    extras_type = "legbye"
                elif "penalty" in extras_dict:
                    extras_type = "penalty"
                else:
                    extras_type = None

                rows.append({
                    "match_id": match_id,
                    "season": season,
                    "date": date,
                    "match_stage": stage,
                    "batting_team": batting_team,
                    "bowling_team": bowling_team,
                    "innings": inn_num,
                    "over": over_0idx + 1,          # store 1-based
                    "ball": ball_idx + 1,            # delivery index within over, 1-based
                    "batter": batter,
                    "bowler": bowler,
                    "runs_batter": runs.get("batter", 0),
                    "runs_extras": runs.get("extras", 0),
                    "runs_total": runs.get("total", 0),
                    "is_wicket": is_wicket,
                    "wicket_kind": wicket_kind,
                    "batting_position": position_map[batter],
                    "phase": _phase(over_0idx),
                    "extras_type": extras_type,
                    "is_dls": is_dls,
                    "winner": winner,
                })

    return rows


def parse_all(raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR) -> pd.DataFrame:
    files = sorted(glob.glob(str(raw_dir / "*.json")))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {raw_dir}")

    all_rows = []
    for fp in tqdm(files, desc="Parsing matches"):
        all_rows.extend(parse_match(fp))

    df = pd.DataFrame(all_rows)

    # Tighten dtypes
    df["season"] = df["season"].astype("int16")
    df["innings"] = df["innings"].astype("int8")
    df["over"] = df["over"].astype("int8")
    df["ball"] = df["ball"].astype("int8")
    df["runs_batter"] = df["runs_batter"].astype("int8")
    df["runs_extras"] = df["runs_extras"].astype("int8")
    df["runs_total"] = df["runs_total"].astype("int8")
    df["batting_position"] = df["batting_position"].astype("int8")
    df["is_wicket"] = df["is_wicket"].astype(bool)
    df["is_dls"] = df["is_dls"].astype(bool)
    df["phase"] = df["phase"].astype("category")
    df["extras_type"] = df["extras_type"].astype("category")
    df["match_stage"] = df["match_stage"].astype("category")

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "ball_by_ball.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Saved {len(df):,} rows → {out_path}")
    return df


if __name__ == "__main__":
    df = parse_all()
    print(df.dtypes)
    print(df.head())
