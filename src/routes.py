from pathlib import Path
import ast
import re

import os
import json
import logging
from infosci_spark_client import LLMClient

import numpy as np
import pandas as pd
from flask import Blueprint, jsonify, request, session
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import normalize

logger = logging.getLogger(__name__)

bp = Blueprint("bp", __name__)

BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "recipes_enriched.csv"

SEARCH_LIMIT = 12
RECOMMEND_LIMIT = 24
DEFAULT_MODEL = "tfidf"

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


EXCLUDE_PATTERNS = [
    re.compile(r"\bwithout\s+((?:[\w-]+\s+){0,2}[\w-]+)\b", re.I),
    re.compile(r"\bexclude\s+((?:[\w-]+\s+){0,2}[\w-]+)\b", re.I),
    re.compile(r"\bno\s+((?:[\w-]+\s+){0,2}[\w-]+)\b", re.I),
]


def parse_query_exclusions(raw):
    text = str(raw or "").strip()
    exclusions = []
    for _ in range(24):
        matched = False
        for pattern in EXCLUDE_PATTERNS:
            hit = pattern.search(text)
            if hit:
                exclusions.append(normalize_text(hit.group(1)))
                text = pattern.sub(" ", text, count=1)
                matched = True
                break
        if not matched:
            break
    retrieval_text = normalize_text(re.sub(r"\s+", " ", text).strip())
    unique = []
    seen = set()
    for phrase in exclusions:
        if phrase and phrase not in seen:
            seen.add(phrase)
            unique.append(phrase)
    return retrieval_text, unique


def row_contains_exclusion(row, exclusion):
    row_text = normalize_text(
        f"{row.get('title', '')} {row.get('ingredients', '')} {row.get('NER', '')} "
        f"{row.get('document_text', '')} {row.get('recommendation_text', '')}"
    )
    if not exclusion:
        return False
    if " " in exclusion:
        return exclusion in row_text
    return exclusion in tokenize(row_text)


def apply_exclusion_filter(df, exclusions):
    if df is None or df.empty or not exclusions:
        return df
    keep_mask = ~df.apply(lambda row: any(row_contains_exclusion(row, ex) for ex in exclusions), axis=1)
    return df[keep_mask].copy()


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

    cleaned_query, exclusions = parse_query_exclusions(query)
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

    filtered = apply_exclusion_filter(filtered, exclusions)
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

def llm_refine_mealmap_query(client, user_message, current_profile="none", current_model=DEFAULT_MODEL):
    messages = [
        {
            "role": "system",
            "content": (
                "You rewrite recipe-search requests into retrieval-friendly queries for an IR system.\n"
                "Return exactly one JSON object and nothing else.\n"
                "Do not use markdown.\n"
                "Do not use code fences.\n"
                "Do not add commentary before or after the JSON.\n"
                "Use this exact schema:\n"
                '{"refined_query":"...","profile":"...","model":"...","reason":"..."}\n'
                "Rules:\n"
                "- refined_query should be short, concrete, and optimized for retrieval.\n"
                "- Keep the main dish, cuisine, ingredients, dietary goals, and meal type when relevant.\n"
                "- Remove filler phrases like 'I want', 'can you find', 'something with'.\n"
                "- profile must be one of: none, high_protein, low_carb, keto, low_calorie, low_fat, low_sodium, balanced, bodybuilding.\n"
                "- model must be either tfidf or svd.\n"
                "- reason should be one short sentence.\n"
                "- If the user request is already a good search query, keep it close to the original.\n"
                "Valid example:\n"
                '{"refined_query":"chicken soup","profile":"none","model":"tfidf","reason":"Removed conversational phrasing and kept the main dish terms."}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"User request: {user_message}\n"
                f"Current profile: {current_profile}\n"
                f"Current model: {current_model}"
            ),
        },
    ]

    try:
        response = client.chat(messages)
    except Exception as e:
        logger.warning("Refinement LLM call failed: %s", e)
        return {
            "refined_query": user_message,
            "profile": current_profile,
            "model": current_model,
            "reason": "Fallback: LLM call failed.",
        }

    text = ""
    if isinstance(response, dict):
        text = (
            response.get("content")
            or response.get("text")
            or response.get("output_text")
            or ""
        )
    else:
        text = str(response or "")

    text = text.strip()
    logger.warning("Raw refinement response: %r", text)

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0).strip()

    try:
        data = json.loads(text)
    except Exception as e:
        logger.warning("Failed to parse refinement JSON; falling back. Error: %s", e)
        return {
            "refined_query": user_message,
            "profile": current_profile,
            "model": current_model,
            "reason": "Fallback: could not parse LLM output.",
        }

    refined_query = str(data.get("refined_query", user_message)).strip() or user_message
    profile = str(data.get("profile", current_profile)).strip().lower() or current_profile
    model = str(data.get("model", current_model)).strip().lower() or current_model
    reason = str(data.get("reason", "")).strip() or "Used LLM to refine the query."

    valid_profiles = {
        "none",
        "high_protein",
        "low_carb",
        "keto",
        "low_calorie",
        "low_fat",
        "low_sodium",
        "balanced",
        "bodybuilding",
    }

    if profile not in valid_profiles:
        profile = current_profile

    if model not in {"tfidf", "svd"}:
        model = current_model

    return {
        "refined_query": refined_query,
        "profile": profile,
        "model": model,
        "reason": reason,
    }

def build_recipe_context(recipes):
    if not recipes:
        return "No recipes retrieved."

    chunks = []
    for recipe in recipes:
        ingredients = recipe.get("ingredients", [])[:8]
        directions = recipe.get("directions", [])[:2]

        chunks.append(
            f"Title: {recipe.get('title', '')}\n"
            f"Source: {recipe.get('link', '') or recipe.get('source', '') or recipe.get('site', '')}\n"
            f"Calories: {recipe.get('calories', 'N/A')}\n"
            f"Protein: {recipe.get('protein_g', 'N/A')} g\n"
            f"Carbs: {recipe.get('carbs_g', 'N/A')} g\n"
            f"Fat: {recipe.get('fat_g', 'N/A')} g\n"
            f"Ingredients: {', '.join(map(str, ingredients))}\n"
            f"Directions: {' '.join(map(str, directions))}\n"
            f"Similarity: {recipe.get('similarity_score', 'N/A')}"
        )

    return "\n\n---\n\n".join(chunks)


def build_recipe_sources(recipes):
    sources = []
    for recipe in recipes:
        sources.append(
            {
                "title": recipe.get("title", ""),
                "url": recipe.get("link", "") or recipe.get("source", "") or recipe.get("site", ""),
            }
        )
    return sources

def llm_answer_with_recipes(client, user_message, refined_query, recipes):
    context_text = build_recipe_context(recipes)

    messages = [
        {
            "role": "system",
            "content": (
                "You are a recipe assistant. Use only the retrieved recipe information provided.\n"
                "Return ONLY simple HTML for the answer body.\n"
                "Formatting rules:\n"
                "- Start with one short paragraph in <p>...</p>.\n"
                "- Then group options into sections when helpful.\n"
                "- Use <p><strong>Section Name</strong></p> for section headings.\n"
                "- Use <ul> and <li> for recipe options.\n"
                "- Each recipe option must start with <strong>Recipe Name:</strong> followed by 1-2 sentences.\n"
                "- Do not use markdown.\n"
                "- Do not use asterisks.\n"
                "- Do not use quotation marks unless truly needed.\n"
                "- Do not invent recipes not present in the retrieved context.\n"
                "- Do not mention recipes that were not retrieved.\n"
                "- When mentioning a recipe, include its source URL if available.\n"
                "- Keep the answer concise, clean, and readable.\n"
                "Example output:\n"
                "<p>I found several good chicken options for you, including light dishes and heartier casseroles.</p>"
                "<p><strong>Simple and Light</strong></p>"
                "<ul>"
                "<li><strong>Poached Chicken:</strong> A clean, basic option if you want something minimal and straightforward.</li>"
                "<li><strong>Chicken and Noodles:</strong> A simple comfort-food choice with a classic preparation.</li>"
                "</ul>"
                "<p><strong>Comforting Casseroles</strong></p>"
                "<ul>"
                "<li><strong>Chicken Casserole:</strong> A filling option if you want something hearty and rich.</li>"
                "</ul>"
            ),
        },
        {
            "role": "user",
            "content": (
                f"Original user request: {user_message}\n"
                f"Refined retrieval query: {refined_query}\n\n"
                f"Retrieved recipes:\n\n{context_text}"
            ),
        },
    ]

    response = client.chat(messages)
    return (response.get("content") or "").strip()


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
    filter_query = request.args.get("filter_query", "").strip()
    profile = request.args.get("profile", "none").strip().lower()
    model_name = request.args.get("model", DEFAULT_MODEL).strip().lower()

    if model_name not in {"tfidf", "svd"}:
        model_name = DEFAULT_MODEL

    if not selected:
        return jsonify({"recipes": []})

    candidates = recommend_from_selected_recipe(selected, model_name=model_name, top_k=350)
    if candidates.empty:
        return jsonify({"recipes": []})

    if filter_query:
        _, exclusions = parse_query_exclusions(filter_query)
        candidates = apply_exclusion_filter(candidates, exclusions)
        if candidates.empty:
            return jsonify({"recipes": []})

    ranked = profile_sort(candidates, profile).head(RECOMMEND_LIMIT)
    payload = [build_payload(row, profile) for _, row in ranked.iterrows()]
    return jsonify({"recipes": payload})

@bp.post("/mealmap/chat")
def mealmap_chat():
    ensure_models_loaded()

    data = request.get_json() or {}
    user_message = str(data.get("message", "")).strip()
    profile = str(data.get("profile", "none")).strip().lower()
    model_name = str(data.get("model", DEFAULT_MODEL)).strip().lower()

    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    if profile not in {
        "none", "high_protein", "low_carb", "keto", "low_calorie",
        "low_fat", "low_sodium", "balanced", "bodybuilding"
    }:
        profile = "none"

    if model_name not in {"tfidf", "svd"}:
        model_name = DEFAULT_MODEL

    api_key = os.getenv("SPARK_API_KEY")
    if not api_key:
        return jsonify({"error": "API_KEY not set"}), 500

    client = LLMClient(api_key=api_key)

    refinement = llm_refine_mealmap_query(
        client,
        user_message,
        current_profile=profile,
        current_model=model_name,
    )

    refined_query = refinement["refined_query"]
    refined_profile = refinement["profile"]
    refined_model = refinement["model"]

    candidates = retrieve_candidates(refined_query, model_name=refined_model, top_k=200)
    ranked = profile_sort(candidates, refined_profile).head(SEARCH_LIMIT)
    payload = [build_payload(row, refined_profile) for _, row in ranked.iterrows()]

    llm_answer = llm_answer_with_recipes(
        client,
        user_message=user_message,
        refined_query=refined_query,
        recipes=payload,
    )
    sources = build_recipe_sources(payload)

    return jsonify(
        {
            "original_query": user_message,
            "refined_query": refined_query,
            "refinement_reason": refinement["reason"],
            "profile_used": refined_profile,
            "model_used": refined_model,
            "matches": payload,
            "sources": sources,
            "answer": llm_answer,
        }
    )


@bp.post("/mealplan/add")
def mealplan_add():
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    if not title:
        return jsonify({"error": "Missing title"}), 400

    plan = session.get("meal_plan", [])
    if any(r["title"] == title for r in plan):
        return jsonify({"plan": plan, "already_added": True})

    plan.append({
        "title": title,
        "ingredients": data.get("ingredients", []),
        "servings": data.get("servings", ""),
    })
    session["meal_plan"] = plan
    session.modified = True
    return jsonify({"plan": plan})


@bp.post("/mealplan/remove")
def mealplan_remove():
    data = request.get_json() or {}
    title = (data.get("title") or "").strip()
    plan = [r for r in session.get("meal_plan", []) if r["title"] != title]
    session["meal_plan"] = plan
    session.modified = True
    return jsonify({"plan": plan})


@bp.get("/mealplan")
def mealplan_get():
    return jsonify({"plan": session.get("meal_plan", [])})


@bp.get("/mealplan/shopping-list")
def mealplan_shopping_list():
    plan = session.get("meal_plan", [])
    seen = set()
    items = []
    for recipe in plan:
        for ingredient in recipe.get("ingredients", []):
            clean = ingredient.strip()
            if clean and clean.lower() not in seen:
                seen.add(clean.lower())
                items.append(clean)
    return jsonify({"items": items, "recipe_count": len(plan)})


def register_routes(app):
    app.register_blueprint(bp)

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def server_error(_):
        return jsonify({"error": "Internal server error"}), 500