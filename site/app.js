const state = {
  jobs: [],
  search: "",
  eligibility: "",
  decision: "",
};

const decisionsKey = "intern-scout-decisions-v1";

function loadDecisions() {
  try {
    return JSON.parse(localStorage.getItem(decisionsKey) || "{}");
  } catch {
    return {};
  }
}

function saveDecision(id, decision) {
  const decisions = loadDecisions();
  decisions[id] = decision;
  localStorage.setItem(decisionsKey, JSON.stringify(decisions));
  render();
}

function textElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  element.textContent = text;
  return element;
}

function detailsElement(label, items) {
  const details = document.createElement("details");
  details.append(textElement("summary", "", label));
  const list = document.createElement("ul");
  items.forEach((item) => list.append(textElement("li", "", item)));
  details.append(list);
  return details;
}

function jobCard(job, decision) {
  const article = document.createElement("article");
  article.className = "card";
  article.dataset.eligibility = job.eligibility;
  article.append(textElement("div", "score", Math.round(job.score).toString()));

  const content = document.createElement("div");
  const heading = document.createElement("h2");
  const link = document.createElement("a");
  link.href = job.url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = job.title;
  heading.append(link);
  content.append(heading);
  content.append(textElement("p", "meta", `${job.company} · ${job.location} · ${job.eligibility.replace("_", " ")} · ${decision}`));

  const tags = document.createElement("div");
  tags.className = "tags";
  job.tags.slice(0, 7).forEach((tag) => tags.append(textElement("span", "tag", tag)));
  content.append(tags);
  content.append(detailsElement("Why it ranked here", job.score_reasons));
  content.append(detailsElement("Eligibility checks", job.eligibility_reasons));

  const actions = document.createElement("div");
  actions.className = "actions";
  ["approved", "maybe", "rejected"].forEach((value) => {
    const button = textElement("button", "", value[0].toUpperCase() + value.slice(1));
    button.type = "button";
    button.setAttribute("aria-pressed", String(decision === value));
    button.addEventListener("click", () => saveDecision(job.key, value));
    actions.append(button);
  });
  content.append(actions);
  article.append(content);
  return article;
}

function render() {
  const container = document.querySelector("#jobs");
  const decisions = loadDecisions();
  const query = state.search.trim().toLowerCase();
  const filtered = state.jobs.filter((job) => {
    const decision = decisions[job.key] || "new";
    const searchable = `${job.title} ${job.company} ${job.description} ${job.tags.join(" ")}`.toLowerCase();
    return (!query || searchable.includes(query)) &&
      (!state.eligibility || job.eligibility === state.eligibility) &&
      (!state.decision || decision === state.decision);
  });
  container.replaceChildren();
  if (!filtered.length) {
    container.append(textElement("p", "empty", "No opportunities match these filters."));
    return;
  }
  filtered.forEach((job) => container.append(jobCard(job, decisions[job.key] || "new")));
}

async function start() {
  const response = await fetch("jobs.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load jobs.json (${response.status})`);
  const payload = await response.json();
  state.jobs = payload.jobs || [];
  document.querySelector("#job-count").textContent = payload.count ?? state.jobs.length;
  document.querySelector("#updated-at").textContent = `Updated ${new Date(payload.generated_at).toLocaleString()}`;
  render();
}

document.querySelector("#search").addEventListener("input", (event) => { state.search = event.target.value; render(); });
document.querySelector("#eligibility").addEventListener("change", (event) => { state.eligibility = event.target.value; render(); });
document.querySelector("#decision").addEventListener("change", (event) => { state.decision = event.target.value; render(); });

start().catch((error) => {
  document.querySelector("#jobs").append(textElement("p", "empty", `Unable to load opportunities: ${error.message}`));
});
