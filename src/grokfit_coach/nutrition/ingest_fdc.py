"""Ingest a full USDA FoodData Central (FDC) CSV download into the local nutrition DB.

USDA FDC is public domain (CC0). Download the bulk CSVs you want from
https://fdc.nal.usda.gov/download-datasets/ (recommended generic-food subset:
Foundation Foods + SR Legacy + FNDDS — tens of MB), unzip into one directory, then:

    python -m grokfit_coach.nutrition.ingest_fdc /path/to/fdc_csv_dir

This is intentionally a manual, offline step (no network calls here): it degrades gracefully
if the directory or files are absent, and the app still works from the committed seed.

Because USDA generic foods have NO allergen/diet fields, allergen and dietary flags are derived
from the curated keyword map (``data/seeds/nutrition/allergen_diet_map.json``). Foods that match
NO rule are stored with ``allergen_known = 0`` and are therefore excluded from allergy-restricted
plans (fail closed).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any

from grokfit_coach.config.settings import get_settings
from grokfit_coach.nutrition import food_db

# FDC nutrient ids (food_nutrient.amount is per 100 g).
_PROTEIN_ID = 1003
_FAT_ID = 1004
_CARB_ID = 1005
_ENERGY_KCAL_IDS = (1008, 2048, 2047)  # prefer 1008; Foundation data may use Atwater 2047/2048


def _map_path() -> Path:
    return get_settings().seeds_dir / "nutrition" / "allergen_diet_map.json"


def load_allergen_map(map_path: Path | str | None = None) -> list[dict[str, Any]]:
    data = json.loads(Path(map_path or _map_path()).read_text(encoding="utf-8"))
    return data.get("rules", [])


def classify(description: str, rules: list[dict[str, Any]]) -> tuple[list[str], list[str], bool]:
    """Return (allergens, diet_flags, allergen_known) for a food description via the keyword map.

    First matching rule wins. No match -> ([], [], False) i.e. UNKNOWN (fail closed downstream).
    """
    desc = description.lower()
    for rule in rules:
        if any(kw in desc for kw in rule.get("match", [])):
            return list(rule.get("allergens", [])), list(rule.get("diet", [])), True
    return [], [], False


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh)


def ingest_fdc_csv_dir(
    source_dir: Path | str,
    db_path: Path | str | None = None,
    map_path: Path | str | None = None,
    data_types: set[str] | None = None,
) -> int:
    """Ingest FDC CSVs from ``source_dir`` into the nutrition DB. Returns the food count.

    Expects ``food.csv``, ``food_nutrient.csv`` (and optionally ``food_portion.csv``).
    ``data_types`` optionally restricts which FDC data_types to import
    (e.g. {"foundation_food", "sr_legacy_food", "survey_fndds_food"}).
    """
    src = Path(source_dir)
    food_csv = src / "food.csv"
    nutrient_csv = src / "food_nutrient.csv"
    if not food_csv.exists() or not nutrient_csv.exists():
        raise FileNotFoundError(
            f"FDC CSVs not found in {src} (need food.csv and food_nutrient.csv). "
            f"Download from https://fdc.nal.usda.gov/download-datasets/ and unzip there."
        )

    rules = load_allergen_map(map_path)

    # 1) foods
    foods: dict[int, dict[str, str]] = {}
    for row in _read_csv(food_csv):
        try:
            fid = int(row["fdc_id"])
        except (KeyError, ValueError):
            continue
        dtype = (row.get("data_type") or "").strip()
        if data_types and dtype not in data_types:
            continue
        foods[fid] = {"description": (row.get("description") or "").strip(), "data_type": dtype}

    # 2) nutrients (accumulate macros per food)
    macros: dict[int, dict[str, float]] = {}
    for row in _read_csv(nutrient_csv):
        try:
            fid = int(row["fdc_id"])
            nid = int(row["nutrient_id"])
            amount = float(row["amount"]) if row.get("amount") not in (None, "") else 0.0
        except (KeyError, ValueError):
            continue
        if fid not in foods:
            continue
        m = macros.setdefault(fid, {})
        if nid == _PROTEIN_ID:
            m["protein_g"] = amount
        elif nid == _FAT_ID:
            m["fat_g"] = amount
        elif nid == _CARB_ID:
            m["carbs_g"] = amount
        elif nid in _ENERGY_KCAL_IDS:
            # prefer 1008; only overwrite if not already set by the preferred id
            if "calories" not in m or nid == _ENERGY_KCAL_IDS[0]:
                m["calories"] = amount

    # 3) portions (optional)
    portions: dict[int, list[dict[str, Any]]] = {}
    portion_csv = src / "food_portion.csv"
    if portion_csv.exists():
        for row in _read_csv(portion_csv):
            try:
                fid = int(row["fdc_id"])
                grams = float(row["gram_weight"]) if row.get("gram_weight") not in (None, "") else 0.0
            except (KeyError, ValueError):
                continue
            if fid not in foods or grams <= 0:
                continue
            desc = (row.get("portion_description") or row.get("modifier") or "").strip()
            portions.setdefault(fid, []).append({"grams": grams, "description": desc})

    # 4) write
    conn = food_db._connect(db_path)
    try:
        for fid, info in foods.items():
            m = macros.get(fid, {})
            allergens, diet, known = classify(info["description"], rules)
            food_db._insert_food(
                conn,
                fdc_id=fid,
                description=info["description"],
                data_type=info["data_type"] or "usda_fdc",
                calories=m.get("calories", 0.0),
                protein_g=m.get("protein_g", 0.0),
                carbs_g=m.get("carbs_g", 0.0),
                fat_g=m.get("fat_g", 0.0),
                allergens=allergens,
                diet=diet,
                portions=portions.get(fid, []),
                allergen_known=known,
            )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('dataset', ?), ('version', ?)",
            ("USDA FoodData Central (ingested)", f"fdc-import:{src.name}"),
        )
        conn.commit()
        return conn.execute("SELECT COUNT(*) AS c FROM food").fetchone()["c"]
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m grokfit_coach.nutrition.ingest_fdc <fdc_csv_dir>", file=sys.stderr)
        print("Download CSVs from https://fdc.nal.usda.gov/download-datasets/ first.", file=sys.stderr)
        return 2
    try:
        count = ingest_fdc_csv_dir(args[0])
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Ingested {count} foods into the local nutrition DB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
