from flask import Blueprint, jsonify, request
import pandas as pd
import re
from difflib import SequenceMatcher

bp = Blueprint("bp", __name__)

DATA_PATH = "../data/recipes_enriched.csv"

def norm_text(value):
    return str(value or "").lower().strip()

def tokenize(value):
    return set(re.findall(r"[a-z0-9]+", norm_text(value)))

def similarity_score(query, title, ner=""):
    q = norm_text(query)
    t = norm_text(title)
    n = norm_text(ner)

    if not q:
        return 0.0

    seq_title = SequenceMatcher(None, q, t).ratio()
    seq_ner = SequenceMatcher(None, q, n).ratio() if n else 0.0

    q_tokens = tokenize(q)
    t_tokens = tokenize(t)
    n_tokens = tokenize(n)

    overlap_title = len(q_tokens & t_tokens) / max(len(q_tokens), 1)
    overlap_ner = len(q_tokens & n_tokens) / max(len(q_tokens), 1)

    score = max(
        0.65 * seq_title + 0.35 * overlap_title,
        0.55 * seq_ner + 0.45 * overlap_ner
    )

    return round(score * 100, 1)

def load_data():
    df = pd.read_csv(DATA_PATH).fillna("")
    if "title" in df.columns:
        df["normalized_title"] = (
            df["title"].astype(str)
            .str.lower()
            .str.replace(r'["“”‘’!?,.:;()\[\]{}]+', "", regex=True)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )
        df = df.drop_duplicates(subset=["normalized_title"])
    return df.fillna("")

DF = load_data()

def first_nonempty(row, keys):
    for key in keys:
        value = row.get(key, "")
        if str(value).strip() != "":
            return value
    return None

def add_final_nutrition_columns(df):
    df = df.copy()
    df["final_calories"] = df.apply(lambda row: first_nonempty(row, ["clean_calories", "estimated_calories"]), axis=1)
    df["final_protein_g"] = df.apply(lambda row: first_nonempty(row, ["protein_g", "estimated_protein_g"]), axis=1)
    df["final_carbs_g"] = df.apply(lambda row: first_nonempty(row, ["carbs_g", "estimated_carbs_g"]), axis=1)
    df["final_fat_g"] = df.apply(lambda row: first_nonempty(row, ["fat_g", "estimated_fat_g"]), axis=1)
    df["final_fiber_g"] = df.apply(lambda row: first_nonempty(row, ["fiber_g", "estimated_fiber_g"]), axis=1)
    df["final_sodium_mg"] = df.apply(lambda row: first_nonempty(row, ["sodium_mg", "estimated_sodium_mg"]), axis=1)
    df["final_servings"] = df.apply(lambda row: first_nonempty(row, ["servings", "estimated_servings"]), axis=1)
    return df

def nutrition_status_for_row(row):
    has_estimated = any(str(row.get(col, "")).strip() != "" for col in [
        "estimated_calories", "estimated_protein_g", "estimated_carbs_g",
        "estimated_fat_g", "estimated_fiber_g", "estimated_sodium_mg"
    ])
    has_parsed = any(str(row.get(col, "")).strip() != "" for col in [
        "clean_calories", "protein_g", "carbs_g", "fat_g", "fiber_g", "sodium_mg"
    ])

    if has_parsed:
        return "Parsed + estimated"
    if has_estimated:
        return "Estimated nutrition"
    return "Limited nutrition data"

def add_sort_scores(df):
    df = df.copy()
    df["_cal"] = pd.to_numeric(df["final_calories"], errors="coerce")
    df["_protein"] = pd.to_numeric(df["final_protein_g"], errors="coerce")
    df["_carbs"] = pd.to_numeric(df["final_carbs_g"], errors="coerce")
    df["_fat"] = pd.to_numeric(df["final_fat_g"], errors="coerce")
    df["_fiber"] = pd.to_numeric(df["final_fiber_g"], errors="coerce")
    df["_sodium"] = pd.to_numeric(df["final_sodium_mg"], errors="coerce")

    df["_keto_score"] = (
        df["_protein"].fillna(0) * 1.2
        + df["_fat"].fillna(0) * 1.0
        - df["_carbs"].fillna(0) * 2.5
        - df["_sodium"].fillna(0) / 1000.0
    )

    df["_balanced_score"] = (
        df["_protein"].fillna(0) * 1.0
        + df["_fiber"].fillna(0) * 1.0
        - df["_cal"].fillna(0) / 200.0
        - df["_sodium"].fillna(0) / 800.0
        - df["_fat"].fillna(0) / 25.0
    )

    df["_bodybuilding_score"] = (
        df["_protein"].fillna(0) * 2.0
        - df["_cal"].fillna(0) / 250.0
        - df["_sodium"].fillna(0) / 1200.0
    )

    df["_vegan_score"] = (
        df["_fiber"].fillna(0) * 2.0
        + df["_carbs"].fillna(0) * 0.3
        - df["_fat"].fillna(0) * 0.3
        - df["_sodium"].fillna(0) / 1200.0
    )
    return df

def sort_for_profile(df, profile):
    df = add_final_nutrition_columns(df)
    df = add_sort_scores(df)

    df["nutrition_available"] = df.apply(
        lambda row: any(str(row.get(col, "")).strip() != "" for col in [
            "final_calories", "final_protein_g", "final_carbs_g",
            "final_fat_g", "final_fiber_g", "final_sodium_mg"
        ]),
        axis=1
    )

    if profile == "low_calorie":
        return df.sort_values(["nutrition_available", "_cal", "similarity_score"], ascending=[False, True, False])
    if profile == "high_protein":
        return df.sort_values(["nutrition_available", "_protein", "similarity_score"], ascending=[False, False, False])
    if profile == "bodybuilding":
        return df.sort_values(["nutrition_available", "_bodybuilding_score", "similarity_score"], ascending=[False, False, False])
    if profile == "low_carb":
        return df.sort_values(["nutrition_available", "_carbs", "similarity_score"], ascending=[False, True, False])
    if profile == "low_fat":
        return df.sort_values(["nutrition_available", "_fat", "similarity_score"], ascending=[False, True, False])
    if profile == "low_sodium":
        return df.sort_values(["nutrition_available", "_sodium", "similarity_score"], ascending=[False, True, False])
    if profile == "keto":
        return df.sort_values(["nutrition_available", "_keto_score", "similarity_score"], ascending=[False, False, False])
    if profile == "balanced":
        return df.sort_values(["nutrition_available", "_balanced_score", "similarity_score"], ascending=[False, False, False])
    if profile == "vegan":
        return df.sort_values(["nutrition_available", "_vegan_score", "similarity_score"], ascending=[False, False, False])

    return df.sort_values(["nutrition_available", "similarity_score", "title"], ascending=[False, False, True])

@bp.route("/mealmap/matches")
def matches():
    query = request.args.get("query", "").strip()
    profile = request.args.get("profile", "none").strip().lower()

    if not query:
        return jsonify({"matches": []})

    df = DF.copy()

    title_mask = df["title"].astype(str).str.lower().str.contains(query.lower(), na=False)
    ner_mask = df["NER"].astype(str).str.lower().str.contains(query.lower(), na=False) if "NER" in df.columns else False
    ingredient_mask = df["ingredients"].astype(str).str.lower().str.contains(query.lower(), na=False) if "ingredients" in df.columns else False

    filtered = df[title_mask | ner_mask | ingredient_mask].copy()

    if filtered.empty:
        return jsonify({"matches": []})

    filtered["similarity_score"] = filtered.apply(
        lambda row: similarity_score(query, row.get("title", ""), row.get("NER", "")),
        axis=1
    )

    filtered = sort_for_profile(filtered, profile)

    matches = []
    for _, row in filtered.head(12).iterrows():
        matches.append({
            "title": row.get("title", ""),
            "calories": row.get("final_calories", None),
            "protein_g": row.get("final_protein_g", None),
            "carbs_g": row.get("final_carbs_g", None),
            "fat_g": row.get("final_fat_g", None),
            "fiber_g": row.get("final_fiber_g", None),
            "sodium_mg": row.get("final_sodium_mg", None),
            "servings": row.get("final_servings", None),
            "similarity_score": row.get("similarity_score", 0),
            "nutrition_status": nutrition_status_for_row(row)
        })

    return jsonify({"matches": matches})

@bp.route("/mealmap/recommend")
def recommend():
    selected = request.args.get("selected", "").strip()
    profile = request.args.get("profile", "none").strip().lower()

    if not selected:
        return jsonify({"recipes": []})

    df = DF.copy()

    title_mask = df["title"].astype(str).str.lower().str.contains(selected.lower(), na=False)
    ner_mask = df["NER"].astype(str).str.lower().str.contains(selected.lower(), na=False) if "NER" in df.columns else False
    ingredient_mask = df["ingredients"].astype(str).str.lower().str.contains(selected.lower(), na=False) if "ingredients" in df.columns else False

    results_df = df[title_mask | ner_mask | ingredient_mask].copy()

    if results_df.empty:
        return jsonify({"recipes": []})

    results_df["similarity_score"] = results_df.apply(
        lambda row: similarity_score(selected, row.get("title", ""), row.get("NER", "")),
        axis=1
    )

    results_df = sort_for_profile(results_df, profile)

    recipes = []
    for _, row in results_df.head(50).iterrows():
        recipes.append({
            "title": row.get("title", ""),
            "ingredients": row.get("ingredients", ""),
            "directions": row.get("directions", ""),
            "link": row.get("link", ""),
            "source": row.get("source", ""),
            "site": row.get("site", ""),
            "calories": row.get("final_calories", None),
            "protein_g": row.get("final_protein_g", None),
            "carbs_g": row.get("final_carbs_g", None),
            "fat_g": row.get("final_fat_g", None),
            "fiber_g": row.get("final_fiber_g", None),
            "sodium_mg": row.get("final_sodium_mg", None),
            "servings": row.get("final_servings", None),
            "similarity_score": row.get("similarity_score", 0),
            "nutrition_status": nutrition_status_for_row(row),
            "nutrition_confidence": row.get("nutrition_confidence", None),
            "matched_ingredient_keywords": row.get("matched_ingredient_keywords", ""),
            "diet": profile if profile != "none" else ""
        })

    return jsonify({"recipes": recipes})

def register_routes(app):
    app.register_blueprint(bp)
