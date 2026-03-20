let currentDiet = "";
let currentRecipes = [];

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const recipesGrid = document.getElementById("recipesGrid");
const statusMessage = document.getElementById("statusMessage");
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

async function fetchRecipes() {
  const query = searchInput.value.trim();
  const params = new URLSearchParams();

  if (query) params.append("query", query);
  if (currentDiet) params.append("diet", currentDiet);

  setStatus("Loading recipes...");
  recipesGrid.innerHTML = "";

  try {
    const response = await fetch(`/recipes?${params.toString()}`);
    if (!response.ok) {
      throw new Error(`Request failed: ${response.status}`);
    }

    const data = await response.json();
    const recipes = Array.isArray(data) ? data : (Array.isArray(data.recipes) ? data.recipes : []);
    renderRecipes(recipes);
  } catch (err) {
    console.error(err);
    setStatus("Could not load recipes from the backend.", true);
  }
}

searchButton.addEventListener("click", fetchRecipes);

searchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    fetchRecipes();
  }
});

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    filterButtons.forEach((btn) => btn.classList.remove("active"));
    button.classList.add("active");
    currentDiet = button.dataset.diet || "";
    fetchRecipes();
  });
});

modalBackdrop.addEventListener("click", closeModal);
closeModalButton.addEventListener("click", closeModal);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !recipeModal.classList.contains("hidden")) {
    closeModal();
  }
});

fetchRecipes();
