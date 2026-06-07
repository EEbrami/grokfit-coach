"""Local nutrition database: food -> nutrients, with deterministic, fail-closed filtering.

- Macros are stored **per 100 g** (the USDA FoodData Central basis) as the single source of truth.
- Allergen and dietary filtering is **pure SQL on structured tables**, never embedding similarity.
- Allergen filtering is **fail-closed**: a food passes only if it is positively known to be free
  of every listed allergen (``allergen_known = 1`` AND none of the user's allergens present).
  Foods with unknown allergen status are excluded from allergy-restricted results.

The DB is built offline from the committed seed (``data/seeds/nutrition/seed_foods.json``) on
first use, so the app works out of the box; a full USDA FDC download can be ingested on top
(see ``ingest_fdc``).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from grokfit_coach.config.settings import get_settings
from grokfit_coach.models import FoodItem

SCHEMA = """
CREATE TABLE IF NOT EXISTS food (
    fdc_id         INTEGER PRIMARY KEY,
    description    TEXT NOT NULL,
    data_type      TEXT,
    calories       REAL DEFAULT 0,
    protein_g      REAL DEFAULT 0,
    carbs_g        REAL DEFAULT 0,
    fat_g          REAL DEFAULT 0,
    allergen_known INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS food_portion (fdc_id INTEGER, grams REAL, description TEXT);
CREATE TABLE IF NOT EXISTS food_allergen (fdc_id INTEGER, allergen TEXT);
CREATE TABLE IF NOT EXISTS food_diet (fdc_id INTEGER, diet TEXT);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX IF NOT EXISTS idx_food_allergen ON food_allergen(allergen);
CREATE INDEX IF NOT EXISTS idx_food_diet ON food_diet(diet);
"""

# Map common user phrasings to our canonical (big-9) allergen vocabulary. Safety-critical:
# without this, "dairy" would not match stored "milk" and dairy foods would wrongly pass.
_ALLERGEN_SYNONYMS = {
    "dairy": "milk",
    "lactose": "milk",
    "milk": "milk",
    "egg": "egg",
    "eggs": "egg",
    "peanut": "peanut",
    "peanuts": "peanut",
    "groundnut": "peanut",
    "nut": "tree_nut",
    "nuts": "tree_nut",
    "tree nut": "tree_nut",
    "tree nuts": "tree_nut",
    "tree_nut": "tree_nut",
    "treenut": "tree_nut",
    "soy": "soy",
    "soya": "soy",
    "soybean": "soy",
    "wheat": "wheat",
    "gluten": "wheat",
    "fish": "fish",
    "shellfish": "shellfish",
    "crustacean": "shellfish",
    "sesame": "sesame",
}

# Dietary pattern -> the set of diet tags a food must carry to be allowed.
# (Vegan foods are tagged both 'vegan' and 'vegetarian'; fish 'pescatarian'.)
_DIET_REQUIRED = {
    "vegan": ["vegan"],
    "vegetarian": ["vegetarian"],
    "pescatarian": ["vegetarian", "pescatarian"],
}


def normalize_allergen(a: str) -> str:
    """Normalize a user-provided allergen to our canonical vocabulary (best effort)."""
    key = a.strip().lower()
    return _ALLERGEN_SYNONYMS.get(key, key)


def diet_required_for(dietary_pattern: str | None) -> list[str] | None:
    """Return the diet tags required for a pattern, or None for no dietary filter."""
    if not dietary_pattern:
        return None
    return _DIET_REQUIRED.get(dietary_pattern.lower())


# --------------------------------------------------------------------------- #
# Paths / connection / build
# --------------------------------------------------------------------------- #
def _resolve_path(db_path: Path | str | None) -> Path:
    return Path(db_path) if db_path is not None else get_settings().nutrition_db_path


def _seed_path() -> Path:
    return get_settings().seeds_dir / "nutrition" / "seed_foods.json"


def _connect(db_path: Path | str | None) -> sqlite3.Connection:
    path = _resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _count_foods(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM food").fetchone()["c"]


def build_from_seed(
    db_path: Path | str | None = None,
    seed_path: Path | str | None = None,
    force: bool = False,
) -> int:
    """Build the nutrition DB from the committed JSON seed. Idempotent. Returns food count."""
    conn = _connect(db_path)
    try:
        if not force and _count_foods(conn) > 0:
            return _count_foods(conn)
        if force:
            for t in ("food", "food_portion", "food_allergen", "food_diet"):
                conn.execute(f"DELETE FROM {t}")
        seed = json.loads(Path(seed_path or _seed_path()).read_text(encoding="utf-8"))
        for f in seed.get("foods", []):
            _insert_food(
                conn,
                fdc_id=int(f["fdc_id"]),
                description=f["description"],
                data_type=f.get("data_type", "seed"),
                calories=float(f.get("calories", 0)),
                protein_g=float(f.get("protein_g", 0)),
                carbs_g=float(f.get("carbs_g", 0)),
                fat_g=float(f.get("fat_g", 0)),
                allergens=f.get("allergens", []),
                diet=f.get("diet", []),
                portions=f.get("portions", []),
                allergen_known=True,  # seed foods are curated/reviewed
            )
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('dataset', ?), ('version', ?)",
            (seed.get("dataset", "grokfit-seed"), seed.get("version", "seed")),
        )
        conn.commit()
        return _count_foods(conn)
    finally:
        conn.close()


def _insert_food(
    conn: sqlite3.Connection,
    *,
    fdc_id: int,
    description: str,
    data_type: str,
    calories: float,
    protein_g: float,
    carbs_g: float,
    fat_g: float,
    allergens: list[str],
    diet: list[str],
    portions: list[dict[str, Any]],
    allergen_known: bool,
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO food (fdc_id, description, data_type, calories, protein_g, carbs_g, fat_g, allergen_known) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (fdc_id, description, data_type, calories, protein_g, carbs_g, fat_g, 1 if allergen_known else 0),
    )
    conn.execute("DELETE FROM food_allergen WHERE fdc_id = ?", (fdc_id,))
    conn.execute("DELETE FROM food_diet WHERE fdc_id = ?", (fdc_id,))
    conn.execute("DELETE FROM food_portion WHERE fdc_id = ?", (fdc_id,))
    for a in allergens:
        conn.execute("INSERT INTO food_allergen (fdc_id, allergen) VALUES (?, ?)", (fdc_id, a.strip().lower()))
    for d in diet:
        conn.execute("INSERT INTO food_diet (fdc_id, diet) VALUES (?, ?)", (fdc_id, d.strip().lower()))
    for p in portions:
        conn.execute(
            "INSERT INTO food_portion (fdc_id, grams, description) VALUES (?, ?, ?)",
            (fdc_id, float(p.get("grams", 0)), p.get("description", "")),
        )


def ensure_db(db_path: Path | str | None = None) -> Path:
    """Ensure the nutrition DB exists and is populated (build from seed if empty)."""
    path = _resolve_path(db_path)
    conn = _connect(db_path)
    try:
        empty = _count_foods(conn) == 0
    finally:
        conn.close()
    if empty:
        build_from_seed(db_path)
    return path


# --------------------------------------------------------------------------- #
# Query / filter
# --------------------------------------------------------------------------- #
def _build_item(conn: sqlite3.Connection, fdc_id: int) -> FoodItem | None:
    row = conn.execute("SELECT * FROM food WHERE fdc_id = ?", (fdc_id,)).fetchone()
    if not row:
        return None
    allergens = [r["allergen"] for r in conn.execute("SELECT allergen FROM food_allergen WHERE fdc_id = ?", (fdc_id,))]
    diet = [r["diet"] for r in conn.execute("SELECT diet FROM food_diet WHERE fdc_id = ?", (fdc_id,))]
    return FoodItem(
        name=row["description"],
        calories=row["calories"],
        protein_g=row["protein_g"],
        carbs_g=row["carbs_g"],
        fat_g=row["fat_g"],
        serving_desc="100g",
        source=row["data_type"] or "usda_fdc",
        fdc_id=row["fdc_id"],
        grams=100.0,
        diet_flags=diet,
        allergen_flags=allergens,
    )


def search_foods(query: str, limit: int = 10, db_path: Path | str | None = None) -> list[FoodItem]:
    """Token-AND substring search over food descriptions (deterministic name lookup)."""
    ensure_db(db_path)
    conn = _connect(db_path)
    try:
        tokens = [t for t in query.lower().split() if t]
        sql = "SELECT fdc_id FROM food"
        params: list[Any] = []
        if tokens:
            sql += " WHERE " + " AND ".join(["lower(description) LIKE ?"] * len(tokens))
            params += [f"%{t}%" for t in tokens]
        sql += " ORDER BY length(description) LIMIT ?"
        params.append(limit)
        ids = [r["fdc_id"] for r in conn.execute(sql, params)]
        return [item for fid in ids if (item := _build_item(conn, fid))]
    finally:
        conn.close()


def filter_foods(
    allergens: list[str] | None = None,
    dietary_pattern: str | None = None,
    query: str | None = None,
    limit: int = 25,
    db_path: Path | str | None = None,
) -> list[FoodItem]:
    """Return foods passing FAIL-CLOSED allergen exclusion + dietary-pattern filter (pure SQL)."""
    ensure_db(db_path)
    conn = _connect(db_path)
    try:
        where: list[str] = []
        params: list[Any] = []

        norm_allergens = sorted({normalize_allergen(a) for a in (allergens or []) if a and a.strip()})
        if norm_allergens:
            ph = ",".join(["?"] * len(norm_allergens))
            # fail closed: must be reviewed AND free of every listed allergen
            where.append(
                f"(food.allergen_known = 1 AND food.fdc_id NOT IN "
                f"(SELECT fdc_id FROM food_allergen WHERE lower(allergen) IN ({ph})))"
            )
            params += norm_allergens

        diet_required = diet_required_for(dietary_pattern)
        if diet_required:
            ph = ",".join(["?"] * len(diet_required))
            where.append(f"food.fdc_id IN (SELECT fdc_id FROM food_diet WHERE diet IN ({ph}))")
            params += diet_required

        if query:
            for tok in query.lower().split():
                where.append("lower(food.description) LIKE ?")
                params.append(f"%{tok}%")

        sql = "SELECT fdc_id FROM food"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY length(description) LIMIT ?"
        params.append(limit)
        ids = [r["fdc_id"] for r in conn.execute(sql, params)]
        return [item for fid in ids if (item := _build_item(conn, fid))]
    finally:
        conn.close()


def get_food(fdc_id: int, db_path: Path | str | None = None) -> FoodItem | None:
    ensure_db(db_path)
    conn = _connect(db_path)
    try:
        return _build_item(conn, fdc_id)
    finally:
        conn.close()


def macros_for_grams(item: FoodItem, grams: float) -> dict[str, float]:
    """Scale a per-100g FoodItem to a given gram portion."""
    factor = grams / 100.0
    return {
        "calories": round(item.calories * factor, 1),
        "protein_g": round(item.protein_g * factor, 1),
        "carbs_g": round(item.carbs_g * factor, 1),
        "fat_g": round(item.fat_g * factor, 1),
    }
