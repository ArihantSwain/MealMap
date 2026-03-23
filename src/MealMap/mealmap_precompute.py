"""
Given a dish user like finds recipes with similar ingredients, then rerank
o fit your dietary goals (keto, high protein, low calorie, etc.).
Reads from recipes_with_nutrition.csv 

Ex:
python mealmap_precompute.py
python mealmap_precompute.py --top-k 50 --results 10
"""

import argparse
import ast
import heapq
import os
import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

#diet profiles which nutrients to favor (+) or avoid (-)
DIETARY_PROFILES = {
    "high_protein": {
        "description": "Maximize protein content",
        "weights": {"protein_g": 2.0, "fat_g": -0.3},
        "constraints": {},
    },
    "low_carb": {
        "description": "Minimize carbohydrates",
        "weights": {"carbs_g": -2.0, "fiber_g": 0.5},
        "constraints": {},
    },
    "keto": {
        "description": "Very low carb, high fat, moderate protein",
        "weights": {"carbs_g": -3.0, "fat_g": 1.5, "protein_g": 0.5},
        "constraints": {"carbs_g_max": 300},
    },
    "low_calorie": {
        "description": "Minimize total calories",
        "weights": {"calories": -2.0},
        "constraints": {},
    },
    "low_fat": {
        "description": "Minimize fat content",
        "weights": {"fat_g": -2.0, "protein_g": 0.5},
        "constraints": {},
    },
    "low_sodium": {
        "description": "Minimize sodium intake",
        "weights": {"sodium_mg": -2.0},
        "constraints": {},
    },
    "balanced": {
        "description": "Balanced macros, moderate everything",
        "weights": {"protein_g": 1.0, "fiber_g": 0.5, "calories": -0.5},
        "constraints": {},
    },
    "bodybuilding": {
        "description": "High protein, high calorie, moderate carbs",
        "weights": {"protein_g": 3.0, "calories": 1.0, "carbs_g": 0.5, "fat_g": -0.5},
        "constraints": {},
    },
    "none": {
        "description": "No preference, rank by similarity only",
        "weights": {},
        "constraints": {},
    },
}



def load_data(data_path: str):
    """Load the standalone recipes + nutrition CSV."""
    print(f"Loading data from {data_path}...")
    df = pd.read_csv(data_path)
    print(f"  {len(df)} recipes loaded")

    required = ["calories", "protein_g", "fat_g", "carbs_g"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            f"Missing columns: {missing}. Run compute_nutrition.py first."
        )

    if "NER" not in df.columns and "ingredients" not in df.columns:
        raise ValueError(
            "Need either 'NER' or 'ingredients' column for similarity matching."
        )

    return df


# -Ingredient indexing

def _extract_food_name(ingredient_str: str) -> str:
    """Pull just the food name out of something like '2 c. crushed pretzels' -> 'pretzels'."""
    import re
    s = ingredient_str.lower().strip()
    s = re.sub(r'\([\d\s./½¼¾⅓⅔]+\s*(oz|ounce|lb|g|ml|kg)\.?\)', '', s)
    s = re.sub(r'^[\d\s./-]+', '', s)
    stopwords = [
        r'\bc\.?\b', r'\bcup[s]?\b', r'\btbsp\.?\b', r'\btablespoon[s]?\b',
        r'\btsp\.?\b', r'\bteaspoon[s]?\b', r'\boz\.?\b', r'\bounce[s]?\b',
        r'\blb[s]?\.?\b', r'\bpound[s]?\b', r'\bpkg\.?\b', r'\bpackage[s]?\b',
        r'\bcan[s]?\b', r'\bjar[s]?\b', r'\bcontainer[s]?\b', r'\bcarton[s]?\b',
        r'\bsmall\b', r'\bmedium\b', r'\blarge\b',
        r'\bchopped\b', r'\bminced\b', r'\bdiced\b', r'\bsliced\b',
        r'\bcrushed\b', r'\bmelted\b', r'\bsoftened\b', r'\bthawed\b',
        r'\bfresh\b', r'\bdried\b', r'\bfrozen\b', r'\bcanned\b',
        r'\boptional\b', r'\bto taste\b',
    ]
    for w in stopwords:
        s = re.sub(w, '', s)
    s = re.sub(r'[,;()\[\]]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def build_ingredient_index(df: pd.DataFrame) -> dict[str, set[str]]:
    """
    Build a map of recipe title -> set of ingredient names.
    Uses the NER column if it exists, otherwise strips quantities from the ingredients column.
    """
    has_ner = "NER" in df.columns
    name_ingredient_map = {}

    for row in df.itertuples(index=False):
        title = row.title
        ingredients = set()

        # NER column cleaner
        if has_ner:
            ner_str = str(getattr(row, "NER", "[]"))
            if ner_str and ner_str not in ("nan", "", "[]"):
                try:
                    ingredients = set(ast.literal_eval(ner_str))
                except (ValueError, SyntaxError):
                    pass

        # If no NER, parse the ingredients column and strip out the quantities
        if not ingredients and hasattr(row, "ingredients"):
            ing_str = str(row.ingredients)
            if ing_str and ing_str not in ("nan", "", "[]"):
                try:
                    raw_list = ast.literal_eval(ing_str)
                    if isinstance(raw_list, list):
                        ingredients = {
                            _extract_food_name(item)
                            for item in raw_list
                            if len(_extract_food_name(str(item))) > 1
                        }
                except (ValueError, SyntaxError):
                    pass

        if ingredients:
            name_ingredient_map[title] = ingredients

    return name_ingredient_map


# Similaritu

def find_matching_dishes(query: str, name_ingredient_map: dict) -> list[str]:
    """Find recipes whose title contains the search query."""
    matches = []
    query_lower = query.lower()
    for name in name_ingredient_map:
        lower_name = name.lower()
        if lower_name == query_lower:
            return [name]
        if query_lower in lower_name:
            matches.append(name)
    return matches


def get_similar_by_ingredients(dish_name: str, name_ingredient_map: dict, top_k: int = 50,) -> list[tuple[int, str]]:
    """Find the top-k recipes with the most shared ingredients."""
    sample_ingredients = name_ingredient_map[dish_name]
    return heapq.nlargest(
        top_k,
        (
            (len(sample_ingredients & ingredients), name)
            for name, ingredients in name_ingredient_map.items()
            if name != dish_name
        ),
    )


# Score and rerank

def compute_nutrition_score(row: pd.Series, profile: dict) -> float:
    """Score a recipe based on how well its macros match the dietary profile."""
    score = 0.0
    for nutrient, weight in profile["weights"].items():
        val = row.get(nutrient, 0)
        if pd.notna(val):
            score += weight * val
    return score


def normalize_scores(similarity_scores: list[float], nutrition_scores: list[float]):
    """Scale both score lists to 0-1 so we can combine them fairly."""
    def _norm(scores):
        lo = min(scores) if scores else 0
        hi = max(scores) if scores else 1
        span = hi - lo
        if span == 0:
            return [0.5] * len(scores)
        return [(s - lo) / span for s in scores]

    return _norm(similarity_scores), _norm(nutrition_scores)


def rerank(
    similar_recipes: list[tuple[int, str]],
    df: pd.DataFrame,
    profile: dict,
    similarity_weight: float = 0.6,
    nutrition_weight: float = 0.4,
    num_results: int = 10,
) -> list[dict]:
    """
    Take the similar recipes and reorder them using a mix of
    ingredient similarity (60%) and nutrition fit (40%).
    """
    nutrition_lookup = df.drop_duplicates(subset="title").set_index("title").to_dict("index")

    # Score each candidate
    candidates = []
    for sim_score, title in similar_recipes:
        if title not in nutrition_lookup:
            continue
        row_data = nutrition_lookup[title]
        nut_score = compute_nutrition_score(pd.Series(row_data), profile)
        candidates.append({
            "title": title,
            "similarity_score": sim_score,
            "nutrition_score": nut_score,
            "calories": row_data.get("calories", 0),
            "protein_g": row_data.get("protein_g", 0),
            "fat_g": row_data.get("fat_g", 0),
            "carbs_g": row_data.get("carbs_g", 0),
            "fiber_g": row_data.get("fiber_g", 0),
            "sodium_mg": row_data.get("sodium_mg", 0),
        })

    if not candidates:
        return []

    # Filter out for constraint
    filtered = []
    for c in candidates:
        passes = True
        for key, limit in profile.get("constraints", {}).items():
            col = key.replace("_max", "").replace("_min", "")
            val = c.get(col, 0)
            if key.endswith("_max") and val > limit:
                passes = False
            elif key.endswith("_min") and val < limit:
                passes = False
        if passes:
            filtered.append(c)

    if not filtered:
        print("  (Nothing passed the dietary constraints, showing unfiltered results)")
        filtered = candidates

    sim_scores = [c["similarity_score"] for c in filtered]
    nut_scores = [c["nutrition_score"] for c in filtered]
    norm_sim, norm_nut = normalize_scores(sim_scores, nut_scores)

    for i, c in enumerate(filtered):
        c["norm_similarity"] = norm_sim[i]
        c["norm_nutrition"] = norm_nut[i]
        c["combined_score"] = (
            similarity_weight * norm_sim[i] + nutrition_weight * norm_nut[i]
        )

    filtered.sort(key=lambda x: x["combined_score"], reverse=True)
    return filtered[:num_results]


# Display

def display_results(results: list[dict], profile_name: str, dish_name: str):
    """Print the final ranked results."""
    profile = DIETARY_PROFILES[profile_name]
    print(f"\n{'='*70}")
    print(f"Top recipes similar to \"{dish_name}\"")
    print(f"Diet: {profile_name} — {profile['description']}")
    print(f"{'='*70}\n")

    for i, r in enumerate(results, start=1):
        print(f"  {i}. {r['title']}")
        print(f"     {r['similarity_score']} shared ingredients")
        print(f"     Cal: {r['calories']:.0f}  |  Protein: {r['protein_g']:.1f}g  |  "
              f"Fat: {r['fat_g']:.1f}g  |  Carbs: {r['carbs_g']:.1f}g  |  "
              f"Fiber: {r['fiber_g']:.1f}g  |  Sodium: {r['sodium_mg']:.0f}mg")
        print(f"     Score: {r['combined_score']:.3f} "
              f"(similarity: {r['norm_similarity']:.2f}, diet fit: {r['norm_nutrition']:.2f})")
        print()



def interactive_mode(df: pd.DataFrame, name_ingredient_map: dict, args):
    """The main CLI loop — ask for a dish and a diet, then show results."""


    sample_dish = input("Name a dish we should model suggestions based off of: ")
    matches = find_matching_dishes(sample_dish, name_ingredient_map)

    while len(matches) == 0:
        sample_dish = input("That dish isn't in our database, try another one: ")
        matches = find_matching_dishes(sample_dish, name_ingredient_map)

    if len(matches) == 1:
        chosen_dish = matches[0]
    else:
        print("\nI found multiple matches:")
        for i, name in enumerate(matches[:10], start=1):
            print(f"  {i}: {name}")
        choice = int(input("Choose the number of the dish you meant: "))
        chosen_dish = matches[choice - 1]

    print(f"\nSelected: {chosen_dish}")
    print(f"Ingredients: {', '.join(sorted(name_ingredient_map[chosen_dish]))}")


    print("\nDietary preferences:")
    profile_names = list(DIETARY_PROFILES.keys())
    for i, name in enumerate(profile_names, start=1):
        print(f"  {i}. {name:20s} — {DIETARY_PROFILES[name]['description']}")

    choice = input(f"\nPick one (1-{len(profile_names)}) [default: none]: ").strip()
    if choice and choice.isdigit() and 1 <= int(choice) <= len(profile_names):
        profile_name = profile_names[int(choice) - 1]
    else:
        profile_name = "none"

    print(f"\nUsing: {profile_name}")


    print(f"\nSearching for top {args.top_k} similar recipes...")
    similar = get_similar_by_ingredients(chosen_dish, name_ingredient_map, args.top_k)
    print(f"  Found {len(similar)} candidates")

    profile = DIETARY_PROFILES[profile_name]
    if profile_name == "none":
        results = []
        nutrition_lookup = df.drop_duplicates(subset="title").set_index("title").to_dict("index")
        for sim_score, title in similar[:args.results]:
            row_data = nutrition_lookup.get(title, {})
            results.append({
                "title": title,
                "similarity_score": sim_score,
                "nutrition_score": 0,
                "norm_similarity": 1.0,
                "norm_nutrition": 0.0,
                "combined_score": sim_score,
                "calories": row_data.get("calories", 0),
                "protein_g": row_data.get("protein_g", 0),
                "fat_g": row_data.get("fat_g", 0),
                "carbs_g": row_data.get("carbs_g", 0),
                "fiber_g": row_data.get("fiber_g", 0),
                "sodium_mg": row_data.get("sodium_mg", 0),
            })
    else:
        results = rerank(similar, df, profile, num_results=args.results)

    display_results(results, profile_name, chosen_dish)


def main():
    parser = argparse.ArgumentParser(description="MealMap recipe recommender")
    parser.add_argument(
        "--data",
        default=os.path.join(SCRIPT_DIR, "recipes_with_nutrition.csv"),
        help="Path to the recipes + nutrition CSV (default: recipes_with_nutrition.csv)",
    )
    parser.add_argument("--top-k", type=int, default=50, help="How many similar recipes to consider (default: 50)")
    parser.add_argument("--results", type=int, default=10, help="How many results to show (default: 10)")
    args = parser.parse_args()

    df = load_data(args.data)

    print("\nBuilding ingredient index...")
    name_ingredient_map = build_ingredient_index(df)
    print(f"  {len(name_ingredient_map)} recipes indexed")

    interactive_mode(df, name_ingredient_map, args)


if __name__ == "__main__":
    main()
