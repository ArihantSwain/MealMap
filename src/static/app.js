let currentDiet = "";
let currentRecipes = [];
let selectedFood = "";

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const recipesGrid = document.getElementById("recipesGrid");
const statusMessage = document.getElementById("statusMessage");
const nutrientFilters = document.getElementById("nutrientFilters");
const filterButtons = document.querySelectorAll(".filter-btn");

const recipeModal = document.getElementById("recipeModal");
const modalBackdrop = document.getElementById("modalBackdrop");
const closeModalButton = document.getElementById("closeModalButton");
const modalBody = document.getElementById("modalBody");

function setStatus(message, isError = false) {
  statusMessage.textContent = message;
  statusMessage.classList.toggle("error", isError);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function parseMaybeList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;

  try {
    const parsed = JSON.parse(value);
    return Array.isArray(parsed) ? parsed : [String(value)];
  } catch {
    return String(value)
      .split(/,\s*(?=(?:[^"]*"[^"]*")*[^"]*$)/)
      .map((item) => item.trim())
      .filter(Boolean);
  }
}

function diet_prefs(dietValue) {
  return dietValue;
}

function clearActiveFilters() {
  filterButtons.forEach((btn) => btn.classList.remove("active"));
  currentDiet = "";
}

function current_prefs() {
  return diet_prefs(currentDiet || "none");
}

function showFilters() {
  nutrientFilters.classList.remove("hidden");
}

function hideFilters() {
  nutrientFilters.classList.add("hidden");
}

function recipeCard(recipe, index) {
  const title = recipe.title || recipe.name || "Untitled Recipe";

  const calories =
    recipe.calories_per_serving ??
    recipe.calories ??
    "N/A";

  const protein =
    recipe.protein_per_serving ??
    recipe.protein_g ??
    recipe.protein ??
    "N/A";

  const carbs =
    recipe.carbs_per_serving ??
    recipe.carbs_g ??
    recipe.carbs ??
    recipe.carbohydrates ??
    "N/A";

  const fat =
    recipe.fat_per_serving ??
    recipe.fat_g ??
    recipe.fat ??
    "N/A";

  const diet = recipe.diet || recipe.tags || "";
  const servings = recipe.servings ?? "N/A";

  return `
    <article class="card clickable-card" data-index="${index}" role="button" tabindex="0">
      <div class="card-body">
        <h2>${escapeHtml(title)}</h2>
        <div class="meta-row">
          <span class="badge">Servings: ${escapeHtml(servings)}</span>
          ${diet ? `<span class="badge">${escapeHtml(diet)}</span>` : ""}
        </div>
        <div class="nutrition-grid">
          <div class="nutrition-box"><div class="label">Calories</div><div class="value">${escapeHtml(calories)}</div></div>
          <div class="nutrition-box"><div class="label">Protein</div><div class="value">${escapeHtml(protein)}g</div></div>
          <div class="nutrition-box"><div class="label">Carbs</div><div class="value">${escapeHtml(carbs)}g</div></div>
          <div class="nutrition-box"><div class="label">Fat</div><div class="value">${escapeHtml(fat)}g</div></div>
        </div>
        <p class="open-hint">Click to view full recipe</p>
      </div>
    </article>
  `;
}

function select_match(title, index) {
  return `
    <article class="card">
      <div class="card-body">
        <h2>${escapeHtml(title)}</h2>
        <p>Did you mean this food?</p>
        <button class="match-select-btn" data-index="${index}">Use This</button>
      </div>
    </article>
  `;
}

function renderRecipes(recipes) {
  currentRecipes = recipes;

  if (!recipes.length) {
    recipesGrid.innerHTML = "";
    setStatus("No recipes found.");
    return;
  }

  recipesGrid.innerHTML = recipes.map((recipe, index) => recipeCard(recipe, index)).join("");
  setStatus("");
  attachCardListeners();
}

function display_cards(matches) {
  currentRecipes = [];

  if (!matches.length) {
    recipesGrid.innerHTML = "";
    hideFilters();
    setStatus("No close matches found. Try another search.");
    return;
  }

  recipesGrid.innerHTML = matches.map((title, index) => select_match(title, index)).join("");
  setStatus("Select the food you meant, then choose a nutrient filter.");

  document.querySelectorAll(".match-select-btn").forEach((button) => {
    button.addEventListener("click", () => {
      const index = Number(button.dataset.index);
      selectedFood = matches[index];
      showFilters();
      setStatus(`Selected "${selectedFood}". Loading similar foods (none preference).`);
      fetch_similar_recipes();
    });
  });
}

function openModal(recipe) {
  const title = recipe.title || recipe.name || "Untitled Recipe";
  const ingredients = parseMaybeList(recipe.ingredients);
  const directions = parseMaybeList(recipe.directions);

  const calories =
    recipe.calories_per_serving ??
    recipe.calories ??
    "N/A";

  const protein =
    recipe.protein_per_serving ??
    recipe.protein_g ??
    recipe.protein ??
    "N/A";

  const carbs =
    recipe.carbs_per_serving ??
    recipe.carbs_g ??
    recipe.carbs ??
    recipe.carbohydrates ??
    "N/A";

  const fat =
    recipe.fat_per_serving ??
    recipe.fat_g ??
    recipe.fat ??
    "N/A";

  const fiber = recipe.fiber_g ?? "N/A";
  const sodium = recipe.sodium_mg ?? "N/A";
  const link = recipe.link ? (String(recipe.link).startsWith("http") ? recipe.link : `https://${recipe.link}`) : "";

  modalBody.innerHTML = `
    <h2 class="modal-title">${escapeHtml(title)}</h2>

    <div class="modal-nutrition-grid">
      <div class="nutrition-box"><div class="label">Calories</div><div class="value">${escapeHtml(calories)}</div></div>
      <div class="nutrition-box"><div class="label">Protein</div><div class="value">${escapeHtml(protein)}g</div></div>
      <div class="nutrition-box"><div class="label">Carbs</div><div class="value">${escapeHtml(carbs)}g</div></div>
      <div class="nutrition-box"><div class="label">Fat</div><div class="value">${escapeHtml(fat)}g</div></div>
      <div class="nutrition-box"><div class="label">Fiber</div><div class="value">${escapeHtml(fiber)}g</div></div>
      <div class="nutrition-box"><div class="label">Sodium</div><div class="value">${escapeHtml(sodium)} mg</div></div>
    </div>

    <div class="modal-section">
      <h3>Ingredients</h3>
      ${
        ingredients.length
          ? `<ul>${ingredients.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
          : `<p>No ingredients listed.</p>`
      }
    </div>

    <div class="modal-section">
      <h3>Directions</h3>
      ${
        directions.length
          ? `<ol>${directions.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol>`
          : `<p>No directions listed.</p>`
      }
    </div>

    ${
      link
        ? `<div class="modal-section"><a class="recipe-link" href="${escapeHtml(link)}" target="_blank" rel="noreferrer">Open Original Recipe</a></div>`
        : ""
    }
  `;

  recipeModal.classList.remove("hidden");
  document.body.classList.add("modal-open");
}

function closeModal() {
  recipeModal.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

function attachCardListeners() {
  document.querySelectorAll(".clickable-card").forEach((card) => {
    card.addEventListener("click", () => {
      const index = Number(card.dataset.index);
      openModal(currentRecipes[index]);
    });

    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        const index = Number(card.dataset.index);
        openModal(currentRecipes[index]);
      }
    });
  });
}

async function fetch_query_cards() {
  const query = searchInput.value.trim();
  const params = new URLSearchParams({ query });

  if (!query) {
    setStatus("Enter a food to search for.", true);
    return;
  }

  selectedFood = "";
  clearActiveFilters();
  hideFilters();

  setStatus("Finding close matches...");
  recipesGrid.innerHTML = "";

  try {
    const response = await fetch(`/mealmap/matches?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const data = await response.json();
    const matches = Array.isArray(data.matches) ? data.matches : [];
    if (matches.length === 1) {
      selectedFood = matches[0];
      showFilters();
      setStatus(`Matched "${selectedFood}". Loading similar foods (none preference).`);
      fetch_similar_recipes();
      return;
    }
    display_cards(matches);
  } catch (err) {
    console.error(err);
    setStatus("Could not load any close matches.", true);
  }
}

async function fetch_similar_recipes() {
  if (!selectedFood) {
    setStatus("Choose one of the suggested foods first.", true);
    return;
  }

  const params = new URLSearchParams({
    selected: selectedFood,
    profile: current_prefs(),
  });

  setStatus("Finding similar foods...");
  recipesGrid.innerHTML = "";

  try {
    const response = await fetch(`/mealmap/recommend?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const data = await response.json();
    const recipes = Array.isArray(data.recipes) ? data.recipes : [];
    renderRecipes(recipes);
  } catch (err) {
    console.error(err);
    setStatus("Could not load similar foods from the backend.", true);
  }
}

searchButton.addEventListener("click", fetch_query_cards);

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    fetch_query_cards();
  }
});

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    clearActiveFilters();
    button.classList.add("active");
    currentDiet = button.dataset.diet || "";
    fetch_similar_recipes();
  });
});

modalBackdrop.addEventListener("click", closeModal);
closeModalButton.addEventListener("click", closeModal);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !recipeModal.classList.contains("hidden")) {
    closeModal();
  }
});

setStatus("Search for a food to begin.");
hideFilters();
