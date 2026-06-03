const singleForm = document.getElementById("singleForm");
const singleInput = document.getElementById("singlePhone");
const singleClear = document.getElementById("singleClear");
const singleResult = document.getElementById("singleResult");
const singleResultLayer = document.getElementById("singleResultLayer");
const globalStatus = document.getElementById("globalStatus");
const runtimeHint = document.getElementById("runtimeHint");
const kpiMatches = document.getElementById("kpiMatches");
const kpiHigh = document.getElementById("kpiHigh");
const resultStamp = document.getElementById("resultStamp");

const bulkForm = document.getElementById("bulkForm");
const bulkInput = document.getElementById("bulkPhones");
const bulkAsync = document.getElementById("bulkAsync");
const bulkResult = document.getElementById("bulkResult");
const bulkProgressBar = document.getElementById("bulkProgressBar");
const bulkProgressText = document.getElementById("bulkProgressText");
const jobStatus = document.getElementById("jobStatus");

const apiEnabled = window.location.protocol !== "file:";
const sourceLabels = {
  phonenumbers_metadata: "Telefoonmetadata",
  numverify: "Numverify API",
  serpapi: "SerpAPI",
  duckduckgo_search: "DuckDuckGo",
  kvk_api: "KVK API",
  kvk_public: "KVK Publiek",
  directory_nl: "Nederlandse directories",
  directory_sites: "Directory & Bedrijfsdata",
};
const trustLabels = {
  officieel: "Officieel",
  openbaar: "Openbaar",
  indirect: "Indicatief",
};
const matchTypeLabels = {
  exact: "Directe match",
  context: "Contextsignaal",
  inconclusive: "Voorzichtig signaal",
};
const statusLabels = {
  queued: "In de wachtrij",
  running: "Verwerken",
  done: "Voltooid",
  completed: "Voltooid",
  error: "Mislukt",
};

function setStatus(text, tone) {
  globalStatus.textContent = text;
  globalStatus.dataset.tone = tone;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function confidenceLabel(value) {
  return `Betrouwbaarheid: ${(Number(value || 0) * 100).toFixed(1)}%`;
}

function confidenceClass(value, matchType) {
  const score = Number(value || 0);
  if (matchType === "exact" || score >= 0.75) return "";
  if (score >= 0.45) return "warn";
  return "error";
}

function updateCounts(results) {
  const matchCount = results.length;
  const highConfidenceCount = results.filter((item) => Number(item.confidence || 0) >= 0.75).length;
  kpiMatches.textContent = `${matchCount} resultaten`;
  kpiHigh.textContent = `${highConfidenceCount} betrouwbare treffers`;
}

function translateStatus(status) {
  return statusLabels[status] || status || "-";
}

function translateSource(source) {
  return sourceLabels[source] || source || "Onbekende bron";
}

function translateMatchType(matchType) {
  return matchTypeLabels[matchType] || matchType || "Voorzichtig signaal";
}

function translateTrust(sourceTier) {
  return trustLabels[sourceTier] || "Indicatief";
}

function trustClass(sourceTier) {
  return sourceTier === "officieel" ? "official" : sourceTier === "openbaar" ? "public" : "indirect";
}

function renderSummary(text, target) {
  target.className = "summary-box";
  target.textContent = text;
}

function renderEmptyResults(message) {
  singleResultLayer.className = "result-layer muted-empty";
  singleResultLayer.innerHTML = `<span class="empty-label">${escapeHtml(message)}</span>`;
}

function renderMatches(results, stamp) {
  if (!results.length) {
    updateCounts([]);
    resultStamp.textContent = stamp;
    renderEmptyResults("Geen publieke vermeldingen gevonden voor dit nummer.");
    return;
  }

  const cards = results
    .map((item) => {
      const platform = escapeHtml(item.platform || translateSource(item.source) || "Onbekend platform");
      const source = escapeHtml(translateSource(item.source));
      const matchType = escapeHtml(translateMatchType(item.match_type));
      const trustTier = item?.details?.source_tier || "indirect";
      const name = escapeHtml(item.name || item.organization || item.account_handle || platform || "Onbekend");
      const handle = escapeHtml(item.account_handle || "-");
      const organization = escapeHtml(item.organization || "-");
      const location = escapeHtml(item.location || "-");
      const evidence = escapeHtml((item.evidence || []).slice(0, 6).join(" | ") || "-");
      const url = item.account_url
        ? `<a href="${escapeAttr(item.account_url)}" target="_blank" rel="noopener">${escapeHtml(item.account_url)}</a>`
        : "-";

      return `
        <article class="match-card">
          <div class="match-top">
            <div class="match-tags">
              <span class="tag platform">${platform}</span>
              <span class="tag">${source}</span>
              <span class="tag trust-tag trust-${trustClass(trustTier)}">${translateTrust(trustTier)}</span>
              <span class="tag">${matchType}</span>
            </div>
            <span class="tag score-tag ${confidenceClass(item.confidence, item.match_type)}">${confidenceLabel(item.confidence)}</span>
          </div>
          <div class="match-body">
            <strong>Naam</strong><span>${name}</span>
            <strong>Gebruikersnaam</strong><span>${handle}</span>
            <strong>Organisatie</strong><span>${organization}</span>
            <strong>Locatie</strong><span>${location}</span>
            <strong>Link</strong><span>${url}</span>
            <strong>Bewijs</strong><span>${evidence}</span>
          </div>
        </article>
      `;
    })
    .join("");

  updateCounts(results);
  resultStamp.textContent = stamp;
  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = cards;
}

function resetSingleView() {
  renderSummary("Systeem klaar\nNog geen scan uitgevoerd.", singleResult);
  renderEmptyResults("Geen resultaten weergegeven.");
  kpiMatches.textContent = "0 resultaten";
  kpiHigh.textContent = "0 betrouwbare treffers";
  resultStamp.textContent = "klaar voor scan";
}

async function runSingleLookup(phoneNumber) {
  setStatus("Scan gestart", "busy");
  renderSummary("Zoekopdracht gestart...\nBel Radar verzamelt publieke signalen.", singleResult);
  renderEmptyResults("Resultaten worden geladen...");

  const response = await fetch("/api/v1/lookup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
  const payload = await response.json();

  if (!response.ok) {
    setStatus("Zoekopdracht mislukt", "err");
    renderSummary(`Fout: ${payload.detail || "onbekend"}`, singleResult);
    renderEmptyResults("De zoekopdracht kon niet worden voltooid.");
    return;
  }

  renderSummary(
    [
      `Status: ${translateStatus(payload.status)}`,
      `Zoek-ID: ${payload.request_id}`,
      `Internationaal formaat: ${payload.phone_e164}`,
      `Gevonden resultaten: ${payload.results.length}`,
    ].join("\n"),
    singleResult,
  );
  renderMatches(payload.results || [], `laatste scan · ${payload.phone_e164}`);
  setStatus("Scan klaar", "ok");
}

async function pollJob(jobId) {
  const response = await fetch(`/api/v1/jobs/${jobId}`);
  if (!response.ok) {
    setStatus("Batch mislukt", "err");
    renderSummary("Taak niet gevonden.", jobStatus);
    return;
  }

  const payload = await response.json();
  const percent = Math.max(0, Math.min(100, Number(payload.percent || 0)));

  bulkProgressBar.style.width = `${percent}%`;
  bulkProgressText.textContent = `${payload.processed_items} / ${payload.total_items} voltooide regels`;
  renderSummary(
    [
      `Status: ${translateStatus(payload.status)}`,
      `Voortgang: ${payload.processed_items}/${payload.total_items} (${payload.percent}%)`,
      `Fout: ${payload.error || "-"}`,
      "",
      ...payload.items.map((item) => `${item.row_index}. ${item.phone_raw} -> ${translateStatus(item.status)}`),
    ].join("\n"),
    jobStatus,
  );

  if (payload.status === "done") {
    setStatus("Batch klaar", "ok");
    return;
  }

  if (payload.status === "error") {
    setStatus("Batch mislukt", "err");
    return;
  }

  setStatus("Batch draait", "busy");
  window.setTimeout(() => pollJob(jobId), 1200);
}

singleForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const phoneNumber = singleInput.value.trim();

  if (!phoneNumber) {
    setStatus("Invoer ontbreekt", "err");
    renderSummary("Vul eerst een telefoonnummer in.", singleResult);
    return;
  }

  if (!apiEnabled) {
    setStatus("Previewmodus", "busy");
    renderSummary("Voorbeeldmodus actief.\nOpen http://127.0.0.1:8000 voor live zoeken.", singleResult);
    renderEmptyResults("De live API is niet beschikbaar in bestandsmodus.");
    return;
  }

  await runSingleLookup(phoneNumber);
});

singleClear.addEventListener("click", () => {
  singleInput.value = "";
  resetSingleView();
});

bulkForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const numbers = bulkInput.value.split("\n").map((value) => value.trim()).filter(Boolean);

  if (!numbers.length) {
    setStatus("Batchinvoer ontbreekt", "err");
    renderSummary("Voer minimaal één geldig nummer in.", bulkResult);
    return;
  }

  if (!apiEnabled) {
    setStatus("Previewmodus", "busy");
    renderSummary("Previewmodus actief.\nOpen http://127.0.0.1:8000 voor batchjobs.", bulkResult);
    return;
  }

  setStatus("Batch gestart", "busy");
  bulkProgressBar.style.width = "0%";
  bulkProgressText.textContent = "0 / 0 voltooide regels";
  renderSummary("Batchscan wordt gestart...", bulkResult);
  renderSummary("Geen actieve taak.", jobStatus);

  const response = await fetch("/api/v1/lookup/bulk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ numbers, async_mode: bulkAsync.checked }),
  });
  const payload = await response.json();

  if (!response.ok) {
    setStatus("Batch mislukt", "err");
    renderSummary(`Fout: ${payload.detail || "onbekend"}`, bulkResult);
    return;
  }

  if (payload.job_id) {
    renderSummary(`Asynchrone batchscan gestart: ${payload.job_id}`, bulkResult);
    pollJob(payload.job_id);
    return;
  }

  bulkProgressBar.style.width = "100%";
  bulkProgressText.textContent = `${payload.request_count} / ${payload.request_count} voltooide regels`;
  setStatus("Batch klaar", "ok");
  renderSummary(`Synchrone batch voltooid: ${payload.request_count} nummers`, bulkResult);
});

if (!apiEnabled) {
  runtimeHint.textContent = "Voorbeeldmodus via file://. Open http://127.0.0.1:8000 voor live zoekopdrachten.";
  setStatus("Previewmodus", "busy");
} else {
  runtimeHint.textContent = "Live modus actief. Resultaten komen direct uit de API en openbare bronnen.";
}

resetSingleView();
if (!apiEnabled) {
  setStatus("Previewmodus", "busy");
} else {
  setStatus("Systeem klaar", "idle");
}
