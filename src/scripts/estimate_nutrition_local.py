import pandas as pd
import re
import ast

INPUT_CSV = "../../data/raw/recipes_data.csv"
OUTPUT_CSV = "../../data/recipes_enriched.csv"
MAX_ROWS = 10000

# Expanded nutrition DB: values are per typical serving/unit in a recipe
# (cal, protein, carbs, fat, fiber, sodium)
NUTRITION_DB = {
    # Proteins
    "chicken": {"cal": 165, "protein": 31, "carbs": 0, "fat": 3.6, "fiber": 0, "sodium": 74},
    "beef": {"cal": 250, "protein": 26, "carbs": 0, "fat": 15, "fiber": 0, "sodium": 72},
    "pork": {"cal": 242, "protein": 27, "carbs": 0, "fat": 14, "fiber": 0, "sodium": 62},
    "turkey": {"cal": 135, "protein": 30, "carbs": 0, "fat": 1, "fiber": 0, "sodium": 60},
    "lamb": {"cal": 250, "protein": 26, "carbs": 0, "fat": 16, "fiber": 0, "sodium": 65},
    "bacon": {"cal": 90, "protein": 6, "carbs": 0, "fat": 7, "fiber": 0, "sodium": 300},
    "sausage": {"cal": 180, "protein": 8, "carbs": 1, "fat": 16, "fiber": 0, "sodium": 500},
    "ham": {"cal": 145, "protein": 21, "carbs": 1.5, "fat": 6, "fiber": 0, "sodium": 1200},
    "fish": {"cal": 136, "protein": 20, "carbs": 0, "fat": 6, "fiber": 0, "sodium": 60},
    "salmon": {"cal": 208, "protein": 20, "carbs": 0, "fat": 13, "fiber": 0, "sodium": 59},
    "tuna": {"cal": 130, "protein": 28, "carbs": 0, "fat": 1, "fiber": 0, "sodium": 40},
    "shrimp": {"cal": 85, "protein": 20, "carbs": 0, "fat": 0.5, "fiber": 0, "sodium": 190},
    "crab": {"cal": 97, "protein": 19, "carbs": 0, "fat": 1.5, "fiber": 0, "sodium": 320},
    "lobster": {"cal": 90, "protein": 19, "carbs": 0, "fat": 0.9, "fiber": 0, "sodium": 380},
    "tofu": {"cal": 76, "protein": 8, "carbs": 2, "fat": 4.5, "fiber": 0.3, "sodium": 7},
    "tempeh": {"cal": 195, "protein": 20, "carbs": 8, "fat": 11, "fiber": 0, "sodium": 9},
    "egg": {"cal": 70, "protein": 6, "carbs": 1, "fat": 5, "fiber": 0, "sodium": 70},
    "perch": {"cal": 100, "protein": 21, "carbs": 0, "fat": 1, "fiber": 0, "sodium": 70},
    "cod": {"cal": 82, "protein": 18, "carbs": 0, "fat": 0.7, "fiber": 0, "sodium": 54},
    "tilapia": {"cal": 96, "protein": 20, "carbs": 0, "fat": 1.7, "fiber": 0, "sodium": 52},
    "catfish": {"cal": 105, "protein": 18, "carbs": 0, "fat": 3, "fiber": 0, "sodium": 50},
    "venison": {"cal": 158, "protein": 30, "carbs": 0, "fat": 3.2, "fiber": 0, "sodium": 54},
    "duck": {"cal": 201, "protein": 23, "carbs": 0, "fat": 11, "fiber": 0, "sodium": 65},

    # Dairy
    "cheese": {"cal": 110, "protein": 7, "carbs": 1, "fat": 9, "fiber": 0, "sodium": 180},
    "cheddar": {"cal": 113, "protein": 7, "carbs": 0.4, "fat": 9.3, "fiber": 0, "sodium": 185},
    "mozzarella": {"cal": 85, "protein": 6, "carbs": 1, "fat": 6, "fiber": 0, "sodium": 175},
    "parmesan": {"cal": 110, "protein": 10, "carbs": 1, "fat": 7, "fiber": 0, "sodium": 390},
    "cream cheese": {"cal": 100, "protein": 2, "carbs": 1, "fat": 10, "fiber": 0, "sodium": 90},
    "milk": {"cal": 120, "protein": 8, "carbs": 12, "fat": 5, "fiber": 0, "sodium": 100},
    "cream": {"cal": 50, "protein": 0.4, "carbs": 0.5, "fat": 5, "fiber": 0, "sodium": 5},
    "butter": {"cal": 100, "protein": 0, "carbs": 0, "fat": 11, "fiber": 0, "sodium": 90},
    "yogurt": {"cal": 100, "protein": 6, "carbs": 12, "fat": 3, "fiber": 0, "sodium": 70},
    "sour cream": {"cal": 60, "protein": 1, "carbs": 1, "fat": 6, "fiber": 0, "sodium": 15},
    "whey": {"cal": 100, "protein": 20, "carbs": 3, "fat": 0.5, "fiber": 0, "sodium": 50},
    "cottage cheese": {"cal": 100, "protein": 12, "carbs": 4, "fat": 4, "fiber": 0, "sodium": 360},
    "buttermilk": {"cal": 100, "protein": 8, "carbs": 12, "fat": 2, "fiber": 0, "sodium": 250},
    "margarine": {"cal": 100, "protein": 0, "carbs": 0, "fat": 11, "fiber": 0, "sodium": 90},
    "muenster": {"cal": 104, "protein": 7, "carbs": 0.3, "fat": 8.5, "fiber": 0, "sodium": 178},

    # Grains & starches
    "rice": {"cal": 200, "protein": 4, "carbs": 45, "fat": 1, "fiber": 1, "sodium": 5},
    "pasta": {"cal": 220, "protein": 8, "carbs": 43, "fat": 1, "fiber": 2, "sodium": 1},
    "noodle": {"cal": 220, "protein": 8, "carbs": 40, "fat": 2, "fiber": 2, "sodium": 5},
    "bread": {"cal": 80, "protein": 3, "carbs": 15, "fat": 1, "fiber": 1, "sodium": 150},
    "tortilla": {"cal": 120, "protein": 3, "carbs": 20, "fat": 3, "fiber": 1, "sodium": 300},
    "flour": {"cal": 100, "protein": 3, "carbs": 21, "fat": 1, "fiber": 1, "sodium": 2},
    "oat": {"cal": 150, "protein": 5, "carbs": 27, "fat": 3, "fiber": 4, "sodium": 0},
    "cereal": {"cal": 110, "protein": 2, "carbs": 24, "fat": 1, "fiber": 1, "sodium": 200},
    "cornstarch": {"cal": 30, "protein": 0, "carbs": 7, "fat": 0, "fiber": 0, "sodium": 1},
    "cornmeal": {"cal": 110, "protein": 2, "carbs": 24, "fat": 1, "fiber": 2, "sodium": 5},
    "cracker": {"cal": 70, "protein": 1, "carbs": 11, "fat": 2.5, "fiber": 0, "sodium": 120},
    "biscuit": {"cal": 120, "protein": 2, "carbs": 17, "fat": 5, "fiber": 0.5, "sodium": 300},
    "pretzel": {"cal": 110, "protein": 3, "carbs": 23, "fat": 1, "fiber": 1, "sodium": 400},
    "quinoa": {"cal": 220, "protein": 8, "carbs": 39, "fat": 3.5, "fiber": 5, "sodium": 13},
    "couscous": {"cal": 175, "protein": 6, "carbs": 36, "fat": 0.3, "fiber": 2, "sodium": 8},
    "barley": {"cal": 190, "protein": 4, "carbs": 44, "fat": 0.7, "fiber": 6, "sodium": 5},

    # Vegetables
    "potato": {"cal": 160, "protein": 4, "carbs": 37, "fat": 0, "fiber": 4, "sodium": 17},
    "sweet potato": {"cal": 115, "protein": 2, "carbs": 27, "fat": 0, "fiber": 4, "sodium": 70},
    "onion": {"cal": 20, "protein": 0.5, "carbs": 5, "fat": 0, "fiber": 1, "sodium": 2},
    "garlic": {"cal": 5, "protein": 0.2, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "tomato": {"cal": 20, "protein": 1, "carbs": 4, "fat": 0, "fiber": 1, "sodium": 5},
    "corn": {"cal": 80, "protein": 3, "carbs": 19, "fat": 1, "fiber": 2, "sodium": 15},
    "carrot": {"cal": 25, "protein": 0.5, "carbs": 6, "fat": 0, "fiber": 2, "sodium": 40},
    "broccoli": {"cal": 30, "protein": 2.5, "carbs": 6, "fat": 0.3, "fiber": 2.5, "sodium": 30},
    "spinach": {"cal": 7, "protein": 1, "carbs": 1, "fat": 0, "fiber": 0.7, "sodium": 24},
    "pepper": {"cal": 20, "protein": 0.7, "carbs": 5, "fat": 0, "fiber": 1.5, "sodium": 2},
    "celery": {"cal": 6, "protein": 0.3, "carbs": 1, "fat": 0, "fiber": 0.6, "sodium": 32},
    "lettuce": {"cal": 5, "protein": 0.5, "carbs": 1, "fat": 0, "fiber": 0.5, "sodium": 5},
    "cabbage": {"cal": 22, "protein": 1, "carbs": 5, "fat": 0, "fiber": 2, "sodium": 16},
    "mushroom": {"cal": 15, "protein": 2, "carbs": 2, "fat": 0, "fiber": 1, "sodium": 4},
    "zucchini": {"cal": 20, "protein": 1.5, "carbs": 4, "fat": 0, "fiber": 1, "sodium": 10},
    "squash": {"cal": 40, "protein": 1, "carbs": 10, "fat": 0, "fiber": 2, "sodium": 4},
    "pumpkin": {"cal": 30, "protein": 1, "carbs": 8, "fat": 0, "fiber": 1, "sodium": 1},
    "pea": {"cal": 60, "protein": 4, "carbs": 10, "fat": 0, "fiber": 3.5, "sodium": 3},
    "asparagus": {"cal": 20, "protein": 2.2, "carbs": 4, "fat": 0, "fiber": 2, "sodium": 2},
    "cauliflower": {"cal": 25, "protein": 2, "carbs": 5, "fat": 0, "fiber": 2, "sodium": 30},
    "cucumber": {"cal": 8, "protein": 0.3, "carbs": 2, "fat": 0, "fiber": 0.3, "sodium": 1},
    "eggplant": {"cal": 25, "protein": 1, "carbs": 6, "fat": 0, "fiber": 3, "sodium": 2},
    "artichoke": {"cal": 60, "protein": 3, "carbs": 13, "fat": 0, "fiber": 7, "sodium": 120},
    "kale": {"cal": 33, "protein": 3, "carbs": 6, "fat": 0.6, "fiber": 1.3, "sodium": 25},
    "beet": {"cal": 35, "protein": 1.3, "carbs": 8, "fat": 0, "fiber": 2, "sodium": 65},
    "turnip": {"cal": 28, "protein": 0.9, "carbs": 6, "fat": 0, "fiber": 2, "sodium": 55},
    "radish": {"cal": 12, "protein": 0.5, "carbs": 2.5, "fat": 0, "fiber": 1, "sodium": 30},
    "parsnip": {"cal": 55, "protein": 1, "carbs": 13, "fat": 0, "fiber": 4, "sodium": 8},
    "leek": {"cal": 30, "protein": 1, "carbs": 7, "fat": 0, "fiber": 1, "sodium": 12},
    "avocado": {"cal": 160, "protein": 2, "carbs": 9, "fat": 15, "fiber": 7, "sodium": 7},
    "olive": {"cal": 40, "protein": 0.3, "carbs": 2, "fat": 4, "fiber": 1, "sodium": 310},

    # Legumes
    "bean": {"cal": 120, "protein": 8, "carbs": 21, "fat": 0.5, "fiber": 8, "sodium": 5},
    "lentil": {"cal": 115, "protein": 9, "carbs": 20, "fat": 0.4, "fiber": 8, "sodium": 2},
    "chickpea": {"cal": 135, "protein": 7, "carbs": 23, "fat": 2, "fiber": 6, "sodium": 6},
    "hummus": {"cal": 70, "protein": 3, "carbs": 6, "fat": 4, "fiber": 2, "sodium": 150},

    # Fruits
    "apple": {"cal": 52, "protein": 0.3, "carbs": 14, "fat": 0, "fiber": 2.4, "sodium": 1},
    "banana": {"cal": 89, "protein": 1, "carbs": 23, "fat": 0, "fiber": 2.6, "sodium": 1},
    "orange": {"cal": 47, "protein": 1, "carbs": 12, "fat": 0, "fiber": 2.4, "sodium": 0},
    "lemon": {"cal": 12, "protein": 0.4, "carbs": 4, "fat": 0, "fiber": 0.2, "sodium": 1},
    "lime": {"cal": 10, "protein": 0.3, "carbs": 3.5, "fat": 0, "fiber": 0, "sodium": 1},
    "strawberry": {"cal": 30, "protein": 0.6, "carbs": 7, "fat": 0, "fiber": 2, "sodium": 1},
    "blueberry": {"cal": 40, "protein": 0.5, "carbs": 10, "fat": 0, "fiber": 2, "sodium": 1},
    "raspberry": {"cal": 32, "protein": 0.7, "carbs": 7, "fat": 0, "fiber": 4, "sodium": 1},
    "grape": {"cal": 62, "protein": 0.6, "carbs": 16, "fat": 0, "fiber": 0.8, "sodium": 2},
    "peach": {"cal": 39, "protein": 0.9, "carbs": 10, "fat": 0, "fiber": 1.5, "sodium": 0},
    "pear": {"cal": 57, "protein": 0.4, "carbs": 15, "fat": 0, "fiber": 3, "sodium": 1},
    "cherry": {"cal": 50, "protein": 1, "carbs": 12, "fat": 0, "fiber": 1.6, "sodium": 0},
    "pineapple": {"cal": 50, "protein": 0.5, "carbs": 13, "fat": 0, "fiber": 1.4, "sodium": 1},
    "mango": {"cal": 60, "protein": 0.8, "carbs": 15, "fat": 0, "fiber": 1.6, "sodium": 1},
    "coconut": {"cal": 180, "protein": 2, "carbs": 7, "fat": 17, "fiber": 5, "sodium": 10},
    "raisin": {"cal": 85, "protein": 1, "carbs": 22, "fat": 0, "fiber": 1, "sodium": 3},
    "cranberry": {"cal": 46, "protein": 0.4, "carbs": 12, "fat": 0, "fiber": 4.6, "sodium": 2},
    "plum": {"cal": 30, "protein": 0.5, "carbs": 8, "fat": 0, "fiber": 1, "sodium": 0},
    "apricot": {"cal": 17, "protein": 0.5, "carbs": 4, "fat": 0, "fiber": 0.7, "sodium": 0},
    "fig": {"cal": 37, "protein": 0.4, "carbs": 10, "fat": 0, "fiber": 1.5, "sodium": 1},
    "date": {"cal": 70, "protein": 0.5, "carbs": 18, "fat": 0, "fiber": 2, "sodium": 0},
    "watermelon": {"cal": 30, "protein": 0.6, "carbs": 8, "fat": 0, "fiber": 0.4, "sodium": 1},
    "cantaloupe": {"cal": 34, "protein": 0.8, "carbs": 8, "fat": 0, "fiber": 0.9, "sodium": 16},

    # Nuts & seeds
    "almond": {"cal": 160, "protein": 6, "carbs": 6, "fat": 14, "fiber": 3, "sodium": 0},
    "walnut": {"cal": 185, "protein": 4, "carbs": 4, "fat": 18, "fiber": 2, "sodium": 1},
    "pecan": {"cal": 195, "protein": 3, "carbs": 4, "fat": 20, "fiber": 3, "sodium": 0},
    "cashew": {"cal": 155, "protein": 5, "carbs": 9, "fat": 12, "fiber": 1, "sodium": 3},
    "peanut": {"cal": 160, "protein": 7, "carbs": 5, "fat": 14, "fiber": 2, "sodium": 5},
    "peanut butter": {"cal": 190, "protein": 7, "carbs": 7, "fat": 16, "fiber": 2, "sodium": 140},
    "pistachio": {"cal": 160, "protein": 6, "carbs": 8, "fat": 13, "fiber": 3, "sodium": 1},
    "sunflower": {"cal": 165, "protein": 6, "carbs": 7, "fat": 14, "fiber": 2, "sodium": 1},
    "sesame": {"cal": 160, "protein": 5, "carbs": 7, "fat": 14, "fiber": 3, "sodium": 3},
    "flax": {"cal": 55, "protein": 2, "carbs": 3, "fat": 4, "fiber": 3, "sodium": 3},
    "chia": {"cal": 58, "protein": 2, "carbs": 5, "fat": 4, "fiber": 5, "sodium": 2},

    # Oils & fats
    "oil": {"cal": 120, "protein": 0, "carbs": 0, "fat": 14, "fiber": 0, "sodium": 0},
    "olive oil": {"cal": 120, "protein": 0, "carbs": 0, "fat": 14, "fiber": 0, "sodium": 0},
    "shortening": {"cal": 115, "protein": 0, "carbs": 0, "fat": 13, "fiber": 0, "sodium": 0},
    "lard": {"cal": 115, "protein": 0, "carbs": 0, "fat": 13, "fiber": 0, "sodium": 0},
    "mayonnaise": {"cal": 94, "protein": 0, "carbs": 0, "fat": 10, "fiber": 0, "sodium": 88},

    # Sweeteners & baking
    "sugar": {"cal": 50, "protein": 0, "carbs": 13, "fat": 0, "fiber": 0, "sodium": 1},
    "honey": {"cal": 60, "protein": 0, "carbs": 17, "fat": 0, "fiber": 0, "sodium": 1},
    "maple syrup": {"cal": 52, "protein": 0, "carbs": 13, "fat": 0, "fiber": 0, "sodium": 2},
    "molasses": {"cal": 58, "protein": 0, "carbs": 15, "fat": 0, "fiber": 0, "sodium": 7},
    "chocolate": {"cal": 150, "protein": 2, "carbs": 17, "fat": 9, "fiber": 2, "sodium": 7},
    "cocoa": {"cal": 12, "protein": 1, "carbs": 3, "fat": 0.7, "fiber": 2, "sodium": 1},
    "vanilla": {"cal": 12, "protein": 0, "carbs": 0.5, "fat": 0, "fiber": 0, "sodium": 1},
    "baking powder": {"cal": 2, "protein": 0, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 360},
    "baking soda": {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 630},
    "gelatin": {"cal": 23, "protein": 6, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 14},
    "yeast": {"cal": 12, "protein": 1.5, "carbs": 1.5, "fat": 0.2, "fiber": 0.8, "sodium": 4},
    "jam": {"cal": 56, "protein": 0, "carbs": 14, "fat": 0, "fiber": 0.2, "sodium": 6},
    "jelly": {"cal": 56, "protein": 0, "carbs": 14, "fat": 0, "fiber": 0.2, "sodium": 6},

    # Condiments & sauces
    "salt": {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 500},
    "soy sauce": {"cal": 10, "protein": 1, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 900},
    "vinegar": {"cal": 3, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 1},
    "ketchup": {"cal": 20, "protein": 0, "carbs": 5, "fat": 0, "fiber": 0, "sodium": 160},
    "mustard": {"cal": 3, "protein": 0.2, "carbs": 0.3, "fat": 0.2, "fiber": 0, "sodium": 55},
    "worcestershire": {"cal": 13, "protein": 0, "carbs": 3, "fat": 0, "fiber": 0, "sodium": 200},
    "hot sauce": {"cal": 1, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 125},
    "salsa": {"cal": 10, "protein": 0.5, "carbs": 2, "fat": 0, "fiber": 0.5, "sodium": 200},
    "broth": {"cal": 5, "protein": 1, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 400},
    "stock": {"cal": 5, "protein": 1, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 400},
    "bouillon": {"cal": 5, "protein": 1, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 800},
    "tomato sauce": {"cal": 30, "protein": 1, "carbs": 6, "fat": 0, "fiber": 1.5, "sodium": 500},
    "tomato paste": {"cal": 25, "protein": 1, "carbs": 5, "fat": 0, "fiber": 1, "sodium": 20},
    "barbecue sauce": {"cal": 30, "protein": 0, "carbs": 7, "fat": 0, "fiber": 0, "sodium": 250},
    "ranch": {"cal": 73, "protein": 0.5, "carbs": 1, "fat": 8, "fiber": 0, "sodium": 200},
    "teriyaki": {"cal": 16, "protein": 1, "carbs": 3, "fat": 0, "fiber": 0, "sodium": 610},

    # Spices (small impact but avoids zero-match)
    "cinnamon": {"cal": 6, "protein": 0, "carbs": 2, "fat": 0, "fiber": 1, "sodium": 0},
    "cumin": {"cal": 8, "protein": 0.4, "carbs": 1, "fat": 0.5, "fiber": 0, "sodium": 4},
    "paprika": {"cal": 6, "protein": 0.3, "carbs": 1, "fat": 0.3, "fiber": 0, "sodium": 1},
    "oregano": {"cal": 5, "protein": 0.2, "carbs": 1, "fat": 0, "fiber": 0.5, "sodium": 0},
    "basil": {"cal": 1, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0},
    "thyme": {"cal": 3, "protein": 0, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "rosemary": {"cal": 4, "protein": 0, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "parsley": {"cal": 2, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 3},
    "ginger": {"cal": 5, "protein": 0, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "nutmeg": {"cal": 12, "protein": 0, "carbs": 1, "fat": 1, "fiber": 0, "sodium": 0},
    "chili": {"cal": 6, "protein": 0.3, "carbs": 1, "fat": 0.3, "fiber": 0.5, "sodium": 3},
    "curry": {"cal": 7, "protein": 0.3, "carbs": 1, "fat": 0.3, "fiber": 0, "sodium": 3},
    "tarragon": {"cal": 5, "protein": 0.2, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "dill": {"cal": 3, "protein": 0.2, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 2},
    "sage": {"cal": 6, "protein": 0.2, "carbs": 1, "fat": 0.3, "fiber": 0.5, "sodium": 0},
    "clove": {"cal": 6, "protein": 0, "carbs": 1, "fat": 0.3, "fiber": 0.5, "sodium": 5},
    "allspice": {"cal": 5, "protein": 0, "carbs": 1, "fat": 0, "fiber": 0, "sodium": 1},
    "turmeric": {"cal": 9, "protein": 0.3, "carbs": 2, "fat": 0, "fiber": 0.5, "sodium": 1},

    # Misc
    "wine": {"cal": 85, "protein": 0, "carbs": 3, "fat": 0, "fiber": 0, "sodium": 5},
    "beer": {"cal": 43, "protein": 0.5, "carbs": 4, "fat": 0, "fiber": 0, "sodium": 4},
    "water": {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0},
    "juice": {"cal": 45, "protein": 0.5, "carbs": 11, "fat": 0, "fiber": 0, "sodium": 5},
    "whipped cream": {"cal": 25, "protein": 0.3, "carbs": 2, "fat": 2, "fiber": 0, "sodium": 5},
    "marshmallow": {"cal": 90, "protein": 0.5, "carbs": 23, "fat": 0, "fiber": 0, "sodium": 20},
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


def stem_word(word):
    """Simple stemmer: strips common plural/verb suffixes to match DB keys."""
    if len(word) <= 3:
        return word
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith("es") and len(word) > 4:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def extract_keywords(text):
    return re.findall(r"[a-z]+", str(text).lower())


def extract_ner_phrases(ner_str):
    """Parse NER column and return multi-word ingredient phrases."""
    try:
        parsed = ast.literal_eval(str(ner_str))
        if isinstance(parsed, list):
            return [str(item).strip().lower() for item in parsed if str(item).strip()]
    except Exception:
        pass
    return []


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


def estimate_nutrition(title, ingredients, directions, ner=""):
    """Estimate nutrition by matching NER phrases and individual words to NUTRITION_DB."""
    total = {"cal": 0, "protein": 0, "carbs": 0, "fat": 0, "fiber": 0, "sodium": 0}
    matched = set()

    # First pass: match multi-word NER phrases (e.g., "cream cheese", "sour cream")
    ner_phrases = extract_ner_phrases(ner)
    for phrase in ner_phrases:
        phrase_lower = phrase.strip()
        if phrase_lower in NUTRITION_DB:
            matched.add(phrase_lower)
            for k in total:
                total[k] += NUTRITION_DB[phrase_lower][k]
            continue

        # Try stemmed version of the phrase
        stemmed = " ".join(stem_word(w) for w in phrase_lower.split())
        if stemmed in NUTRITION_DB and stemmed not in matched:
            matched.add(stemmed)
            for k in total:
                total[k] += NUTRITION_DB[stemmed][k]
            continue

        # Try individual words from this phrase
        for word in phrase_lower.split():
            stemmed_w = stem_word(word)
            key = None
            if word in NUTRITION_DB:
                key = word
            elif stemmed_w in NUTRITION_DB:
                key = stemmed_w
            if key and key not in matched:
                matched.add(key)
                for k in total:
                    total[k] += NUTRITION_DB[key][k]

    # Second pass: pick up anything from title + ingredients text not already matched
    words = extract_keywords(f"{title} {ingredients}")
    for word in words:
        stemmed_w = stem_word(word)
        key = None
        if word in NUTRITION_DB:
            key = word
        elif stemmed_w in NUTRITION_DB:
            key = stemmed_w
        if key and key not in matched:
            matched.add(key)
            for k in total:
                total[k] += NUTRITION_DB[key][k]

    if len(matched) == 0:
        return None

    servings = estimate_servings(title, ingredients, directions)
    if servings < 1:
        servings = 1

    base_divisor = max(min(len(matched) / 2, 12), 1)
    recipe_multiplier = max(servings / 2, 1)

    per_serving = {
        "estimated_servings": servings,
        "estimated_calories": round(max(total["cal"] * recipe_multiplier / base_divisor, 1), 1),
        "estimated_protein_g": round(max(total["protein"] * recipe_multiplier / base_divisor, 0), 1),
        "estimated_carbs_g": round(max(total["carbs"] * recipe_multiplier / base_divisor, 0), 1),
        "estimated_fat_g": round(max(total["fat"] * recipe_multiplier / base_divisor, 0), 1),
        "estimated_fiber_g": round(max(total["fiber"] * recipe_multiplier / base_divisor, 0), 1),
        "estimated_sodium_mg": round(max(total["sodium"] * recipe_multiplier / base_divisor, 0), 1),
        "nutrition_source": "rule_estimated",
        "nutrition_confidence": round(min(0.35 + 0.08 * len(matched), 0.92), 2),
        "matched_ingredient_keywords": ", ".join(sorted(matched)),
    }

    return per_serving


def main():
    df = pd.read_csv(INPUT_CSV)

    if MAX_ROWS:
        df = df.head(MAX_ROWS).copy()

    matched_count = 0
    for i, row in df.iterrows():
        title = str(row.get("title", ""))
        ingredients = str(row.get("ingredients", ""))
        directions = str(row.get("directions", ""))
        ner = str(row.get("NER", ""))

        est = estimate_nutrition(title, ingredients, directions, ner)

        if est:
            matched_count += 1
            for k, v in est.items():
                df.at[i, k] = v

        if i % 500 == 0:
            print(f"{i} processed ({matched_count} matched so far)")

    total = len(df)
    print(f"\nDone: {matched_count}/{total} recipes matched ({100*matched_count/total:.1f}%)")
    df.to_csv(OUTPUT_CSV, index=False)
    print("Saved to", OUTPUT_CSV)


if __name__ == "__main__":
    main()


def backfill_missing(csv_path):
    """Fill zero/missing nutrition values with median from recipes that have data."""
    df = pd.read_csv(csv_path)

    nutrient_cols = [
        "estimated_calories",
        "estimated_protein_g",
        "estimated_carbs_g",
        "estimated_fat_g",
        "estimated_fiber_g",
        "estimated_sodium_mg",
    ]

    for col in nutrient_cols:
        if col not in df.columns:
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        median_val = round(numeric[numeric > 0].median(), 1)
        before = (numeric.isna() | (numeric == 0)).sum()
        df[col] = numeric.fillna(0)
        df.loc[df[col] == 0, col] = median_val
        after = (pd.to_numeric(df[col], errors="coerce") == 0).sum()
        print(f"  {col}: filled {before} zeros/nulls with median {median_val} -> {after} zeros remain")

    # Mark backfilled rows
    if "nutrition_confidence" not in df.columns:
        df["nutrition_confidence"] = 0.5
    if "nutrition_source" not in df.columns:
        df["nutrition_source"] = "rule_estimated"

    df.to_csv(csv_path, index=False)
    print(f"Saved backfilled data to {csv_path}")


if __name__ == "__main__":
    pass  # main() already ran above
