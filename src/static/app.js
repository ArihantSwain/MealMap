let currentDiet = "";

const searchInput = document.getElementById("searchInput");
const searchButton = document.getElementById("searchButton");
const recipesGrid = document.getElementById("recipesGrid");
const statusMessage = document.getElementById("statusMessage");
const filterButtons = document.querySelectorAll(".filter-btn");

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

function recipeCard(recipe) {
  const title = recipe.title || recipe.name || "Untitled Recipe";
  const image = recipe.image || recipe.image_url || "";
  const servings = recipe.servings ?? "N/A";
  const calories = recipe.calories_per_serving ?? recipe.calories ?? "N/A";
  const protein = recipe.protein_per_serving ?? recipe.protein ?? "N/A";
  const carbs = recipe.carbs_per_serving ?? recipe.carbs ?? "N/A";
  const fat = recipe.fat_per_serving ?? recipe.fat ?? "N/A";
  const diet = recipe.diet || recipe.tags || "";
  const url = recipe.url || "";

  return `
    <article class="card">
      ${
        image
          ? `<img class="card-image" src="${escapeHtml(image)}" alt="${escapeHtml(title)}" />`
          : `<div class="card-image placeholder">No Image</div>`
      }
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
        ${
          url
            ? `<a class="recipe-link" href="${escapeHtml(url)}" target="_blank" rel="noreferrer">View Recipe</a>`
            : ""
        }
      </div>
    </article>
  `;
}

function renderRecipes(recipes) {
  if (!recipes.length) {
    recipesGrid.innerHTML = "";
    setStatus("No recipes found.");
    return;
  }

  recipesGrid.innerHTML = recipes.map(recipeCard).join("");
  setStatus("");
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

fetchRecipes();
