import pandas as pd
import numpy as np
import ast

input_csv = "recipes_data.csv"

name_ingredient_map = {}
name_calorie_map = {}
name_vector_map = {}
name_similarity_map = {}

all_ingredients = set()

def dot_product(name_vec_map, sample_dish_vector):
    np_sample_dish_vector = np.array(sample_dish_vector)
    for name in name_vec_map:
        np_dish_vector = np.array(name_vec_map[name])
        name_similarity_map[name] = np.dot(np_sample_dish_vector, np_dish_vector)

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

    df = pd.read_csv(input_csv)
    df = df.dropna(subset=["title", "NER"])

    for i, row in df.iterrows():
        name_ingredient_map[row["title"]] = ast.literal_eval(row["NER"])

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
        

    for name in name_ingredient_map:
        ingredient_list = name_ingredient_map[name]
        for ingredient in ingredient_list:
            all_ingredients.add(ingredient)

    all_ingredients_list = sorted(all_ingredients)

    for name in name_ingredient_map:
        ingredient_list = name_ingredient_map[name]
        vector = [1 if ingredient in ingredient_list else 0 for ingredient in all_ingredients_list]
        name_vector_map[name] = vector

    sample_dish_vector = name_vector_map[similar_dish]

    dot_product(name_vector_map, sample_dish_vector)

    ranked_dishes = sorted(
        name_similarity_map.items(),
        key=lambda x: x[1],
        reverse=True
    )

    count = 0
    for name, score in ranked_dishes:
        if name != similar_dish:
            print(count, ": ", name)
            count += 1
        if count == 10:
            break

    

if __name__ == "__main__":
    main()