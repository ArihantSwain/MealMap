import pandas as pd
import re

INPUT_CSV = "../data/recipes_data.csv"
OUTPUT_CSV = "../data/recipes_enriched.csv"
MAX_ROWS = 10000

NUTRITION_DB = {
    "chicken": {"cal": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0, "sodium": 74},
    "beef": {"cal": 250, "protein": 26, "carbs": 0, "fat": 15, "fiber": 0, "sodium": 72},
    "egg": {"cal": 70, "protein": 6, "carbs": 1, "fat": 5, "fiber": 0, "sodium": 70},
    "rice": {"cal": 200, "protein": 4, "carbs": 45, "fat": 1, "fiber": 1, "sodium": 5},
    "cheese": {"cal": 110, "protein": 7, "carbs": 1, "fat": 9, "fiber": 0, "sodium": 180},
    "milk": {"cal": 120, "protein": 8, "carbs": 12, "fat": 5, "fiber": 0, "sodium": 100},
    "butter": {"cal": 100, "protein": 0, "carbs": 0, "fat": 11, "fiber": 0, "sodium": 90},
    "oil": {"cal": 120, "protein": 0, "carbs": 0, "fat": 14, "fiber": 0, "sodium": 0},
    "flour": {"cal": 100, "protein": 3, "carbs": 21, "fat": 1, "fiber": 1, "sodium": 2},
    "sugar": {"cal": 50, "protein": 0, "carbs": 13, "fat": 0, "fiber": 0, "sodium": 1},
    "potato": {"cal": 160, "protein": 4, "carbs": 37, "fat": 0, "fiber": 4, "sodium": 17},
    "pasta": {"cal": 220, "protein": 8, "carbs": 43, "fat": 1, "fiber": 2, "sodium": 1},
    "bean": {"cal": 120, "protein": 8, "carbs": 21, "fat": 0.5, "fiber": 8, "sodium": 5},
    "beans": {"cal": 120, "protein": 8, "carbs": 21, "fat": 0.5, "fiber": 8, "sodium": 5},
    "bread": {"cal": 80, "protein": 3, "carbs": 15, "fat": 1, "fiber": 1, "sodium": 150},
    "onion": {"cal": 20, "protein": 0.5, "carbs": 5, "fat": 0, "fiber": 1, "sodium": 2},
    "tomato": {"cal": 20, "protein": 1, "carbs": 4, "fat": 0, "fiber": 1, "sodium": 5},
    "corn": {"cal": 80, "protein": 3, "carbs": 19, "fat": 1, "fiber": 2, "sodium": 15},
    "carrot": {"cal": 25, "protein": 0.5, "carbs": 6, "fat": 0, "fiber": 2, "sodium": 40},
    "broccoli": {"cal": 30, "protein": 2.5, "carbs": 6, "fat": 0.3, "fiber": 2.5, "sodium": 30},
    "salt": {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 500},
    "bacon": {"cal": 90, "protein": 6, "carbs": 0, "fat": 7, "fiber": 0, "sodium": 300},
    "sausage": {"cal": 180, "protein": 8, "carbs": 1, "fat": 16, "fiber": 0, "sodium": 500},
}

SERVING_HINTS = [
    (r"serves\s+(\d+)", 1),
    (r"serve[s]?\s+(\d+)", 1),
    (r"makes\s+(\d+)", 1),
    (r"yields?\s+(\d+)", 1),
    (r"(\d+)\s+servings", 1),
    (r"(\d+)\s+biscuits", 1),
    (r"(\d+)\s+cookies", 1),
    (r"(\d+)\s+muffins", 1),
    (r"(\d+)\s+rolls", 1),
    (r"(\d+)\s+cups", 1),
]

def extract_keywords(text):
    return re.findall(r"[a-z]+", str(text).lower())

def estimate_servings(title, ingredients, directions):
    text = f"{title} {ingredients} {directions}".lower()

    for pattern, group in SERVING_HINTS:
        match = re.search(pattern, text)
        if match:
            try:
                value = int(match.group(group))
                if 1 <= value <= 24:
                    return value
            except Exception:
                pass

    ingredient_count = len(extract_keywords(ingredients))

    if ingredient_count >= 40:
        return 8
    if ingredient_count >= 28:
        return 6
    if ingredient_count >= 18:
        return 4
    if ingredient_count >= 10:
        return 3
    return 2

def estimate_nutrition(title, ingredients, directions):
    words = extract_keywords(f"{title} {ingredients}")
    total = {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0}
    count = 0
    matched = set()

    for word in words:
        if word in NUTRITION_DB:
            matched.add(word)
            for k in total:
                total[k] += NUTRITION_DB[word][k]
            count += 1

    if count == 0:
        return None

    servings = estimate_servings(title, ingredients, directions)
    if servings < 1:
        servings = 1

    base_divisor = max(min(count / 2, 12), 1)
    recipe_multiplier = max(servings / 2, 1)

    estimated_recipe_cal = total["cal"] * recipe_multiplier
    estimated_recipe_protein = total["protein"] * recipe_multiplier
    estimated_recipe_carbs = total["carbs"] * recipe_multiplier
    estimated_recipe_fat = total["fat"] * recipe_multiplier
    estimated_recipe_fiber = total["fiber"] * recipe_multiplier
    estimated_recipe_sodium = total["sodium"] * recipe_multiplier

    per_serving = {
        "estimated_servings": servings,
        "estimated_calories": round(max(estimated_recipe_cal / base_divisor, 1), 1),
        "estimated_protein_g": round(max(estimated_recipe_protein / base_divisor, 0), 1),
        "estimated_carbs_g": round(max(estimated_recipe_carbs / base_divisor, 0), 1),
        "estimated_fat_g": round(max(estimated_recipe_fat / base_divisor, 0), 1),
        "estimated_fiber_g": round(max(estimated_recipe_fiber / base_divisor, 0), 1),
        "estimated_sodium_mg": round(max(estimated_recipe_sodium / base_divisor, 0), 1),
        "nutrition_source": "rule_estimated",
        "nutrition_confidence": round(min(0.35 + 0.08 * len(matched), 0.92), 2),
        "matched_ingredient_keywords": ", ".join(sorted(matched))
    }

    return per_serving

def main():
    df = pd.read_csv(INPUT_CSV)

    if MAX_ROWS:
        df = df.head(MAX_ROWS).copy()

    for i, row in df.iterrows():
        title = row.get("title", "")
        ingredients = row.get("ingredients", "")
        directions = row.get("directions", "")

        est = estimate_nutrition(title, ingredients, directions)

        if est:
            for k, v in est.items():
                df.at[i, k] = v

        if i % 200 == 0:
            print(f"{i} processed")

    df.to_csv(OUTPUT_CSV, index=False)
    print("Saved to", OUTPUT_CSV)

if __name__ == "__main__":
    main()
