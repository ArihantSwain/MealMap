import pandas as pd
import ast
import heapq

input_csv = "recipes_data.csv"

name_ingredient_map = {}

def find_matching_dishes(sample_dish, name_ingredient_map):
    matches = []
    sample = sample_dish.lower()

    for name in name_ingredient_map:
        lower_name = name.lower()
        if lower_name == sample:
            return [name]
        if sample in lower_name:
            matches.append(name)

    return matches

def main():
    df = pd.read_csv(input_csv, usecols=["title", "NER"])
    df = df.dropna(subset=["title", "NER"])

    for row in df.itertuples(index=False):
        title = row.title
        ingredients = set(ast.literal_eval(row.NER))
        name_ingredient_map[title] = ingredients

    # Uncomment these lines when we add dietary filtering to the implementation:
    # calories_per_meal = input("Enter the number of calories you would like in each meal: ")
    # nutrients_to_maximize = input("Which nutrients do you want to prioritize most (enter as a comma separated list -- ie. protein, carbohydrates): ")

    sample_dish = input("Name a dish we should model suggestions based off of: ")

    matches = find_matching_dishes(sample_dish, name_ingredient_map)

    while len(matches) == 0:
        sample_dish = input("That dish isn't in our database, try another one: ")
        matches = find_matching_dishes(sample_dish, name_ingredient_map)

    if len(matches) == 1:
        similar_dish = matches[0]
    else:
        print("\nI found multiple matches:")
        for i, name in enumerate(matches[:10], start=1):
            print(f"{i}: {name}")

        choice = int(input("Choose the number of the dish you meant: "))
        similar_dish = matches[choice - 1]

    sample_ingredients = name_ingredient_map[similar_dish]

    top_matches = heapq.nlargest(
        10,
        (
            (len(sample_ingredients & ingredients), name)
            for name, ingredients in name_ingredient_map.items()
            if name != similar_dish
        )
    )

    print(f"\nTop dishes most similar to {similar_dish}:\n")
    for i, (score, name) in enumerate(top_matches, start=1):
        print(f"{i}: {name} ({score} shared ingredients)")

if __name__ == "__main__":
    main()