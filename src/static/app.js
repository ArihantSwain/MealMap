let currentDiet = "";
let currentRecipes = [];
let currentMatches = [];
let selectedFood = "";
let currentModel = "svd";
let autocompleteTimer = null;

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const clearFiltersButton = document.getElementById("clearFiltersButton");
const recipesGrid = document.getElementById("recipesGrid");
const statusMessage = document.getElementById("statusMessage");
const filterButtons = document.querySelectorAll(".filter-btn");
const activeState = document.getElementById("activeState");
const resultsTitle = document.getElementById("resultsTitle");
const metaPills = document.getElementById("metaPills");
const modelSelect = document.getElementById("modelSelect");
const matchDropdown = document.getElementById("matchDropdown");

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

function displayValue(value, suffix = "") {
  if (value === null || value === undefined || value === "" || String(value).toLowerCase() === "nan") return "N/A";
  return `${escapeHtml(value)}${suffix}`;
}

function niceDietLabel(diet) {
  if (!diet) return "None";
  return diet
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function niceModelLabel(model) {
  return model === "tfidf" ? "TF-IDF" : "SVD";
}

function normalizeList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value)
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function updateActiveState() {
  const pieces = [];
  if (selectedFood) pieces.push(`Query: ${selectedFood}`);
  pieces.push(`Model: ${niceModelLabel(currentModel)}`);
  if (currentDiet) pieces.push(`Goal: ${niceDietLabel(currentDiet)}`);
  activeState.innerHTML = pieces.map((piece) => `<span class="state-pill">${escapeHtml(piece)}</span>`).join("");
}

function updateResultsTitle(prefix = "Results") {
  if (!selectedFood) {
    resultsTitle.textContent = "Search to get started";
    return;
  }
  resultsTitle.textContent = `${prefix} for "${selectedFood}"`;
}
function hideMatchDropdown() {
  currentMatches = [];
  matchDropdown.innerHTML = "";
  matchDropdown.classList.add("hidden");
}

function showMatchDropdown() {
  matchDropdown.classList.remove("hidden");
}
function renderMatchDropdown(matches) {
  currentMatches = matches || [];

  if (!currentMatches.length) {
    matchDropdown.innerHTML = `<div class="match-dropdown-empty">No close matches found.</div>`;
    showMatchDropdown();
    return;
  }

  matchDropdown.innerHTML = currentMatches
    .slice(0, 8)
    .map(
      (match, index) => `
        <button class="match-dropdown-item" type="button" data-index="${index}">
          <div class="match-dropdown-title">${escapeHtml(match.title || "Untitled")}</div>
          <div class="match-dropdown-meta">
            <span>${escapeHtml(niceModelLabel(match.retrieval_method || currentModel))}</span>
            <span>Similarity ${displayValue(match.similarity_score, "%")}</span>
            <span>${escapeHtml(match.nutrition_status || "Nutrition info")}</span>
          </div>
        </button>
      `
    )
    .join("");

  showMatchDropdown();

  document.querySelectorAll(".match-dropdown-item").forEach((button) => {
    button.addEventListener("click", () => {
      const match = currentMatches[Number(button.dataset.index)];
      if (!match) return;

      selectedFood = match.title || "";
      searchInput.value = selectedFood;
      hideMatchDropdown();
      updateActiveState();
      updateResultsTitle("Recipes");
      fetchRecommendations(selectedFood);
    });
  });
}

function recipeCard(recipe, index) {
  const title = recipe.title || "Untitled Recipe";
  return `
    <article class="card clickable-card" data-index="${index}" role="button" tabindex="0">
      <div class="card-top">
        <div>
          <h3>${escapeHtml(title)}</h3>
          <div class="meta-row">
            <span class="badge">Similarity ${displayValue(recipe.similarity_score, "%")}</span>
            <span class="badge">${escapeHtml(niceModelLabel(recipe.retrieval_method || currentModel))}</span>
            <span class="badge">Model ${displayValue(recipe.model_score, "%")}</span>
            <span class="badge">TF-IDF ${displayValue(recipe.tfidf_score, "%")}</span>
            <span class="badge">Servings ${displayValue(recipe.servings)}</span>
            <span class="badge">${escapeHtml(recipe.nutrition_status || "Nutrition info")}</span>
            ${recipe.diet ? `<span class="badge accent">${escapeHtml(niceDietLabel(recipe.diet))}</span>` : ""}
          </div>
        </div>
      </div>

      <div class="nutrition-grid">
        <div class="nutrition-box"><div class="label">Calories</div><div class="value">${displayValue(recipe.calories)}</div></div>
        <div class="nutrition-box"><div class="label">Protein</div><div class="value">${displayValue(recipe.protein_g, "g")}</div></div>
        <div class="nutrition-box"><div class="label">Carbs</div><div class="value">${displayValue(recipe.carbs_g, "g")}</div></div>
        <div class="nutrition-box"><div class="label">Fat</div><div class="value">${displayValue(recipe.fat_g, "g")}</div></div>
        <div class="nutrition-box"><div class="label">Fiber</div><div class="value">${displayValue(recipe.fiber_g, "g")}</div></div>
        <div class="nutrition-box"><div class="label">Sodium</div><div class="value">${displayValue(recipe.sodium_mg, " mg")}</div></div>
      </div>

      <p class="open-hint">Open full recipe</p>
    </article>
  `;
}

function renderRecipes(recipes) {
  currentRecipes = recipes;

  if (!recipes.length) {
    recipesGrid.innerHTML = "";
    setStatus("No recipes found.", true);
    return;
  }

  recipesGrid.innerHTML = recipes.map((recipe, index) => recipeCard(recipe, index)).join("");
  setStatus(`Showing ${recipes.length} recipes using ${niceModelLabel(currentModel)}.`);
  document.querySelectorAll(".clickable-card").forEach((card) => {
    const open = () => {
      const index = Number(card.dataset.index);
      openRecipeModal(currentRecipes[index]);
    };

    card.addEventListener("click", open);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        open();
      }
    });
  });
}


function listMarkup(items, ordered = false) {
  const cleanItems = normalizeList(items);
  if (!cleanItems.length) return `<p class="empty-copy">Not available.</p>`;
  const tag = ordered ? "ol" : "ul";
  return `<${tag} class="recipe-list">${cleanItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>`;
}

function openRecipeModal(recipe) {
  if (!recipe) return;

  modalBody.innerHTML = `
    <div class="modal-header">
      <p class="modal-kicker">${recipe.diet ? escapeHtml(niceDietLabel(recipe.diet)) : "MealMap Recipe"}</p>
      <h2 class="modal-title">${escapeHtml(recipe.title || "Untitled Recipe")}</h2>
      <div class="meta-row">
        <span class="badge">Similarity ${displayValue(recipe.similarity_score, "%")}</span>
        <span class="badge">${escapeHtml(niceModelLabel(recipe.retrieval_method || currentModel))}</span>
        <span class="badge">Model ${displayValue(recipe.model_score, "%")}</span>
        <span class="badge">TF-IDF ${displayValue(recipe.tfidf_score, "%")}</span>
        <span class="badge">Servings ${displayValue(recipe.servings)}</span>
        <span class="badge">${escapeHtml(recipe.nutrition_status || "Nutrition info")}</span>
      </div>
    </div>

    <div class="modal-nutrition-grid">
      <div class="nutrition-box"><div class="label">Calories</div><div class="value">${displayValue(recipe.calories)}</div></div>
      <div class="nutrition-box"><div class="label">Protein</div><div class="value">${displayValue(recipe.protein_g, "g")}</div></div>
      <div class="nutrition-box"><div class="label">Carbs</div><div class="value">${displayValue(recipe.carbs_g, "g")}</div></div>
      <div class="nutrition-box"><div class="label">Fat</div><div class="value">${displayValue(recipe.fat_g, "g")}</div></div>
      <div class="nutrition-box"><div class="label">Fiber</div><div class="value">${displayValue(recipe.fiber_g, "g")}</div></div>
      <div class="nutrition-box"><div class="label">Sodium</div><div class="value">${displayValue(recipe.sodium_mg, " mg")}</div></div>
    </div>

    <section class="modal-section">
      <h4>Ingredients</h4>
      ${listMarkup(recipe.ingredients, false)}
    </section>

    <section class="modal-section">
      <h4>Directions</h4>
      ${listMarkup(recipe.directions, true)}
    </section>

    ${
      recipe.link
        ? `<section class="modal-section">
             <a class="recipe-link" href="${escapeHtml(recipe.link)}" target="_blank" rel="noopener noreferrer">Open original recipe source</a>
           </section>`
        : ""
    }
  `;

  recipeModal.classList.remove("hidden");
  recipeModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeRecipeModal() {
  recipeModal.classList.add("hidden");
  recipeModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

async function fetchMeta() {
  try {
    const response = await fetch("/mealmap/meta");
    const data = await response.json();
    currentModel = data.default_retrieval_model || "svd";
    modelSelect.value = currentModel;
    metaPills.innerHTML = `
      <span class="state-pill">Recipes: ${escapeHtml(data.dataset_size)}</span>
      <span class="state-pill">Nutrition coverage: ${escapeHtml(data.nutrition_coverage)}%</span>
      <span class="state-pill">SVD comps: ${escapeHtml(data.svd_components)}</span>
      <span class="state-pill">Variance: ${escapeHtml(data.svd_explained_variance)}%</span>
    `;
    updateActiveState();
  } catch {
    metaPills.innerHTML = "";
  }
}

async function fetchMatchSuggestions(query) {
  const cleanQuery = (query || "").trim();

  if (!cleanQuery) {
    hideMatchDropdown();
    return;
  }

  currentModel = modelSelect.value || "svd";

  try {
    const response = await fetch(
      `/mealmap/matches?query=${encodeURIComponent(cleanQuery)}&profile=${encodeURIComponent(currentDiet || "none")}&model=${encodeURIComponent(currentModel)}`
    );
    const data = await response.json();
    renderMatchDropdown(data.matches || []);
  } catch (error) {
    console.error(error);
    hideMatchDropdown();
  }
}

async function fetchRecommendations(selected) {
  selectedFood = selected;
  currentModel = modelSelect.value || "svd";
  updateActiveState();
  updateResultsTitle("Recipes");
  recipesGrid.innerHTML = "";
  setStatus(`Loading recipes with ${niceModelLabel(currentModel)}...`);

  try {
    const response = await fetch(
      `/mealmap/recommend?selected=${encodeURIComponent(selected)}&profile=${encodeURIComponent(currentDiet || "none")}&model=${encodeURIComponent(currentModel)}`
    );
    const data = await response.json();
    hideMatchDropdown();
    renderRecipes(data.recipes || []);
  } catch (error) {
    console.error(error);
    setStatus("Could not load recipes.", true);
  }
}

searchButton.addEventListener("click", () => {
  if (currentMatches.length) {
    const firstMatch = currentMatches[0];
    selectedFood = firstMatch.title || "";
    searchInput.value = selectedFood;
    hideMatchDropdown();
    fetchRecommendations(selectedFood);
    return;
  }

  const query = searchInput.value.trim();
  if (!query) {
    setStatus("Type a dish before searching.", true);
    return;
  }

  fetchRecommendations(query);
});

searchInput.addEventListener("input", () => {
  const query = searchInput.value.trim();
  selectedFood = "";
  updateActiveState();
  updateResultsTitle();

  clearTimeout(autocompleteTimer);

  if (!query) {
    hideMatchDropdown();
    return;
  }

  autocompleteTimer = setTimeout(() => {
    fetchMatchSuggestions(query);
  }, 250);
});

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();

    if (currentMatches.length) {
      const firstMatch = currentMatches[0];
      selectedFood = firstMatch.title || "";
      searchInput.value = selectedFood;
      hideMatchDropdown();
      fetchRecommendations(selectedFood);
      return;
    }

    const query = searchInput.value.trim();
    if (!query) {
      setStatus("Type a dish before searching.", true);
      return;
    }

    fetchRecommendations(query);
  }

  if (event.key === "Escape") {
    hideMatchDropdown();
  }
});

modelSelect.addEventListener("change", () => {
  currentModel = modelSelect.value || "svd";
  updateActiveState();

  const query = searchInput.value.trim();

  if (selectedFood) {
    fetchRecommendations(selectedFood);
  } else if (query) {
    fetchMatchSuggestions(query);
  }
});

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const clickedDiet = button.dataset.diet;

    if (currentDiet === clickedDiet) {
      currentDiet = "";
      button.classList.remove("active");
    } else {
      currentDiet = clickedDiet;
      filterButtons.forEach((btn) => btn.classList.remove("active"));
      button.classList.add("active");
    }

    updateActiveState();

    if (selectedFood) {
      fetchRecommendations(selectedFood);
    } else {
      const query = searchInput.value.trim();
      if (query) fetchMatchSuggestions(query);
    }
  });
});

clearFiltersButton.addEventListener("click", () => {
  currentDiet = "";
  filterButtons.forEach((btn) => btn.classList.remove("active"));
  updateActiveState();

  if (selectedFood) {
    fetchRecommendations(selectedFood);
  } else {
    const query = searchInput.value.trim();
    if (query) fetchMatchSuggestions(query);
  }
});

closeModalButton.addEventListener("click", closeRecipeModal);
modalBackdrop.addEventListener("click", closeRecipeModal);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !recipeModal.classList.contains("hidden")) {
    closeRecipeModal();
  }
});

document.addEventListener("click", (event) => {
  const clickedInside =
    searchInput.contains(event.target) ||
    searchButton.contains(event.target) ||
    matchDropdown.contains(event.target);

  if (!clickedInside) {
    hideMatchDropdown();
  }
});

fetchMeta();
updateActiveState();
