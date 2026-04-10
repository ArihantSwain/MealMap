import pandas as pd

INPUT = "data/processed/recipes_final.csv"
OUTPUT = "src/data/recipes_enriched.csv"

df = pd.read_csv(INPUT)

def estimate(row):
    text = str(row.get("ingredients", "")).lower()

    protein = text.count("chicken") * 25 + text.count("beef") * 30
    carbs = text.count("rice") * 40 + text.count("pasta") * 45
    fat = text.count("cheese") * 20 + text.count("oil") * 15
    sodium = text.count("salt") * 300
    fiber = text.count("beans") * 10

    return pd.Series({
        "estimated_protein_g": protein,
        "estimated_carbs_g": carbs,
        "estimated_fat_g": fat,
        "estimated_sodium_mg": sodium,
        "estimated_fiber_g": fiber,
    })

df = pd.concat([df, df.apply(estimate, axis=1)], axis=1)

df.to_csv(OUTPUT, index=False)
print("Saved:", OUTPUT)
