let currentDiet = "";
let currentRecipes = [];
let currentMatches = [];
let selectedFood = "";
let currentModel = "tfidf";
let autocompleteTimer = null;
let selectedRecipeTitle = "";

// tracks titles currently in the meal plan
let planTitles = new Set();

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

const llmAnswerPanel = document.getElementById("llmAnswerPanel");
const llmAnswerText = document.getElementById("llmAnswerText");
const ragMeta = document.getElementById("ragMeta");

const recipeModal = document.getElementById("recipeModal");
const modalBackdrop = document.getElementById("modalBackdrop");
const closeModalButton = document.getElementById("closeModalButton");
const modalBody = document.getElementById("modalBody");

const mealPlanBtn = document.getElementById("mealPlanBtn");
const planBadge = document.getElementById("planBadge");
const mealPlanDrawer = document.getElementById("mealPlanDrawer");
const drawerBackdrop = document.getElementById("drawerBackdrop");
const closeDrawerBtn = document.getElementById("closeDrawerBtn");
const drawerBody = document.getElementById("drawerBody");
const drawerFooter = document.getElementById("drawerFooter");
const drawerSubtitle = document.getElementById("drawerSubtitle");

// ── Utilities ────────────────────────────────────────────────────────────────

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

// ── Search UI ─────────────────────────────────────────────────────────────────

function updateActiveState() {
  const pieces = [];
  if (selectedFood) pieces.push({ text: selectedFood, highlight: true });
  if (currentDiet) pieces.push({ text: niceDietLabel(currentDiet), highlight: false });
  activeState.innerHTML = pieces
    .map(({ text, highlight }) =>
      `<span class="state-pill${highlight ? " highlight" : ""}">${escapeHtml(text)}</span>`
    )
    .join("");
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

      selectedRecipeTitle = match.title || "";
      selectedFood = selectedRecipeTitle;
      searchInput.value = selectedRecipeTitle;
      hideMatchDropdown();
      updateActiveState();
      updateResultsTitle("Recipes");
      fetchRecommendations(selectedRecipeTitle);
    });
  });
}

function renderRagAnswer(data) {
  if (!data || !data.answer || !String(data.answer).trim()) {
    llmAnswerPanel.hidden = true;
    llmAnswerText.innerHTML = "";
    ragMeta.innerHTML = "";
    return;
  }

  llmAnswerText.innerHTML = data.answer;
  ragMeta.innerHTML = `
    <span class="badge">Original: ${escapeHtml(data.original_query || "")}</span>
    <span class="badge">Refined: ${escapeHtml(data.refined_query || "")}</span>
    <span class="badge">${escapeHtml(niceModelLabel(data.model_used || currentModel))}</span>
    ${data.profile_used && data.profile_used !== "none" ? `<span class="badge">${escapeHtml(niceDietLabel(data.profile_used))}</span>` : ""}
  `;
  llmAnswerPanel.hidden = false;
}

// ── Recipe cards ──────────────────────────────────────────────────────────────

function recipeCard(recipe, index) {
  const title = recipe.title || "Untitled Recipe";
  return `
    <article class="card clickable-card" data-index="${index}" role="button" tabindex="0">
      <div class="card-top">
        <h3>${escapeHtml(title)}</h3>
        <div class="meta-row">
          ${recipe.diet ? `<span class="badge accent">${escapeHtml(niceDietLabel(recipe.diet))}</span>` : ""}
          <span class="badge">${displayValue(recipe.servings)} servings</span>
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

      <p class="open-hint">View recipe</p>
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

// ── Recipe modal ──────────────────────────────────────────────────────────────

function listMarkup(items, ordered = false) {
  const cleanItems = normalizeList(items);
  if (!cleanItems.length) return `<p class="empty-copy">Not available.</p>`;
  const tag = ordered ? "ol" : "ul";
  return `<${tag} class="recipe-list">${cleanItems.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</${tag}>`;
}

function openRecipeModal(recipe) {
  if (!recipe) return;

  const isAdded = planTitles.has(recipe.title || "");
  const addBtnLabel = isAdded ? "✓ Added to Plan" : "+ Add to Plan";

  modalBody.innerHTML = `
    <div class="modal-header">
      <p class="modal-kicker">${recipe.diet ? escapeHtml(niceDietLabel(recipe.diet)) : "MealMap Recipe"}</p>
      <h2 class="modal-title">${escapeHtml(recipe.title || "Untitled Recipe")}</h2>
      <div class="meta-row" style="margin-bottom:16px;">
        ${recipe.diet ? `<span class="badge accent">${escapeHtml(niceDietLabel(recipe.diet))}</span>` : ""}
        <span class="badge">${displayValue(recipe.servings)} servings</span>
        <button class="add-to-plan-btn${isAdded ? " added" : ""}" id="modalAddToPlanBtn" type="button">${addBtnLabel}</button>
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
             <a class="recipe-link" href="${escapeHtml(/^https?:\/\//i.test(recipe.link) ? recipe.link : "https://" + recipe.link.replace(/^www\./, ""))}" target="_blank" rel="noopener noreferrer">Open original recipe source</a>
           </section>`
        : ""
    }
  `;

  document.getElementById("modalAddToPlanBtn").addEventListener("click", () => {
    addToPlan(recipe);
  });

  recipeModal.classList.remove("hidden");
  recipeModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeRecipeModal() {
  recipeModal.classList.add("hidden");
  recipeModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

// ── Meal plan drawer ──────────────────────────────────────────────────────────

function updatePlanBadge() {
  const count = planTitles.size;
  planBadge.textContent = count;
  planBadge.classList.toggle("hidden", count === 0);
}

function openDrawer() {
  mealPlanDrawer.classList.remove("hidden");
  mealPlanDrawer.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  renderPlanView();
}

function closeDrawer() {
  mealPlanDrawer.classList.add("hidden");
  mealPlanDrawer.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
}

function renderPlanView() {
  fetch("/mealplan")
    .then((r) => r.json())
    .then(({ plan }) => {
      planTitles = new Set(plan.map((r) => r.title));
      updatePlanBadge();
      drawerSubtitle.textContent = plan.length
        ? `${plan.length} recipe${plan.length === 1 ? "" : "s"}`
        : "";

      if (!plan.length) {
        drawerBody.innerHTML = `
          <div class="drawer-empty">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
              <rect x="9" y="3" width="6" height="4" rx="1"/>
              <line x1="9" y1="12" x2="15" y2="12"/>
            </svg>
            <p>No recipes yet. Open a recipe and click "Add to Plan".</p>
          </div>
        `;
        drawerFooter.innerHTML = "";
        return;
      }

      drawerBody.innerHTML = plan
        .map(
          (r) => `
          <div class="plan-item">
            <div class="plan-item-info">
              <div class="plan-item-title">${escapeHtml(r.title)}</div>
              <div class="plan-item-meta">${r.ingredients.length} ingredient${r.ingredients.length === 1 ? "" : "s"}${r.servings ? ` · ${escapeHtml(String(r.servings))} servings` : ""}</div>
            </div>
            <button class="remove-plan-btn" data-title="${escapeHtml(r.title)}" title="Remove">&times;</button>
          </div>
        `
        )
        .join("");

      document.querySelectorAll(".remove-plan-btn").forEach((btn) => {
        btn.addEventListener("click", () => removeFromPlan(btn.dataset.title));
      });

      drawerFooter.innerHTML = `
        <button class="full-width-btn" id="getShoppingListBtn">Get Shopping List</button>
        <button class="full-width-btn secondary" id="clearPlanBtn">Clear Plan</button>
      `;

      document.getElementById("getShoppingListBtn").addEventListener("click", renderShoppingList);
      document.getElementById("clearPlanBtn").addEventListener("click", clearPlan);
    });
}

function renderShoppingList() {
  fetch("/mealplan/shopping-list")
    .then((r) => r.json())
    .then(({ items, recipe_count }) => {
      drawerSubtitle.textContent = `${recipe_count} recipe${recipe_count === 1 ? "" : "s"}`;

      drawerBody.innerHTML = `
        <button class="shopping-back-btn" id="backToPlanBtn">← Back to plan</button>
        <p class="shopping-section-label">${items.length} item${items.length === 1 ? "" : "s"}</p>
        ${
          items.length
            ? items
                .map(
                  (item, i) => `
                  <div class="shopping-item" id="si-${i}">
                    <input type="checkbox" id="cb-${i}" />
                    <label for="cb-${i}">${escapeHtml(item)}</label>
                  </div>
                `
                )
                .join("")
            : `<p style="color:var(--muted);font-size:14px;">No ingredients found.</p>`
        }
      `;

      // toggle strikethrough on check
      document.querySelectorAll(".shopping-item input").forEach((cb) => {
        cb.addEventListener("change", () => {
          cb.closest(".shopping-item").classList.toggle("checked", cb.checked);
        });
      });

      document.getElementById("backToPlanBtn").addEventListener("click", renderPlanView);

      drawerFooter.innerHTML = `
        <button class="full-width-btn secondary" id="copyListBtn">Copy to clipboard</button>
      `;

      document.getElementById("copyListBtn").addEventListener("click", () => {
        navigator.clipboard.writeText(items.join("\n")).then(() => {
          const btn = document.getElementById("copyListBtn");
          btn.textContent = "Copied!";
          setTimeout(() => { btn.textContent = "Copy to clipboard"; }, 2000);
        });
      });
    });
}

// ── Meal plan actions ─────────────────────────────────────────────────────────

async function addToPlan(recipe) {
  const btn = document.getElementById("modalAddToPlanBtn");
  if (!btn) return;

  const res = await fetch("/mealplan/add", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: recipe.title,
      ingredients: normalizeList(recipe.ingredients),
      servings: recipe.servings || "",
    }),
  });
  const data = await res.json();

  planTitles = new Set(data.plan.map((r) => r.title));
  updatePlanBadge();

  btn.textContent = "✓ Added to Plan";
  btn.classList.add("added");
}

async function removeFromPlan(title) {
  const res = await fetch("/mealplan/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  const data = await res.json();
  planTitles = new Set(data.plan.map((r) => r.title));
  updatePlanBadge();
  renderPlanView();
}

async function clearPlan() {
  const plan = await fetch("/mealplan").then((r) => r.json()).then((d) => d.plan);
  for (const recipe of plan) {
    await fetch("/mealplan/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: recipe.title }),
    });
  }
  planTitles.clear();
  updatePlanBadge();
  renderPlanView();
}

// ── Data fetching ─────────────────────────────────────────────────────────────

async function fetchMeta() {
  try {
    const response = await fetch("/mealmap/meta");
    const data = await response.json();
    currentModel = data.default_retrieval_model || "tfidf";
    modelSelect.value = currentModel;
    metaPills.innerHTML = `
      <span class="state-pill">${escapeHtml(data.dataset_size)} recipes</span>
      <span class="state-pill">${escapeHtml(data.nutrition_coverage)}% with nutrition data</span>
    `;
    updateActiveState();
  } catch {
    metaPills.innerHTML = "";
  }
}

async function fetchRagAnswer(query) {
  const cleanQuery = (query || "").trim();
  if (!cleanQuery) {
    setStatus("Type a dish before searching.", true);
    return;
  }

  setStatus("Refining query and retrieving recipes...");
  currentModel = modelSelect.value || "svd";

  try {
    const response = await fetch("/mealmap/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: cleanQuery,
        profile: currentDiet || "none",
        model: currentModel
      })
    });

    const data = await response.json();

    if (!response.ok) {
      setStatus(data.error || "Could not load RAG response.", true);
      return;
    }

    selectedFood = data.refined_query || cleanQuery;
    selectedRecipeTitle = "";
    searchInput.value = selectedFood;
    currentModel = data.model_used || currentModel;
    modelSelect.value = currentModel;

    updateActiveState();
    updateResultsTitle("Matches");
    renderRagAnswer(data);
    renderRecipes(data.matches || []);
    hideMatchDropdown();
    setStatus(`Showing retrieved recipes for refined query: ${data.refined_query}`);
  } catch (error) {
    console.error(error);
    setStatus("Could not load RAG response.", true);
  }
}

async function fetchMatchSuggestions(query) {
  const cleanQuery = (query || "").trim();

  if (!cleanQuery) {
    hideMatchDropdown();
    return;
  }

  currentModel = modelSelect.value || "tfidf";

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
  selectedRecipeTitle = selected;
  selectedFood = selected;
  llmAnswerPanel.hidden = true;
  llmAnswerText.textContent = "";
  ragMeta.innerHTML = "";
  currentModel = modelSelect.value || "tfidf";
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

// ── Event listeners ───────────────────────────────────────────────────────────

searchButton.addEventListener("click", () => {
  const query = searchInput.value.trim();
  if (!query) {
    setStatus("Type a dish before searching.", true);
    return;
  }

  hideMatchDropdown();
  fetchRagAnswer(query);
});

searchInput.addEventListener("input", () => {
  const query = searchInput.value.trim();
  selectedFood = "";
  selectedRecipeTitle = "";
  updateActiveState();
  updateResultsTitle();

  llmAnswerPanel.hidden = true;
  llmAnswerText.innerHTML = "";
  ragMeta.innerHTML = "";

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

    const query = searchInput.value.trim();
    if (!query) {
      setStatus("Type a dish before searching.", true);
      return;
    }

    hideMatchDropdown();
    fetchRagAnswer(query);
  }

  if (event.key === "Escape") {
    hideMatchDropdown();
  }
});

modelSelect.addEventListener("change", () => {
  currentModel = modelSelect.value || "tfidf";
  updateActiveState();

  const query = searchInput.value.trim();

  if (selectedRecipeTitle) {
    fetchRecommendations(selectedRecipeTitle);
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

    if (selectedRecipeTitle) {
      fetchRecommendations(selectedRecipeTitle);
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

  if (selectedRecipeTitle) {
    fetchRecommendations(selectedRecipeTitle);
  } else {
    const query = searchInput.value.trim();
    if (query) fetchMatchSuggestions(query);
  }
});

closeModalButton.addEventListener("click", closeRecipeModal);
modalBackdrop.addEventListener("click", closeRecipeModal);

mealPlanBtn.addEventListener("click", openDrawer);
closeDrawerBtn.addEventListener("click", closeDrawer);
drawerBackdrop.addEventListener("click", closeDrawer);

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (!recipeModal.classList.contains("hidden")) closeRecipeModal();
    else if (!mealPlanDrawer.classList.contains("hidden")) closeDrawer();
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

// ── Init ──────────────────────────────────────────────────────────────────────

fetch("/mealplan")
  .then((r) => r.json())
  .then(({ plan }) => {
    planTitles = new Set(plan.map((r) => r.title));
    updatePlanBadge();
  });

llmAnswerPanel.hidden = true;
llmAnswerText.innerHTML = "";
ragMeta.innerHTML = "";

fetchMeta();
updateActiveState();
