import os
import json
import time
import re
import pandas as pd
from openai import OpenAI

INPUT_CSV = "../data/recipes_data.csv"
OUTPUT_CSV = "../data/recipes_enriched.csv"
CHECKPOINT_EVERY = 25
SLEEP_BETWEEN_CALLS = 0.2
MAX_ROWS = 25

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

def safe_str(v):
    if pd.isna(v):
        return ""
    return str(v)

def normalize_title(title):
    title = safe_str(title).strip().lower()
    title = re.sub(r'["“”‘’!?,.:;()\[\]{}]+', "", title)
    title = re.sub(r"\s+", " ", title)
    return title

def parse_maybe_list(value):
    text = safe_str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(x).strip() for x in parsed if str(x).strip()]
    except Exception:
        pass
    return [x.strip() for x in text.split(",") if x.strip()]

def build_prompt(row):
    title = safe_str(row.get("title", ""))
    ingredients = parse_maybe_list(row.get("ingredients", ""))
    directions = parse_maybe_list(row.get("directions", ""))

    ingredients_text = "\n".join(f"- {x}" for x in ingredients[:40]) or "- Unknown"
    directions_text = "\n".join(f"{i+1}. {x}" for i, x in enumerate(directions[:20])) or "Unknown"

    return f"""
Estimate nutrition for this recipe.

Recipe title:
{title}

Ingredients:
{ingredients_text}

Directions:
{directions_text}

Rules:
- Estimate PER SERVING nutrition.
- Infer servings if possible from title, ingredients, or directions.
- If unclear, make a reasonable guess.
- Return ONLY valid JSON.
- Use numbers only for numeric fields.
- confidence should be between 0 and 1.
- Keep reason under 20 words.

Required JSON format:
{{
  "servings": 4,
  "calories": 520,
  "protein_g": 34,
  "carbs_g": 28,
  "fat_g": 31,
  "confidence": 0.78,
  "reason": "Estimated from chicken, cheese, tortillas, and oil."
}}
""".strip()

def extract_json(text):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    raise ValueError("No valid JSON found in model response")

def estimate_row(row):
    prompt = build_prompt(row)

    response = client.responses.create(
        model="gpt-5-mini",
        input=[
            {
                "role": "system",
                "content": "You estimate recipe nutrition. Output strict JSON only."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    text = response.output_text
    data = extract_json(text)

    return {
        "estimated_servings": data.get("servings"),
        "estimated_calories": data.get("calories"),
        "estimated_protein_g": data.get("protein_g"),
        "estimated_carbs_g": data.get("carbs_g"),
        "estimated_fat_g": data.get("fat_g"),
        "nutrition_confidence": data.get("confidence"),
        "nutrition_reason": data.get("reason"),
        "nutrition_source": "llm_estimated"
    }

def main():
    df = pd.read_csv(INPUT_CSV)

    if MAX_ROWS is not None:
        df = df.head(MAX_ROWS).copy()

    df["normalized_title"] = df["title"].apply(normalize_title)
    df = df.drop_duplicates(subset=["normalized_title"]).copy()

    for col in [
        "estimated_servings",
        "estimated_calories",
        "estimated_protein_g",
        "estimated_carbs_g",
        "estimated_fat_g",
        "nutrition_confidence",
        "nutrition_reason",
        "nutrition_source"
    ]:
        if col not in df.columns:
            df[col] = None

    unfinished = df.index[df["nutrition_source"].fillna("").astype(str) == ""]
    total = len(unfinished)

    for count, idx in enumerate(unfinished, start=1):
        row = df.loc[idx]
        title = safe_str(row.get("title", ""))[:80]

        try:
            result = estimate_row(row)
            for k, v in result.items():
                df.at[idx, k] = v
            print(f"[{count}/{total}] OK: {title}", flush=True)
        except Exception as e:
            df.at[idx, "nutrition_source"] = "error"
            df.at[idx, "nutrition_reason"] = str(e)[:300]
            print(f"[{count}/{total}] ERROR: {title} -> {e}", flush=True)

        if count % CHECKPOINT_EVERY == 0:
            df.to_csv(OUTPUT_CSV, index=False)
            print(f"Checkpoint saved to {OUTPUT_CSV}", flush=True)

        time.sleep(SLEEP_BETWEEN_CALLS)

    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Done. Saved to {OUTPUT_CSV}", flush=True)

if __name__ == "__main__":
    main()
