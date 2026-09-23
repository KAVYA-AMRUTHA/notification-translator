const EXAMPLE_NOTIFICATIONS = [
  "Gmail: Your interview is scheduled for tomorrow at 10 AM.",
  "GitHub: You were assigned issue #42 in repository Espial.",
  "Amazon: Your package will arrive tomorrow between 2 PM and 6 PM.",
  "Instagram: Someone liked your post.",
  "SBI: Your account was debited ₹2,500.",
].join("\n");

const CATEGORY_META = {
  ACTION_REQUIRED: { label: "Action Required", emoji: "🔴" },
  IMPORTANT: { label: "Important", emoji: "🟠" },
  INFORMATIONAL: { label: "Informational", emoji: "🟢" },
  LOW_PRIORITY: { label: "Low Priority", emoji: "⚪" },
  IGNORE: { label: "Ignore", emoji: "⚫" },
};

const CATEGORY_ORDER = ["ACTION_REQUIRED", "IMPORTANT", "INFORMATIONAL", "LOW_PRIORITY", "IGNORE"];

const textarea = document.getElementById("notifications");
const analyzeBtn = document.getElementById("analyzeBtn");
const exampleBtn = document.getElementById("exampleBtn");
const errorMsg = document.getElementById("errorMsg");
const loadingEl = document.getElementById("loading");
const resultsEl = document.getElementById("results");
const resultsCountEl = document.getElementById("resultsCount");
const summaryPillsEl = document.getElementById("summaryPills");
const resultsGroupsEl = document.getElementById("resultsGroups");

exampleBtn.addEventListener("click", () => {
  textarea.value = EXAMPLE_NOTIFICATIONS;
  textarea.focus();
});

analyzeBtn.addEventListener("click", analyze);

function showError(message) {
  errorMsg.textContent = message;
  errorMsg.hidden = false;
}

function clearError() {
  errorMsg.hidden = true;
  errorMsg.textContent = "";
}

function setLoading(isLoading) {
  loadingEl.hidden = !isLoading;
  analyzeBtn.disabled = isLoading;
  if (isLoading) {
    resultsEl.hidden = true;
  }
}

async function analyze() {
  clearError();
  const lines = textarea.value
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length === 0) {
    showError("Please paste at least one notification before analyzing.");
    return;
  }

  setLoading(true);

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notifications: lines }),
    });

    if (!response.ok) {
      let detail = "Something went wrong. Please try again.";
      try {
        const errBody = await response.json();
        if (errBody && errBody.detail) detail = errBody.detail;
      } catch (_) {
        /* ignore parse errors */
      }
      throw new Error(detail);
    }

    const data = await response.json();
    renderResults(data);
  } catch (err) {
    showError(err.message || "Network error. Please check your connection and try again.");
  } finally {
    setLoading(false);
  }
}

function renderResults(data) {
  const results = data.results || [];
  resultsCountEl.textContent = `${data.total} notification${data.total === 1 ? "" : "s"} analyzed`;

  const counts = {};
  for (const cat of CATEGORY_ORDER) counts[cat] = 0;
  for (const r of results) counts[r.category] = (counts[r.category] || 0) + 1;

  summaryPillsEl.innerHTML = "";
  for (const cat of CATEGORY_ORDER) {
    if (counts[cat] === 0) continue;
    const meta = CATEGORY_META[cat];
    const pill = document.createElement("span");
    pill.className = "pill";
    pill.textContent = `${meta.emoji} ${counts[cat]} ${meta.label}`;
    summaryPillsEl.appendChild(pill);
  }

  resultsGroupsEl.innerHTML = "";
  for (const cat of CATEGORY_ORDER) {
    const items = results.filter((r) => r.category === cat);
    if (items.length === 0) continue;

    const meta = CATEGORY_META[cat];
    const group = document.createElement("div");
    group.className = "result-group";

    const title = document.createElement("div");
    title.className = "group-title";
    title.textContent = `${meta.emoji} ${meta.label}`;
    group.appendChild(title);

    const cardsWrap = document.createElement("div");
    cardsWrap.className = "cards";

    for (const item of items) {
      cardsWrap.appendChild(renderCard(item));
    }

    group.appendChild(cardsWrap);
    resultsGroupsEl.appendChild(group);
  }

  resultsEl.hidden = false;
  resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderCard(item) {
  const card = document.createElement("div");
  card.className = `result-card cat-${item.category}`;

  const top = document.createElement("div");
  top.className = "result-top";

  const source = document.createElement("span");
  source.className = "result-source";
  source.textContent = item.source || "Unknown";
  top.appendChild(source);

  const urgency = document.createElement("span");
  urgency.className = `result-urgency urgency-${item.urgency}`;
  urgency.textContent = item.urgency;
  top.appendChild(urgency);

  card.appendChild(top);

  const text = document.createElement("p");
  text.className = "result-text";
  text.textContent = `"${item.original_text}"`;
  card.appendChild(text);

  if (item.requires_action && item.action) {
    const actionRow = document.createElement("p");
    actionRow.className = "result-row";
    actionRow.innerHTML = `<strong>Action:</strong> ${escapeHtml(item.action)}`;
    card.appendChild(actionRow);
  } else {
    const noneRow = document.createElement("p");
    noneRow.className = "result-row";
    noneRow.innerHTML = `<strong>Action:</strong> None`;
    card.appendChild(noneRow);
  }

  if (item.deadline) {
    const deadlineRow = document.createElement("p");
    deadlineRow.className = "result-row result-deadline";
    deadlineRow.innerHTML = `<strong>Deadline:</strong> ${escapeHtml(item.deadline)}`;
    card.appendChild(deadlineRow);
  }

  const reason = document.createElement("p");
  reason.className = "result-reason";
  reason.textContent = `Why: ${item.reason}`;
  card.appendChild(reason);

  return card;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
