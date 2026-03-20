import os
import pandas as pd
from flask import jsonify, request, render_template

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "MealMap", "recipes_with_nutrition.csv")

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
