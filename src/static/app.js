const selectedDiets = new Set();
function currentProfileParam() {
  return selectedDiets.size ? Array.from(selectedDiets).join(",") : "none";
}
function dietLabelList(raw) {
  if (!raw) return [];
  if (Array.isArray(raw)) return raw.filter(Boolean);
  return String(raw).split(",").map((s) => s.trim()).filter(Boolean);
}
let currentRecipes = [];
let currentMatches = [];
let selectedFood = "";
let currentModel = "tfidf";
let defaultMealmapModel = "tfidf";
let autocompleteTimer = null;
let selectedRecipeTitle = "";
let lastUserQuery = "";
let retrievalExplainQuery = "";
let uiBusyCount = 0;
let ragRequestToken = 0;
let recommendRequestToken = 0;

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
const showListingDropdown = document.getElementById("showListingDropdown");

const queryBreakdownBody = document.getElementById("queryBreakdownBody");
const queryBreakdownEmpty = document.getElementById("queryBreakdownEmpty");
const queryRadarMount = document.getElementById("queryRadarMount");
const queryBreakdownExplain = document.getElementById("queryBreakdownExplain");
const queryBreakdownBadge = document.getElementById("queryBreakdownBadge");

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
  const parts = String(diet)
    .split(",")
    .map((p) => p.trim())
    .filter(Boolean);
  return parts
    .map((piece) =>
      piece
        .split("_")
        .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ")
    )
    .join(", ");
}

function niceModelLabel(model) {
  return model === "tfidf" ? "TF-IDF" : "SVD";
}

function recipeSourceUrl(recipe) {
  const raw = String(recipe?.link || recipe?.source || recipe?.site || "").trim();
  if (!raw) return "";
  if (/^https?:\/\//i.test(raw)) return raw.replace(/^https?:\/\/www\./i, (m) => (m.toLowerCase().startsWith("https") ? "https://" : "http://"));
  return `https://${raw.replace(/^www\./i, "")}`;
}

function normalizeExternalUrl(raw) {
  const text = String(raw || "").trim();
  if (!text) return "";
  if (/^https?:\/\//i.test(text)) {
    return text.replace(/^https?:\/\/www\./i, (m) => (m.toLowerCase().startsWith("https") ? "https://" : "http://"));
  }
  if (/^\/\//.test(text)) return `https:${text}`.replace(/^https:\/\/www\./i, "https://");
  if (/^[a-z0-9.-]+\.[a-z]{2,}(\/.*)?$/i.test(text)) return `https://${text.replace(/^www\./i, "")}`;
  return "";
}

function syncModelFromUI() {
  currentModel = (modelSelect && modelSelect.value) || defaultMealmapModel;
}

function setUiBusy(isBusy) {
  const disabled = Boolean(isBusy);
  if (searchButton) searchButton.disabled = disabled;
  if (clearFiltersButton) clearFiltersButton.disabled = disabled;
  filterButtons.forEach((btn) => {
    btn.disabled = disabled;
  });
}

function beginBusy() {
  uiBusyCount += 1;
  setUiBusy(true);
}

function endBusy() {
  uiBusyCount = Math.max(0, uiBusyCount - 1);
  if (uiBusyCount === 0) setUiBusy(false);
}

function getActiveProfiles() {
  return Array.from(selectedDiets);
}

function normalizeList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return String(value)
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
}

function drawRadarChart(mountEl, labels, values, options = {}) {
  if (!mountEl || !labels?.length || !values?.length || labels.length !== values.length) {
    if (mountEl) mountEl.innerHTML = "";
    return;
  }
  const vb = options.viewBox ?? 420;
  const cx = vb / 2;
  const cy = vb / 2;
  const maxR = options.maxRadius ?? 128;
  const n = labels.length;
  const levels = [0.25, 0.5, 0.75, 1];
  const fill = options.fill ?? "rgba(22, 101, 52, 0.18)";
  const stroke = options.stroke ?? "#15803d";
  const gridStroke = options.gridStroke ?? "rgba(120, 113, 108, 0.28)";
  const labelFont = options.labelFontSize ?? 16;

  const angle = (i) => -Math.PI / 2 + (2 * Math.PI * i) / n;
  const pt = (i, t) => {
    const a = angle(i);
    return [cx + maxR * t * Math.cos(a), cy + maxR * t * Math.sin(a)];
  };

  let g = `<defs><style>.radar-label{font-family:Raleway,system-ui,sans-serif;font-size:${labelFont}px;font-weight:700;fill:#44403c;text-transform:capitalize}</style></defs>`;
  for (const lev of levels) {
    const pts = [];
    for (let i = 0; i < n; i++) {
      const [x, y] = pt(i, lev);
      pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    }
    g += `<polygon fill="none" stroke="${gridStroke}" stroke-width="1" points="${pts.join(" ")}"/>`;
  }
  for (let i = 0; i < n; i++) {
    const [x, y] = pt(i, 1);
    g += `<line x1="${cx}" y1="${cy}" x2="${x.toFixed(1)}" y2="${y.toFixed(1)}" stroke="${gridStroke}" stroke-width="1"/>`;
  }
  const polyPts = [];
  for (let i = 0; i < n; i++) {
    const t = Math.max(0, Math.min(1, Number(values[i]) || 0));
    const [x, y] = pt(i, t);
    polyPts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  g += `<polygon fill="${fill}" stroke="${stroke}" stroke-width="1.6" points="${polyPts.join(" ")}"/>`;

  const labelR = maxR + (options.labelOffset ?? 52);
  for (let i = 0; i < n; i++) {
    const a = angle(i);
    const lx = cx + labelR * Math.cos(a);
    const ly = cy + labelR * Math.sin(a);
    const raw = String(labels[i] || "");
    const short = raw.length > 20 ? `${raw.slice(0, 17)}…` : raw;
    g += `<text class="radar-label" x="${lx.toFixed(1)}" y="${ly.toFixed(1)}" text-anchor="middle" dominant-baseline="middle">${escapeHtml(short)}</text>`;
  }

  mountEl.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${vb} ${vb}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Topic radar">${g}</svg>`;
}

function resetQueryBreakdownToEmpty() {
  if (!queryBreakdownBody || !queryBreakdownEmpty || !queryRadarMount) return;
  queryBreakdownBody.classList.add("hidden");
  queryBreakdownEmpty.classList.remove("hidden");
  queryBreakdownEmpty.textContent = "Run a search to see which terms influenced the ranking!";
  queryRadarMount.innerHTML = "";
  if (queryBreakdownExplain) queryBreakdownExplain.textContent = "";
  if (queryBreakdownBadge) queryBreakdownBadge.textContent = "—";
}

async function updateQueryBreakdownPanel(queryText) {
  if (!queryBreakdownBody || !queryRadarMount || !queryBreakdownEmpty) return;
  const q = (queryText || "").trim();
  if (!q) {
    resetQueryBreakdownToEmpty();
    return;
  }
  try {
    const res = await fetch(`/mealmap/svd-explain?query=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "SVD explain failed");
    if (queryBreakdownBadge) {
      queryBreakdownBadge.textContent =
        data.svd_component_count != null && data.svd_component_count !== undefined
          ? String(data.svd_component_count)
          : "—";
    }
    if (!data.available) {
      queryBreakdownBody.classList.add("hidden");
      queryBreakdownEmpty.classList.remove("hidden");
      queryBreakdownEmpty.textContent = data.hint || "SVD breakdown is not available.";
      return;
    }
    queryBreakdownEmpty.classList.add("hidden");
    queryBreakdownBody.classList.remove("hidden");
    drawRadarChart(queryRadarMount, data.axes, data.query_strength, {
      fill: currentModel === "svd" ? "rgba(22, 101, 52, 0.2)" : "rgba(100, 116, 139, 0.16)",
      stroke: currentModel === "svd" ? "#15803d" : "#64748b",
      maxRadius: 126,
      labelOffset: 50,
      labelFontSize: 14,
    });
    const note =
      currentModel === "svd"
        ? ""
        : "Results are ranked with TF‑IDF right now; this chart still maps your wording into the same SVD topic space used for semantic search. ";
    if (queryBreakdownExplain) queryBreakdownExplain.textContent = `${note}${data.explanation || ""}`;
  } catch {
    queryBreakdownBody.classList.add("hidden");
    queryBreakdownEmpty.classList.remove("hidden");
    queryBreakdownEmpty.textContent = "Could not load topic breakdown.";
  }
}

async function loadCardWhyExplain(card, recipe) {
  const explainEl = card.querySelector(".why-explain");
  const mount = card.querySelector(".card-radar-mount");
  if (!explainEl || !mount) return;
  const title = recipe?.title || "";
  const q =
    retrievalExplainQuery.trim() || lastUserQuery.trim() || searchInput.value.trim();
  explainEl.textContent = "Loading…";
  mount.innerHTML = "";
  if (!q || !title) {
    explainEl.textContent = "Run a search first so we can compare your retrieval text to this recipe.";
    return;
  }
  try {
    const res = await fetch(
      `/mealmap/svd-explain?query=${encodeURIComponent(q)}&title=${encodeURIComponent(title)}`
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "SVD explain failed");
    if (!data.available) {
      explainEl.textContent = data.hint || "Explanation not available.";
      return;
    }
    const vals =
      Array.isArray(data.match_strength) && data.match_strength.length
        ? data.match_strength
        : data.query_strength;
    drawRadarChart(mount, data.axes, vals, {
      fill: "rgba(22, 101, 52, 0.22)",
      stroke: "#15803d",
      maxRadius: 106,
      labelOffset: 34,
      labelFontSize: 12,
    });
    const cos = Number(data.cosine_similarity);
    const simPct = Number.isFinite(cos) ? Math.max(0, Math.min(100, Math.round(cos * 100))) : null;
    const simLine = simPct == null ? "" : `Estimated topic similarity: ${simPct}%. `;
    explainEl.textContent = `${simLine}${data.explanation || "This chart shows why this recipe aligns with your query in latent topic space."}`;
  } catch {
    explainEl.textContent = "Could not load explanation.";
  }
}

// ── Search UI ─────────────────────────────────────────────────────────────────

function updateActiveState() {
  const pieces = [];
  if (selectedFood) pieces.push({ text: selectedFood, highlight: true });
  for (const diet of selectedDiets) {
    pieces.push({ text: niceDietLabel(diet), highlight: false });
  }
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
  if (showListingDropdown && !showListingDropdown.checked) {
    hideMatchDropdown();
    return;
  }

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

      lastUserQuery = searchInput.value.trim();
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
  llmAnswerText.querySelectorAll("a").forEach((a) => {
    const normalized = normalizeExternalUrl(a.getAttribute("href") || a.textContent || "");
    if (!normalized) return;
    a.setAttribute("href", normalized);
    a.setAttribute("target", "_blank");
    a.setAttribute("rel", "noopener noreferrer");
  });
  ragMeta.innerHTML = `
    <span class="badge">Original: ${escapeHtml(data.original_query || "")}</span>
    <span class="badge">Refined: ${escapeHtml(data.refined_query || "")}</span>
    <span class="badge">${escapeHtml(niceModelLabel(data.model_used || currentModel))}</span>
    ${dietLabelList(data.profile_used).map((d) => `<span class="badge">${escapeHtml(niceDietLabel(d))}</span>`).join("")}
  `;
  llmAnswerPanel.hidden = false;
}

// ── Recipe cards ──────────────────────────────────────────────────────────────

function recipeCard(recipe, index) {
  const title = recipe.title || "Untitled Recipe";
  return `
    <article class="card recipe-flip-card" data-index="${index}" tabindex="0" aria-expanded="false">
      <div class="flip-inner">
        <div class="flip-face flip-front">
          <div class="card-top">
            <h3>${escapeHtml(title)}</h3>
            <div class="meta-row">
              ${dietLabelList(recipe.diet).map((d) => `<span class="badge accent">${escapeHtml(niceDietLabel(d))}</span>`).join("")}
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

          <button type="button" class="why-chosen-btn">See why this was chosen</button>
          <p class="open-hint">View recipe</p>
        </div>
        <div class="flip-face flip-back">
          <button type="button" class="flip-back-btn">← Back to recipe</button>
          <p class="latent-kicker">Latent dimensions</p>
          <p class="why-explain">Loading explanation...</p>
          <div class="card-radar-wrap">
            <div class="card-radar-mount" aria-label="Recipe topic radar"></div>
          </div>
        </div>
      </div>
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
      <p class="modal-kicker">${dietLabelList(recipe.diet).length ? dietLabelList(recipe.diet).map((d) => escapeHtml(niceDietLabel(d))).join(" · ") : "MealMap Recipe"}</p>
      <h2 class="modal-title">${escapeHtml(recipe.title || "Untitled Recipe")}</h2>
      <div class="meta-row" style="margin-bottom:16px;">
        ${dietLabelList(recipe.diet).map((d) => `<span class="badge accent">${escapeHtml(niceDietLabel(d))}</span>`).join("")}
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
    defaultMealmapModel = data.default_retrieval_model || "tfidf";
    if (modelSelect) modelSelect.value = defaultMealmapModel;
    syncModelFromUI();
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
  const requestToken = ++ragRequestToken;
  beginBusy();

  llmAnswerPanel.hidden = true;
  llmAnswerText.innerHTML = "";
  ragMeta.innerHTML = "";
  recipesGrid.innerHTML = "";
  setStatus("Refining query and retrieving recipes...");
  syncModelFromUI();

  try {
    const response = await fetch("/mealmap/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        message: cleanQuery,
        profile: currentProfileParam(),
        model: currentModel
      })
    });

    const data = await response.json();
    if (requestToken !== ragRequestToken) return;

    if (!response.ok) {
      setStatus(data.error || "Could not load RAG response.", true);
      updateResultsTitle();
      return;
    }

    selectedFood = data.refined_query || cleanQuery;
    selectedRecipeTitle = "";
    lastUserQuery = cleanQuery;
    retrievalExplainQuery = data.refined_query || cleanQuery;
    searchInput.value = selectedFood;
    currentModel = data.model_used || currentModel;
    modelSelect.value = currentModel;

    updateActiveState();
    updateResultsTitle("Matches");
    renderRagAnswer(data);
    renderRecipes(data.matches || []);
    void updateQueryBreakdownPanel(retrievalExplainQuery);
    hideMatchDropdown();
    setStatus(`Showing retrieved recipes for refined query: ${data.refined_query}`);
  } catch (error) {
    if (requestToken !== ragRequestToken) return;
    console.error(error);
    setStatus("Could not load RAG response.", true);
    updateResultsTitle();
  } finally {
    endBusy();
  }
}

async function fetchMatchSuggestions(query) {
  const cleanQuery = (query || "").trim();

  if (!cleanQuery) {
    hideMatchDropdown();
    return;
  }

  if (showListingDropdown && !showListingDropdown.checked) {
    hideMatchDropdown();
    return;
  }

  syncModelFromUI();

  try {
    const response = await fetch(
      `/mealmap/matches?query=${encodeURIComponent(cleanQuery)}&profile=${encodeURIComponent(currentProfileParam())}&model=${encodeURIComponent(currentModel)}`
    );
    const data = await response.json();
    renderMatchDropdown(data.matches || []);
  } catch (error) {
    console.error(error);
    hideMatchDropdown();
  }
}

async function fetchRecommendations(selected) {
  const requestToken = ++recommendRequestToken;
  beginBusy();
  selectedRecipeTitle = selected;
  selectedFood = selected;
  llmAnswerPanel.hidden = true;
  llmAnswerText.textContent = "";
  ragMeta.innerHTML = "";
  syncModelFromUI();
  updateActiveState();
  updateResultsTitle("Recipes");
  recipesGrid.innerHTML = "";
  setStatus(`Loading recipes with ${niceModelLabel(currentModel)}...`);

  try {
    const response = await fetch(
      `/mealmap/recommend?selected=${encodeURIComponent(selected)}&profile=${encodeURIComponent(currentProfileParam())}&model=${encodeURIComponent(currentModel)}&filter_query=${encodeURIComponent(lastUserQuery)}`
    );
    const data = await response.json();
    if (requestToken !== recommendRequestToken) return;
    hideMatchDropdown();
    retrievalExplainQuery = (lastUserQuery && lastUserQuery.trim()) || selected || "";
    renderRecipes(data.recipes || []);
    void updateQueryBreakdownPanel(retrievalExplainQuery);
  } catch (error) {
    if (requestToken !== recommendRequestToken) return;
    console.error(error);
    setStatus("Could not load recipes.", true);
  } finally {
    endBusy();
  }
}

// ── Event listeners ───────────────────────────────────────────────────────────

searchButton.addEventListener("click", () => {
  const query = searchInput.value.trim();
  if (!query) {
    setStatus("Type a dish before searching.", true);
    return;
  }

  resultsTitle.textContent = "Thinking...";
  lastUserQuery = query;
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
    retrievalExplainQuery = "";
    resetQueryBreakdownToEmpty();
    return;
  }

  autocompleteTimer = setTimeout(() => {
    if (showListingDropdown && !showListingDropdown.checked) {
      hideMatchDropdown();
      return;
    }
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

    resultsTitle.textContent = "Thinking...";
    lastUserQuery = query;
    hideMatchDropdown();
    fetchRagAnswer(query);
  }

  if (event.key === "Escape") {
    hideMatchDropdown();
  }
});

if (showListingDropdown) {
  showListingDropdown.addEventListener("change", () => {
    if (!showListingDropdown.checked) {
      hideMatchDropdown();
      return;
    }
    const query = searchInput.value.trim();
    if (query) fetchMatchSuggestions(query);
  });
}

if (modelSelect) {
  modelSelect.addEventListener("change", () => {
    syncModelFromUI();
    updateActiveState();

    const query = searchInput.value.trim();

    if (selectedRecipeTitle) {
      fetchRecommendations(selectedRecipeTitle);
    } else if (query) {
      fetchMatchSuggestions(query);
    }
  });
}

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    if (uiBusyCount > 0) return;
    const clickedDiet = button.dataset.diet;
    if (!clickedDiet) return;

    if (selectedDiets.has(clickedDiet)) {
      selectedDiets.delete(clickedDiet);
      button.classList.remove("active");
    } else {
      selectedDiets.add(clickedDiet);
      button.classList.add("active");
    }

    updateActiveState();

    if (selectedRecipeTitle) {
      fetchRecommendations(selectedRecipeTitle);
    } else if (lastUserQuery.trim()) {
      resultsTitle.textContent = "Thinking...";
      fetchRagAnswer(lastUserQuery);
    } else {
      const query = searchInput.value.trim();
      if (query) fetchMatchSuggestions(query);
    }
  });
});

clearFiltersButton.addEventListener("click", () => {
  if (uiBusyCount > 0) return;
  selectedDiets.clear();
  filterButtons.forEach((btn) => btn.classList.remove("active"));
  updateActiveState();

  if (selectedRecipeTitle) {
    fetchRecommendations(selectedRecipeTitle);
  } else if (lastUserQuery.trim()) {
    resultsTitle.textContent = "Thinking...";
    fetchRagAnswer(lastUserQuery);
  } else {
    const query = searchInput.value.trim();
    if (query) fetchMatchSuggestions(query);
  }
});

recipesGrid.addEventListener("click", (e) => {
  const card = e.target.closest(".recipe-flip-card");
  if (!card) return;
  const index = Number(card.dataset.index);
  const recipe = currentRecipes[index];
  if (e.target.closest(".why-chosen-btn")) {
    e.preventDefault();
    e.stopPropagation();
    card.classList.add("flipped");
    card.setAttribute("aria-expanded", "true");
    void loadCardWhyExplain(card, recipe);
    return;
  }
  if (e.target.closest(".flip-back-btn")) {
    e.preventDefault();
    e.stopPropagation();
    card.classList.remove("flipped");
    card.setAttribute("aria-expanded", "false");
    return;
  }
  if (card.classList.contains("flipped")) return;
  if (!recipe) return;
  openRecipeModal(recipe);
});

recipesGrid.addEventListener("keydown", (e) => {
  const card = e.target.closest(".recipe-flip-card");
  if (!card || card.classList.contains("flipped")) return;
  if (e.target.closest(".why-chosen-btn")) return;
  if (e.key !== "Enter" && e.key !== " ") return;
  e.preventDefault();
  const index = Number(card.dataset.index);
  openRecipeModal(currentRecipes[index]);
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
    else {
      document.querySelectorAll(".recipe-flip-card.flipped").forEach((c) => {
        c.classList.remove("flipped");
        c.setAttribute("aria-expanded", "false");
      });
    }
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
resetQueryBreakdownToEmpty();
