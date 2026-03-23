import os
import pandas as pd
from flask import jsonify, request, render_template
from MealMap.mealmap_precompute import (
    build_ingredient_index,
    find_matching_dishes,
    get_similar_by_ingredients,
    DIETARY_PROFILES,
    rerank,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "MealMap", "recipes_with_nutrition.csv")
DEFAULT_TOP_K = 50
DEFAULT_RESULTS = 10

def register_routes(app):
    @app.route("/")
    def home():
        return render_template("base.html")

    @app.route("/recipes", methods=["GET"])
    def get_recipes():
        df = pd.read_csv(CSV_PATH)
        df = df.fillna("")

        query = request.args.get("query", "").strip().lower()
        diet = request.args.get("diet", "").strip().lower()

        title_col = "title" if "title" in df.columns else ("name" if "name" in df.columns else None)

        if query and title_col:
            df = df[df[title_col].astype(str).str.lower().str.contains(query, na=False)]

        if diet:
            if "diet" in df.columns:
                df = df[df["diet"].astype(str).str.lower().str.contains(diet, na=False)]
            elif "tags" in df.columns:
                df = df[df["tags"].astype(str).str.lower().str.contains(diet, na=False)]

        results = df.head(30).to_dict(orient="records")
        return jsonify(results)

    @app.route("/mealmap/matches", methods=["GET"])
    def mealmap_matches():
        query = request.args.get("query", "").strip()
        if not query:
            return jsonify({"matches": []})

        df = pd.read_csv(CSV_PATH).fillna("")
        name_ingredient_map = build_ingredient_index(df)
        matches = find_matching_dishes(query, name_ingredient_map)[:10]
        return jsonify({"matches": matches})

    @app.route("/mealmap/recommend", methods=["GET"])
    def mealmap_recommend():
        selected = request.args.get("selected", "").strip()
        if not selected:
            return jsonify({"error": "selected is required"}), 400

        profile_name = request.args.get("profile", "none").strip().lower().replace("-", "_")
        if profile_name not in DIETARY_PROFILES:
            profile_name = "none"

        top_k = request.args.get("top_k", type=int) or DEFAULT_TOP_K
        num_results = request.args.get("results", type=int) or DEFAULT_RESULTS

        df = pd.read_csv(CSV_PATH).fillna("")
        name_ingredient_map = build_ingredient_index(df)
        if selected not in name_ingredient_map:
            return jsonify({"recipes": []})

        similar = get_similar_by_ingredients(selected, name_ingredient_map, top_k)
        nutrition_lookup = (
            df.drop_duplicates(subset="title")
            .set_index("title")
            .to_dict("index")
        )

        if profile_name == "none":
            ordered_titles = [title for _, title in similar[:num_results]]
        else:
            reranked = rerank(
                similar_recipes=similar,
                df=df,
                profile=DIETARY_PROFILES[profile_name],
                num_results=num_results,
            )
            ordered_titles = [row["title"] for row in reranked]

        recipes = []
        for title in ordered_titles:
            row = nutrition_lookup.get(title)
            if not row:
                continue
            record = {"title": title, **row}
            recipes.append(record)

        return jsonify({"recipes": recipes, "profile": profile_name})
