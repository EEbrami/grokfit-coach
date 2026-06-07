"""Hermetic tests for the local nutrition DB + FDC ingest (M3). Uses tmp DBs + committed seed/map."""

from __future__ import annotations

from grokfit_coach.models import FoodItem
from grokfit_coach.nutrition import food_db, ingest_fdc


def test_build_from_seed_populates(tmp_path):
    p = tmp_path / "n.sqlite"
    count = food_db.build_from_seed(db_path=p)
    assert count >= 14
    # idempotent
    assert food_db.build_from_seed(db_path=p) == count


def test_search_finds_chicken(tmp_path):
    p = tmp_path / "n.sqlite"
    results = food_db.search_foods("chicken", db_path=p)
    assert results and "chicken" in results[0].name.lower()
    assert results[0].calories > 0


def test_allergen_filter_excludes_milk_failclosed(tmp_path):
    p = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=p)
    items = food_db.filter_foods(allergens=["milk"], db_path=p)
    names = " ".join(i.name.lower() for i in items)
    assert "yogurt" not in names and "milk" not in names  # milk foods excluded
    assert any("chicken" in i.name.lower() or "oats" in i.name.lower() for i in items)  # safe foods remain


def test_allergen_synonyms_normalized(tmp_path):
    p = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=p)
    # "dairy" must map to "milk", "nuts" to "tree_nut", "gluten" to "wheat"
    assert food_db.normalize_allergen("Dairy") == "milk"
    assert food_db.normalize_allergen("nuts") == "tree_nut"
    assert food_db.normalize_allergen("gluten") == "wheat"
    items = food_db.filter_foods(allergens=["dairy"], db_path=p)
    assert all("milk" not in i.allergen_flags for i in items)


def test_failclosed_excludes_unknown_food(tmp_path):
    p = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=p)
    # inject a food with UNKNOWN allergen status
    conn = food_db._connect(p)
    try:
        food_db._insert_food(
            conn,
            fdc_id=999999,
            description="Mystery ration bar",
            data_type="seed",
            calories=300,
            protein_g=10,
            carbs_g=40,
            fat_g=10,
            allergens=[],
            diet=[],
            portions=[],
            allergen_known=False,  # unknown
        )
        conn.commit()
    finally:
        conn.close()
    # with an allergy active, the unknown food must NOT appear (fail closed)
    items = food_db.filter_foods(allergens=["peanut"], db_path=p)
    assert all(i.name != "Mystery ration bar" for i in items)
    # with NO allergy, unknown foods are allowed
    items_no_allergy = food_db.filter_foods(allergens=[], db_path=p)
    assert any(i.name == "Mystery ration bar" for i in items_no_allergy)


def test_vegan_diet_filter(tmp_path):
    p = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=p)
    items = food_db.filter_foods(dietary_pattern="vegan", db_path=p)
    names = " ".join(i.name.lower() for i in items)
    assert "chicken" not in names and "salmon" not in names and "egg" not in names and "yogurt" not in names
    assert any("oats" in i.name.lower() or "lentils" in i.name.lower() for i in items)


def test_macros_for_grams_scaling():
    item = FoodItem(name="x", calories=200, protein_g=20, carbs_g=10, fat_g=5)
    out = food_db.macros_for_grams(item, 50)
    assert out["calories"] == 100.0 and out["protein_g"] == 10.0


def test_classify_keyword_map():
    rules = ingest_fdc.load_allergen_map()
    a, d, known = ingest_fdc.classify("Cheddar cheese", rules)
    assert known and "milk" in a and "vegetarian" in d
    a2, d2, known2 = ingest_fdc.classify("Zorblax nutrient paste", rules)
    assert known2 is False and a2 == [] and d2 == []


def test_ingest_fdc_csv_dir(tmp_path):
    src = tmp_path / "fdc"
    src.mkdir()
    (src / "food.csv").write_text(
        "fdc_id,data_type,description\n"
        "111,sr_legacy_food,Cheddar cheese\n"
        "112,sr_legacy_food,\"Apple, raw\"\n"
        "113,sr_legacy_food,Zorblax nutrient paste\n",
        encoding="utf-8",
    )
    (src / "food_nutrient.csv").write_text(
        "fdc_id,nutrient_id,amount\n"
        "111,1008,403\n111,1003,25\n111,1004,33\n111,1005,1.3\n"
        "112,1008,52\n112,1003,0.3\n112,1004,0.2\n112,1005,14\n"
        "113,1008,100\n113,1003,5\n113,1004,1\n113,1005,10\n",
        encoding="utf-8",
    )
    db = tmp_path / "n.sqlite"
    count = ingest_fdc.ingest_fdc_csv_dir(src, db_path=db)
    assert count == 3

    cheese = food_db.get_food(111, db_path=db)
    assert cheese is not None and cheese.calories == 403 and "milk" in cheese.allergen_flags

    # allergic-to-milk: cheese excluded, apple (known, safe) included, zorblax (unknown) excluded
    items = food_db.filter_foods(allergens=["milk"], db_path=db)
    names = {i.name for i in items}
    assert "Cheddar cheese" not in names
    assert "Apple, raw" in names
    assert "Zorblax nutrient paste" not in names
