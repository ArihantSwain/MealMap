from pathlib import Path
import ast
import re

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

bp = Blueprint("bp", __name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "recipes_enriched.csv"

SEARCH_LIMIT = 12
RECOMMEND_LIMIT = 24
DEFAULT_MODEL = "svd"

DF = None

TFIDF_VECTORIZER = None
TFIDF_MATRIX = None

SVD_COMPONENTS = 0
SVD_MODEL = None
SVD_MATRIX = None
SVD_VARIANCE = 0.0

RECOMMEND_TFIDF_VECTORIZER = None
RECOMMEND_TFIDF_MATRIX = None

RECOMMEND_SVD_COMPONENTS = 0
RECOMMEND_SVD_MODEL = None
RECOMMEND_SVD_MATRIX = None
RECOMMEND_SVD_VARIANCE = 0.0

def normalize_text(value):
    text = str(value or "").lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def tokenize(value):
    return set(normalize_text(value).split())


def parse_listish(value):
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    text = str(value).strip()
    if not text:
        return []

    try:
        parsed = ast.literal_eval(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except Exception:
        pass

    pieces = re.split(r",\s*(?=(?:[^']*'[^']*')*[^']*$)", text)
    return [piece.strip(" '\"") for piece in pieces if piece.strip(" '\"")]


def safe_float(value):
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def first_present(row, keys):
    for key in keys:
        value = row.get(key, "")
        if str(value).strip() != "":
            return value
    return None


def nutrition_status_for_row(row):
    estimated_cols = [
        "estimated_calories",
        "estimated_protein_g",
        "estimated_carbs_g",
        "estimated_fat_g",
        "estimated_fiber_g",
        "estimated_sodium_mg",
    ]
    parsed_cols = [
        "clean_calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "sodium_mg",
    ]

    has_estimated = any(str(row.get(col, "")).strip() != "" for col in estimated_cols)
    has_parsed = any(str(row.get(col, "")).strip() != "" for col in parsed_cols)

    if has_parsed and has_estimated:
        return "Parsed + estimated"
    if has_parsed:
        return "Parsed nutrition"
    if has_estimated:
        return "Estimated nutrition"
    return "Limited nutrition data"


def add_final_columns(df):
    df = df.copy()

    df["final_calories"] = df.apply(
        lambda row: first_present(row, ["clean_calories", "estimated_calories", "calories"]),
        axis=1,
    )
    df["final_protein_g"] = df.apply(
        lambda row: first_present(row, ["protein_g", "estimated_protein_g"]),
        axis=1,
    )
    df["final_carbs_g"] = df.apply(
        lambda row: first_present(row, ["carbs_g", "estimated_carbs_g"]),
        axis=1,
    )
    df["final_fat_g"] = df.apply(
        lambda row: first_present(row, ["fat_g", "estimated_fat_g"]),
        axis=1,
    )
    df["final_fiber_g"] = df.apply(
        lambda row: first_present(row, ["fiber_g", "estimated_fiber_g"]),
        axis=1,
    )
    df["final_sodium_mg"] = df.apply(
        lambda row: first_present(row, ["sodium_mg", "estimated_sodium_mg"]),
        axis=1,
    )
    df["final_servings"] = df.apply(
        lambda row: first_present(row, ["servings", "estimated_servings"]),
        axis=1,
    )

    df["_cal"] = pd.to_numeric(df["final_calories"], errors="coerce")
    df["_protein"] = pd.to_numeric(df["final_protein_g"], errors="coerce")
    df["_carbs"] = pd.to_numeric(df["final_carbs_g"], errors="coerce")
    df["_fat"] = pd.to_numeric(df["final_fat_g"], errors="coerce")
    df["_fiber"] = pd.to_numeric(df["final_fiber_g"], errors="coerce")
    df["_sodium"] = pd.to_numeric(df["final_sodium_mg"], errors="coerce")
    df["_servings"] = pd.to_numeric(df["final_servings"], errors="coerce")

    df["nutrition_available"] = (
        df[
            [
                "final_calories",
                "final_protein_g",
                "final_carbs_g",
                "final_fat_g",
                "final_fiber_g",
                "final_sodium_mg",
            ]
        ]
        .astype(str)
        .apply(lambda row: any(item.strip() not in {"", "nan", "None"} for item in row), axis=1)
    )

    df["_keto_score"] = (
        df["_protein"].fillna(0) * 1.3
        + df["_fat"].fillna(0) * 1.1
        - df["_carbs"].fillna(0) * 2.8
        - df["_sodium"].fillna(0) / 1200.0
    )

    df["_balanced_score"] = (
        df["_protein"].fillna(0) * 1.2
        + df["_fiber"].fillna(0) * 1.4
        - df["_cal"].fillna(0) / 180.0
        - df["_fat"].fillna(0) / 20.0
        - df["_sodium"].fillna(0) / 900.0
    )

    df["_bodybuilding_score"] = (
        df["_protein"].fillna(0) * 2.2
        + df["_servings"].fillna(0) * 0.2
        - df["_sodium"].fillna(0) / 1500.0
        - df["_cal"].fillna(0) / 260.0
    )

    df["_vegan_score"] = (
        df["_fiber"].fillna(0) * 2.0
        + df["_carbs"].fillna(0) * 0.2
        - df["_fat"].fillna(0) * 0.25
        - df["_sodium"].fillna(0) / 1200.0
    )

    return df


def load_data():
    data_path = DATA_PATH
    df = pd.read_csv(data_path).fillna("")

    expected = ["title", "ingredients", "directions", "link", "source", "site", "NER"]
    for col in expected:
        if col not in df.columns:
            df[col] = ""

    df["title"] = df["title"].astype(str)
    df["ingredients"] = df["ingredients"].astype(str)
    df["directions"] = df["directions"].astype(str)
    df["NER"] = df["NER"].astype(str)
    df["ingredients_joined"] = df["ingredients"].apply(lambda x: " ".join(parse_listish(x))).map(normalize_text)
    df["directions_joined"] = df["directions"].apply(lambda x: " ".join(parse_listish(x))).map(normalize_text)
    df["ner_joined"] = df["NER"].apply(lambda x: " ".join(parse_listish(x))).map(normalize_text)

    df["normalized_title"] = df["title"].map(normalize_text)
    df["normalized_ingredients"] = df["ingredients"].map(normalize_text)
    df["normalized_ner"] = df["NER"].map(normalize_text)

    df = df.drop_duplicates(subset=["normalized_title", "normalized_ingredients"]).reset_index(drop=True)
    df = add_final_columns(df)

    df["document_text"] = (
        df["title"].fillna("").astype(str) + " "
        + df["ner_joined"].fillna("").astype(str) + " "
        + df["ingredients_joined"].fillna("").astype(str)
    ).map(normalize_text)

    df["recommendation_text"] = (
        df["ner_joined"].fillna("").astype(str) + " "
        + df["ingredients_joined"].fillna("").astype(str) + " "
        + df["directions_joined"].fillna("").astype(str)
    ).map(normalize_text)

    return df


def ensure_models_loaded():
    global DF

    global TFIDF_VECTORIZER, TFIDF_MATRIX
    global SVD_COMPONENTS, SVD_MODEL, SVD_MATRIX, SVD_VARIANCE

    global RECOMMEND_TFIDF_VECTORIZER, RECOMMEND_TFIDF_MATRIX
    global RECOMMEND_SVD_COMPONENTS, RECOMMEND_SVD_MODEL, RECOMMEND_SVD_MATRIX, RECOMMEND_SVD_VARIANCE

    if DF is not None:
        return

    DF = load_data()

    TFIDF_VECTORIZER = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.90,
        sublinear_tf=True,
    )

    TFIDF_MATRIX = TFIDF_VECTORIZER.fit_transform(DF["document_text"])

    RECOMMEND_TFIDF_VECTORIZER = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.90,
        sublinear_tf=True,
    )

    RECOMMEND_TFIDF_MATRIX = RECOMMEND_TFIDF_VECTORIZER.fit_transform(DF["recommendation_text"])

    if RECOMMEND_TFIDF_MATRIX.shape[1] > 2 and RECOMMEND_TFIDF_MATRIX.shape[0] > 2:
        recommend_probe_k = max(
            2,
            min(300, RECOMMEND_TFIDF_MATRIX.shape[0] - 1, RECOMMEND_TFIDF_MATRIX.shape[1] - 1),
        )
        recommend_probe_model = TruncatedSVD(n_components=recommend_probe_k, random_state=42)
        recommend_probe_model.fit(RECOMMEND_TFIDF_MATRIX)

        recommend_cumvar = np.cumsum(recommend_probe_model.explained_variance_ratio_)
        RECOMMEND_SVD_COMPONENTS = max(2, int(np.searchsorted(recommend_cumvar, 0.80)) + 1)

        RECOMMEND_SVD_MODEL = TruncatedSVD(n_components=RECOMMEND_SVD_COMPONENTS, random_state=42)
        RECOMMEND_SVD_MATRIX = normalize(RECOMMEND_SVD_MODEL.fit_transform(RECOMMEND_TFIDF_MATRIX))
        RECOMMEND_SVD_VARIANCE = float(RECOMMEND_SVD_MODEL.explained_variance_ratio_.sum())
    else:
        RECOMMEND_SVD_COMPONENTS = 0
        RECOMMEND_SVD_MODEL = None
        RECOMMEND_SVD_MATRIX = None
        RECOMMEND_SVD_VARIANCE = 0.0

    if TFIDF_MATRIX.shape[1] > 2 and TFIDF_MATRIX.shape[0] > 2:
        probe_k = max(2, min(300, TFIDF_MATRIX.shape[0] - 1, TFIDF_MATRIX.shape[1] - 1))
        probe_model = TruncatedSVD(n_components=probe_k, random_state=42)
        probe_model.fit(TFIDF_MATRIX)

        cumvar = np.cumsum(probe_model.explained_variance_ratio_)
        SVD_COMPONENTS = max(2, int(np.searchsorted(cumvar, 0.80)) + 1)

        SVD_MODEL = TruncatedSVD(n_components=SVD_COMPONENTS, random_state=42)
        SVD_MATRIX = normalize(SVD_MODEL.fit_transform(TFIDF_MATRIX))
        SVD_VARIANCE = float(SVD_MODEL.explained_variance_ratio_.sum())
    else:
        SVD_COMPONENTS = 0
        SVD_MODEL = None
        SVD_MATRIX = None
        SVD_VARIANCE = 0.0


def lexical_overlap_bonus(query, row):
    q_tokens = tokenize(query)
    title_tokens = tokenize(row.get("title", ""))
    ingredient_tokens = tokenize(row.get("ingredients", ""))
    ner_tokens = tokenize(row.get("NER", ""))

    if not q_tokens:
        return 0.0

    title_overlap = len(q_tokens & title_tokens) / max(len(q_tokens), 1)
    ingredient_overlap = len(q_tokens & ingredient_tokens) / max(len(q_tokens), 1)
    ner_overlap = len(q_tokens & ner_tokens) / max(len(q_tokens), 1)

    return 100.0 * (0.55 * title_overlap + 0.30 * ner_overlap + 0.15 * ingredient_overlap)


def retrieve_candidates(query, model_name, top_k=250):
    ensure_models_loaded()

    cleaned_query = normalize_text(query)
    if not cleaned_query:
        return DF.iloc[0:0].copy()

    query_tfidf = TFIDF_VECTORIZER.transform([cleaned_query])
    tfidf_scores = cosine_similarity(query_tfidf, TFIDF_MATRIX).ravel()

    if model_name == "svd" and SVD_MODEL is not None and SVD_MATRIX is not None:
        query_svd = normalize(SVD_MODEL.transform(query_tfidf))
        model_scores = cosine_similarity(query_svd, SVD_MATRIX).ravel()
        retrieval_method = "svd"
    else:
        model_scores = tfidf_scores
        retrieval_method = "tfidf"

    result = DF.copy()
    result["tfidf_score"] = tfidf_scores * 100.0
    result["model_score"] = model_scores * 100.0
    result["lexical_bonus"] = result.apply(lambda row: lexical_overlap_bonus(cleaned_query, row), axis=1)
    result["similarity_score"] = (
        result["model_score"] * 0.80
        + result["lexical_bonus"] * 0.20
    ).round(1)
    result["retrieval_method"] = retrieval_method

    result = result.sort_values(
        ["similarity_score", "model_score", "tfidf_score"],
        ascending=[False, False, False],
    )

    threshold = 8.0 if retrieval_method == "svd" else 5.0
    filtered = result[result["similarity_score"] >= threshold].copy()

    if filtered.empty:
        filtered = result.head(top_k).copy()
    else:
        filtered = filtered.head(top_k).copy()

    return filtered

def recommend_from_selected_recipe(selected_title, model_name, top_k=350):
    ensure_models_loaded()

    cleaned_title = normalize_text(selected_title)
    if not cleaned_title:
        return DF.iloc[0:0].copy()

    exact_matches = DF.index[DF["normalized_title"] == cleaned_title].tolist()

    if exact_matches:
        selected_idx = exact_matches[0]
    else:
        title_query = TFIDF_VECTORIZER.transform([cleaned_title])
        title_scores = cosine_similarity(title_query, TFIDF_MATRIX).ravel()
        selected_idx = int(np.argmax(title_scores))

    tfidf_scores = cosine_similarity(
        RECOMMEND_TFIDF_MATRIX[selected_idx:selected_idx + 1],
        RECOMMEND_TFIDF_MATRIX
    ).ravel()

    if model_name == "svd" and RECOMMEND_SVD_MODEL is not None and RECOMMEND_SVD_MATRIX is not None:
        model_scores = cosine_similarity(
            RECOMMEND_SVD_MATRIX[selected_idx:selected_idx + 1],
            RECOMMEND_SVD_MATRIX
        ).ravel()
        retrieval_method = "svd"
    else:
        model_scores = tfidf_scores
        retrieval_method = "tfidf"

    result = DF.copy()
    result["tfidf_score"] = tfidf_scores * 100.0
    result["model_score"] = model_scores * 100.0
    result["lexical_bonus"] = 0.0
    result["similarity_score"] = result["model_score"].round(1)
    result["retrieval_method"] = retrieval_method

    selected_title_tokens = tokenize(DF.iloc[selected_idx]["title"])
    result["title_overlap_count"] = result["title"].apply(
        lambda title: len(selected_title_tokens & tokenize(title))
    )

    result["similarity_score"] = (
        result["similarity_score"] - result["title_overlap_count"] * 1.0
    ).round(1)

    result = result.drop(index=selected_idx)

    result = result.sort_values(
        ["similarity_score", "model_score", "tfidf_score"],
        ascending=[False, False, False],
    )

    return result.head(top_k).copy()


def profile_sort(df, profile):
    profile = (profile or "none").strip().lower()

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

    return df.sort_values(["similarity_score", "nutrition_available", "title"], ascending=[False, False, True])


def build_payload(row, profile=""):
    ingredients = parse_listish(row.get("ingredients", ""))
    directions = parse_listish(row.get("directions", ""))

    return {
        "title": row.get("title", ""),
        "ingredients": ingredients,
        "directions": directions,
        "ingredients_text": row.get("ingredients", ""),
        "directions_text": row.get("directions", ""),
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
        "tfidf_score": round(safe_float(row.get("tfidf_score", 0)) or 0, 1),
        "model_score": round(safe_float(row.get("model_score", 0)) or 0, 1),
        "retrieval_method": row.get("retrieval_method", DEFAULT_MODEL),
        "nutrition_status": nutrition_status_for_row(row),
        "nutrition_confidence": row.get("nutrition_confidence", None),
        "diet": profile if profile != "none" else "",
    }


@bp.get("/mealmap/meta")
def meta():
    ensure_models_loaded()

    available_count = int(DF["nutrition_available"].sum())
    return jsonify(
        {
            "dataset_size": int(len(DF)),
            "nutrition_coverage": round((available_count / max(len(DF), 1)) * 100, 1),
            "retrieval_models": ["tfidf", "svd"],
            "default_retrieval_model": DEFAULT_MODEL,
            "svd_components": int(SVD_COMPONENTS),
            "svd_explained_variance": round(SVD_VARIANCE * 100.0, 2),
            "profiles": [
                "high_protein",
                "low_carb",
                "keto",
                "low_calorie",
                "low_fat",
                "low_sodium",
                "balanced",
                "bodybuilding",
                "vegan",
            ],
        }
    )


@bp.get("/mealmap/matches")
def matches():
    query = request.args.get("query", "").strip()
    profile = request.args.get("profile", "none").strip().lower()
    model_name = request.args.get("model", DEFAULT_MODEL).strip().lower()

    if model_name not in {"tfidf", "svd"}:
        model_name = DEFAULT_MODEL

    if not query:
        return jsonify({"matches": []})

    candidates = retrieve_candidates(query, model_name=model_name, top_k=200)
    if candidates.empty:
        return jsonify({"matches": []})

    ranked = profile_sort(candidates, profile).head(SEARCH_LIMIT)
    payload = [build_payload(row, profile) for _, row in ranked.iterrows()]
    return jsonify({"matches": payload})


@bp.get("/mealmap/recommend")
def recommend():
    selected = request.args.get("selected", "").strip()
    profile = request.args.get("profile", "none").strip().lower()
    model_name = request.args.get("model", DEFAULT_MODEL).strip().lower()

    if model_name not in {"tfidf", "svd"}:
        model_name = DEFAULT_MODEL

    if not selected:
        return jsonify({"recipes": []})

    candidates = recommend_from_selected_recipe(selected, model_name=model_name, top_k=350)
    if candidates.empty:
        return jsonify({"recipes": []})
    
    

    ranked = profile_sort(candidates, profile).head(RECOMMEND_LIMIT)
    payload = [build_payload(row, profile) for _, row in ranked.iterrows()]
    return jsonify({"recipes": payload})


def register_routes(app):
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(_):
        return jsonify({"error": "Internal server error"}), 500