const routeCards = Array.from(document.querySelectorAll("[data-route]"));
const lookupForm = document.getElementById("singleForm");
const lookupInput = document.getElementById("singlePhone");
const lookupButton = document.getElementById("singleSubmit");
const refreshToggle = document.getElementById("singleRefresh");
const publicOnlyToggle = document.getElementById("singleHideUntrusted");
const refreshToggleWrap = document.getElementById("refreshToggleWrap");
const publicOnlyWrap = document.getElementById("publicOnlyWrap");
const singleResult = document.getElementById("singleResult");
const singleResultLayer = document.getElementById("singleResultLayer");
const globalStatus = document.getElementById("globalStatus");
const runtimeHint = document.getElementById("runtimeHint");
const kpiMatches = document.getElementById("kpiMatches");
const kpiHigh = document.getElementById("kpiHigh");
const resultStamp = document.getElementById("resultStamp");
const sourceCountChip = document.getElementById("sourceCountChip");
const localCountChip = document.getElementById("localCountChip");
const panelKicker = document.getElementById("panelKicker");
const panelTitle = document.getElementById("panelTitle");
const panelBadge = document.getElementById("panelBadge");
const panelLead = document.getElementById("panelLead");
const routeHint = document.getElementById("routeHint");
const routeSummaryText = document.getElementById("routeSummaryText");
const localStats = document.getElementById("localStats");
const singleOptions = document.getElementById("singleOptions");
const spamPanel = document.getElementById("spamPanel");
const spamForm = document.getElementById("spamForm");
const spamLabel = document.getElementById("spamLabel");
const spamReason = document.getElementById("spamReason");
const spamReports = document.getElementById("spamReports");
const consentPanel = document.getElementById("consentPanel");
const consentForm = document.getElementById("consentForm");
const contactName = document.getElementById("contactName");
const contactPhone = document.getElementById("contactPhone");
const contactCompany = document.getElementById("contactCompany");
const contactNote = document.getElementById("contactNote");
const consentResults = document.getElementById("consentResults");
const exportContactsBtn = document.getElementById("exportContacts");
const importContactsBtn = document.getElementById("importContacts");
const clearContactsBtn = document.getElementById("clearContacts");
const importContactsFile = document.getElementById("importContactsFile");
const consentStatus = document.getElementById("consentStatus");
const dashboardPanel = document.getElementById("dashboardPanel");
const refreshDashboard = document.getElementById("refreshDashboard");
const dashboardKpis = document.getElementById("dashboardKpis");
const dashboardSources = document.getElementById("dashboardSources");
const bulkForm = document.getElementById("bulkForm");
const bulkInput = document.getElementById("bulkPhones");
const bulkAsync = document.getElementById("bulkAsync");
const bulkResult = document.getElementById("bulkResult");
const bulkProgressBar = document.getElementById("bulkProgressBar");
const bulkProgressText = document.getElementById("bulkProgressText");
const jobStatus = document.getElementById("jobStatus");

const LIVE_API_BASE = "https://bel-radar-official.onrender.com";
const isFileProtocol = window.location.protocol === "file:";
const queryParams = new URLSearchParams(window.location.search);
const skipFileRedirect = queryParams.get("belradar_local") === "1" || queryParams.get("skip_redirect") === "1";
const shouldRedirectFromFile = isFileProtocol && !skipFileRedirect;
const apiEnabled = !isFileProtocol;
const currentHost = window.location.host || "";
const isLocalhost = currentHost.includes("localhost") || currentHost.includes("127.0.0.1");
const apiBase = apiEnabled
  ? window.__BELRADAR_API_BASE || (isLocalhost ? LIVE_API_BASE : window.location.origin)
  : window.__BELRADAR_API_BASE || LIVE_API_BASE;
const liveApiHost = apiEnabled ? window.location.host : LIVE_API_BASE.replace(/^https?:\\/\\//, "");

function showFileBootstrapRedirect() {
  if (!shouldRedirectFromFile) {
    return;
  }

  if (!document.body) {
    document.addEventListener("DOMContentLoaded", showFileBootstrapRedirect, { once: true });
    return;
  }

  const redirectDelayMs = 1800;
  const targetUrl = `${LIVE_API_BASE}/?from=file_redirect`;
  const overlay = document.createElement("div");
  overlay.className = "file-mode-boot-overlay";
  overlay.innerHTML = `
    <section class="file-mode-boot-card" role="status" aria-live="polite">
      <p class="file-mode-boot-kicker">Lokale bestandmodus gedetecteerd</p>
      <h3>Herrouteer naar Bel Radar live</h3>
      <p>
        Je draait nu een <strong>file://</strong> versie. Om actuele bronresultaten te tonen, starten we automatisch door naar
        <strong>${LIVE_API_BASE}</strong>.
      </p>
      <p class="file-mode-countdown">
        Start over <strong id="fileRedirectCountdown">1.8</strong> seconde…
      </p>
      <a class="file-mode-link" href="${targetUrl}" target="_self">Open direct live</a>
    </section>
  `;

  document.body.appendChild(overlay);

  const countdownEl = overlay.querySelector("#fileRedirectCountdown");
  let remainingMs = redirectDelayMs;

  const ticker = setInterval(() => {
    remainingMs -= 600;
    if (!countdownEl) {
      return;
    }
    if (remainingMs <= 0) {
      countdownEl.textContent = "0.0";
      return;
    }
    countdownEl.textContent = `${Math.max(0.2, (remainingMs / 1000)).toFixed(1)}`;
  }, 600);

  setTimeout(() => {
    clearInterval(ticker);
    window.location.replace(targetUrl);
  }, redirectDelayMs);
}

showFileBootstrapRedirect();
const STORAGE_KEYS = {
  contacts: "belradar.contacts.v2",
  spam: "belradar.spam.v2",
};
const ROUTES = {
  business: {
    title: "Zakelijke bronverificatie",
    lead: "Gebruik officiële en openbare bedrijfsbronnen met bronlagen, evidence en betrouwbaarheidsscore.",
    hint: "Route 1 combineert KvK, directories, openbare zoekresultaten en optionele premium bronnen in één hit-rapport.",
    badge: "business",
    button: "Vraag zakelijke match op",
    placeholder: "bijv. +31625265551",
    showRefresh: true,
    showPublicOnly: true,
    showForm: true,
  },
  spam: {
    title: "Spamcontrole",
    lead: "Combineer publieke reputatiesignalen met je lokale notities voor één risicobeoordeling.",
    hint: "Route 2 bouwt een risicoscore op uit openbare signalen en lokale observaties met explainability.",
    badge: "spam",
    button: "Bereken risico",
    placeholder: "bijv. +31625265551",
    showRefresh: true,
    showPublicOnly: false,
    showForm: true,
  },
  consent: {
    title: "Toestemmingslogboek",
    lead: "Zoek en beheer alleen lokale contacten met behoud van privacy en offline functionaliteit.",
    hint: "Route 3 werkt alleen lokaal in je browser, inclusief export en import van je eigen logboek.",
    badge: "local",
    button: "Zoek in logboek",
    placeholder: "bijv. 06 25 26 55 51",
    showRefresh: false,
    showPublicOnly: false,
    showForm: true,
  },
  dashboard: {
    title: "Dashboard",
    lead: "Bekijk brongezondheid, latency en conflictratio als technische cockpit met live metrics.",
    hint: "Route 4 laadt metrics en bronstatus direct uit de API.",
    badge: "dashboard",
    button: "Vernieuw dashboard",
    placeholder: "dashboard gebruikt geen zoekveld",
    showRefresh: false,
    showPublicOnly: false,
    showForm: false,
  },
};
const sourceLabels = {
  phonenumbers_metadata: "Telefoonmetadata",
  numverify: "Numverify",
  serpapi: "SerpAPI",
  duckduckgo_search: "DuckDuckGo",
  social_hints: "Social hints",
  kvk_api: "KVK API",
  kvk_public: "KVK publiek",
  directory_nl: "Nederlandse directories",
  directory_sites: "Directory & Bedrijfsdata",
  twilio_lookup: "Twilio Lookup",
  numlookup_api: "Numlookup",
  clearbit_lookup: "Clearbit",
  hunter_lookup: "Hunter",
  reputation_model: "Reputatiemodel",
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

let activeRoute = "business";
let dashboardData = null;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function escapeAttr(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function normalizeDigits(value) {
  return String(value ?? "").replace(/\D/g, "");
}

function normalizeText(value) {
  return String(value ?? "").toLowerCase().replace(/\s+/g, " ").trim();
}

function setStatus(text, tone) {
  globalStatus.textContent = text;
  globalStatus.dataset.tone = tone;
}

function confidenceLabel(value) {
  return `Betrouwbaarheid: ${(Number(value || 0) * 100).toFixed(1)}%`;
}

function confidenceClass(value, matchType) {
  const score = Number(value || 0);
  if (score >= 0.75 && matchType === "exact") return "high";
  if (matchType === "exact" || score >= 0.6) return "";
  if (score >= 0.45) return "warn";
  return "error";
}

function trustBadgeClass(sourceTier) {
  if (sourceTier === "officieel") return "official";
  if (sourceTier === "openbaar") return "public";
  return "indirect";
}

function confidenceBand(value) {
  const score = Number(value || 0);
  if (score >= 0.65) return "betrouwbaar";
  if (score >= 0.45) return "middelmatig";
  return "laag vertrouwen";
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

function formatAge(discoveredAt) {
  if (!discoveredAt) return "onbekend";
  const ms = Date.now() - Date.parse(discoveredAt);
  if (!Number.isFinite(ms) || ms < 0) return "onbekend";
  const minutes = Math.floor(ms / 60000);
  if (minutes < 1) return "net gevonden";
  if (minutes < 60) return `${minutes} min geleden`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} uur geleden`;
  const days = Math.floor(hours / 24);
  return `${days} dagen geleden`;
}

function loadJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  window.localStorage.setItem(key, JSON.stringify(value));
}

function loadContacts() {
  return loadJson(STORAGE_KEYS.contacts, []);
}

function saveContacts(contacts) {
  saveJson(STORAGE_KEYS.contacts, contacts);
}

function loadSpamReports() {
  return loadJson(STORAGE_KEYS.spam, []);
}

function saveSpamReports(reports) {
  saveJson(STORAGE_KEYS.spam, reports);
}

function showConsentStatus(message, tone = "ok") {
  if (!consentStatus) return;
  const colorMap = {
    ok: "var(--ok)",
    warn: "var(--warn)",
    err: "var(--error)",
  };
  consentStatus.textContent = message;
  consentStatus.style.color = colorMap[tone] || "var(--muted)";
  setTimeout(() => {
    if (consentStatus.textContent === message) {
      consentStatus.textContent = "";
      consentStatus.style.color = "";
    }
  }, 3500);
}

function sanitizeContactRecord(raw) {
  if (!raw || typeof raw !== "object") return null;
  const name = String(raw.name || raw.label || raw.ContactName || "").trim();
  const phone = String(raw.phone || raw.Phone || raw.number || raw.telefoon || "").trim();
  const company = String(raw.company || raw.bedrijf || raw.Organization || "").trim();
  const note = String(raw.note || raw.notitie || raw.Comment || raw.notes || "").trim();
  if (!name && !phone) return null;
  return {
    name,
    phone,
    company,
    note,
    createdAt: raw.createdAt || raw.created_at || new Date().toISOString(),
  };
}

function normalizeContactKey(contact) {
  const digits = normalizeDigits(contact.phone || "");
  if (digits) return `phone:${digits}`;
  const text = normalizeText(contact.name || contact.company || "");
  if (text) return `name:${text}`;
  return `anon:${contact.createdAt}`;
}

function mergeContacts(baseContacts, incomingContacts) {
  const indexed = new Map();
  const merged = [];
  for (const contact of baseContacts) {
    const normalized = sanitizeContactRecord(contact);
    if (!normalized) continue;
    const key = normalizeContactKey(normalized);
    indexed.set(key, normalized);
    merged.push(normalized);
  }

  for (const incoming of incomingContacts) {
    const normalized = sanitizeContactRecord(incoming);
    if (!normalized) continue;
    const key = normalizeContactKey(normalized);
    if (indexed.has(key)) {
      const existing = indexed.get(key);
      existing.name = normalized.name || existing.name;
      existing.phone = normalized.phone || existing.phone;
      existing.company = normalized.company || existing.company;
      existing.note = normalized.note || existing.note;
      existing.createdAt = normalized.createdAt || existing.createdAt;
      continue;
    }
    indexed.set(key, normalized);
    merged.push(normalized);
  }

  return merged;
}

function splitCsvLine(line) {
  const out = [];
  let current = "";
  let quoted = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (quoted && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        quoted = !quoted;
      }
      continue;
    }
    if (char === "," && !quoted) {
      out.push(current);
      current = "";
      continue;
    }
    if (char === "\r") continue;
    current += char;
  }
  out.push(current);
  return out;
}

function parseCsv(text) {
  const lines = String(text || "")
    .replace(/\r\n/g, "\n")
    .split("\n")
    .filter((line) => line.trim().length);
  if (!lines.length) return [];
  const header = splitCsvLine(lines[0]).map((item) => normalizeText(item));
  const records = [];
  for (const line of lines.slice(1)) {
    const values = splitCsvLine(line);
    if (!values.length) continue;
    const raw = {};
    header.forEach((key, index) => {
      raw[key] = values[index];
    });
    records.push(raw);
  }
  return records;
}

function parseImportedContacts(payload) {
  if (Array.isArray(payload)) return payload.map((item) => sanitizeContactRecord(item)).filter(Boolean);

  if (payload && typeof payload === "object") {
    if (Array.isArray(payload.records)) return payload.records.map((item) => sanitizeContactRecord(item)).filter(Boolean);
    if (Array.isArray(payload.contacts)) return payload.contacts.map((item) => sanitizeContactRecord(item)).filter(Boolean);
  }

  return [];
}

function sourceStack(item) {
  const stack = [];
  if (item.source) stack.push(item.source);
  if (Array.isArray(item.supporting_sources)) {
    for (const source of item.supporting_sources) {
      if (source && !stack.includes(source)) stack.push(source);
    }
  }
  return stack.length ? stack : [item.source || "Onbekende bron"];
}

function shouldShowBusinessResult(item) {
  if (!publicOnlyToggle || !publicOnlyToggle.checked) return true;
  const tier = item.signal_tier || item?.details?.source_tier || "indirect";
  const confidence = Number(item.confidence || 0);
  return (tier === "officieel" || tier === "openbaar") && confidence >= 0.4;
}

function renderSummary(text, target) {
  target.className = "summary-box";
  target.textContent = text;
}

function renderEmptyResults(message) {
  singleResultLayer.className = "result-layer muted-empty";
  singleResultLayer.innerHTML = `<span class="empty-label">${escapeHtml(message)}</span>`;
}

function updateCounts(results) {
  const count = results.length;
  const highConfidenceCount = results.filter((item) => Number(item.confidence || 0) >= 0.75).length;
  kpiMatches.textContent = `${count} resultaten`;
  kpiHigh.textContent = `${highConfidenceCount} betrouwbare treffers`;
}

function lookupSummary(results) {
  const summary = results.find((item) => item.source === "reputation_model");
  return summary || null;
}

function renderBusinessResults(results, stamp) {
  const filtered = (results || []).filter(shouldShowBusinessResult);
  updateCounts(filtered);
  resultStamp.textContent = stamp;

  if (!filtered.length) {
    renderEmptyResults("Geen resultaten weergegeven met de huidige filter.");
    return;
  }

  const cards = filtered
    .map((item) => {
      const platform = escapeHtml(item.platform || translateSource(item.source) || "Onbekend platform");
      const mainSource = escapeHtml(translateSource(item.source));
      const matchType = escapeHtml(translateMatchType(item.match_type));
      const trustTier = item.signal_tier || item?.details?.source_tier || "indirect";
      const support = sourceStack(item);
      const supportLabel = support.length > 1 ? `${escapeHtml(translateSource(support[0]))} + ${support.length - 1} bron(nen)` : "1 bron";
      const alternatives = support.slice(1).map(translateSource).map(escapeHtml);
      const alternativeLabel = alternatives.length ? alternatives.join(", ") : "geen alternatieven";
      const name = escapeHtml(item.name || item.organization || item.account_handle || platform || "Onbekend");
      const handle = escapeHtml(item.account_handle || "-");
      const organization = escapeHtml(item.organization || "-");
      const location = escapeHtml(item.location || "-");
      const confidence = Number(item.confidence || 0);
      const evidence = escapeHtml((item.evidence || []).slice(0, 6).join(" | ") || "-");
      const confidenceText = confidenceLabel(confidence);
      const sourceText = escapeHtml(supportLabel);
      const confidenceBadge = confidenceBand(confidence);
      const discovered = formatAge(item.discovered_at);
      const url = item.account_url
        ? `<a href="${escapeAttr(item.account_url)}" target="_blank" rel="noopener">${escapeHtml(item.account_url)}</a>`
        : "-";

      return `
        <article class="match-card">
          <div class="match-top">
            <div class="match-tags">
              <span class="tag platform">${platform}</span>
              <span class="tag">${mainSource}</span>
              <span class="tag">${sourceText}</span>
              <span class="tag trust-tag ${trustBadgeClass(trustTier)}">${translateTrust(trustTier)}</span>
              <span class="tag">${matchType}</span>
              <span class="tag score-state">${confidenceBadge}</span>
            </div>
            <span class="tag score-tag ${confidenceClass(item.confidence, item.match_type)}">${confidenceText}</span>
          </div>
          <div class="match-body">
            <strong>Naam</strong><span>${name}</span>
            <strong>Bron</strong><span>${sourceText}</span>
            <strong>Alternatieve bronnen</strong><span>${alternativeLabel}</span>
            <strong>Gebruikersnaam</strong><span>${handle}</span>
            <strong>Organisatie</strong><span>${organization}</span>
            <strong>Locatie</strong><span>${location}</span>
            <strong>Signaal</strong><span>${discoveredAtLabel(confidence)}</span>
            <strong>Gevonden</strong><span>${discovered}</span>
            <strong>Link</strong><span>${url}</span>
            <strong>Bewijs</strong><span>${evidence}</span>
          </div>
        </article>
      `;
    })
    .join("");

  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = cards;
}

function discoveredAtLabel(confidence) {
  const score = Number(confidence || 0);
  if (score >= 0.75) return "sterke match";
  if (score >= 0.45) return "indicatief";
  return "laag vertrouwen";
}

function renderSpamResults(results, stamp) {
  const summary = lookupSummary(results || []);
  const remainder = (results || []).filter((item) => item.source !== "reputation_model");
  updateCounts(remainder.length ? remainder : results || []);
  resultStamp.textContent = stamp;

  if (!summary) {
    renderBusinessResults(results, stamp);
    return;
  }

  const risk = Number(summary.details?.risk_score || summary.confidence || 0);
  const reasonList = Array.isArray(summary.evidence) ? summary.evidence : [];
  const reasons = reasonList.length
    ? reasonList.map((item) => `<li>${escapeHtml(item)}</li>`).join("")
    : "<li>Geen extra redenen opgegeven</li>";

  const primary = `
    <article class="match-card">
      <div class="match-top">
        <div class="match-tags">
          <span class="tag platform">${escapeHtml(summary.platform || "Spamcontrole")}</span>
          <span class="tag">${escapeHtml(summary.details?.risk_label || "Risicoscore")}</span>
          <span class="tag trust-tag indirect">Indicatief</span>
        </div>
        <span class="tag score-tag ${risk >= 0.7 ? "error" : risk >= 0.45 ? "warn" : ""}">Risico ${(risk * 100).toFixed(0)}%</span>
      </div>
      <div class="match-body">
        <strong>Naam</strong><span>${escapeHtml(summary.name || "Reputatieanalyse")}</span>
        <strong>Organisatie</strong><span>${escapeHtml(summary.organization || "-")}</span>
        <strong>Bronnen</strong><span>${escapeHtml((summary.details?.observed_sources || []).join(", ") || "Geen extra bronnen")}</span>
        <strong>Signalen</strong><span>${escapeHtml(`${summary.details?.public_hit_count ?? 0} publieke signalen`)}</span>
        <strong>Lokale uitleg</strong><div>
          <div class="reputation-banner">
            <strong>${escapeHtml(summary.details?.risk_label || "Risicoscore")}</strong>
            <p>${escapeHtml(summary.evidence?.join(" · ") || "Lokale analyse zonder extra signalen")}</p>
            <div class="risk-meter">
              <div class="risk-meter-track"><span class="risk-meter-fill" style="width:${Math.max(0, Math.min(100, risk * 100))}%"></span></div>
            </div>
          </div>
        </div>
        <strong>Redenen</strong><div><ul class="risk-list">${reasons}</ul></div>
      </div>
    </article>
  `;

  const cards = remainder.length
    ? remainder
        .slice(0, 4)
        .map((item) => {
          const platform = escapeHtml(item.platform || translateSource(item.source) || "Onbekend platform");
          const mainSource = escapeHtml(translateSource(item.source));
          const matchType = escapeHtml(translateMatchType(item.match_type));
          const trustTier = item.signal_tier || item?.details?.source_tier || "indirect";
          const support = sourceStack(item);
          const supportLabel = support.length > 1 ? `${escapeHtml(translateSource(support[0]))} + ${support.length - 1} bron(nen)` : "1 bron";
          const name = escapeHtml(item.name || item.organization || item.account_handle || platform || "Onbekend");
          const confidence = Number(item.confidence || 0);
          const evidence = escapeHtml((item.evidence || []).slice(0, 4).join(" | ") || "-");
          return `
            <article class="match-card">
              <div class="match-top">
                <div class="match-tags">
                  <span class="tag platform">${platform}</span>
                  <span class="tag">${mainSource}</span>
                  <span class="tag">${escapeHtml(supportLabel)}</span>
                  <span class="tag trust-tag ${trustBadgeClass(trustTier)}">${translateTrust(trustTier)}</span>
                  <span class="tag">${matchType}</span>
                </div>
                <span class="tag score-tag ${confidenceClass(confidence, item.match_type)}">${confidenceLabel(confidence)}</span>
              </div>
              <div class="match-body">
                <strong>Naam</strong><span>${name}</span>
                <strong>Bewijs</strong><span>${evidence}</span>
              </div>
            </article>
          `;
        })
        .join("")
    : `<div class="mini-card"><strong>Geen aanvullende signalen</strong><span>Alleen het reputatiemodel leverde een score op.</span></div>`;

  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = `${primary}${cards}`;
}

function renderConsentSearch(query) {
  const contacts = loadContacts();
  const needleDigits = normalizeDigits(query);
  const needleText = normalizeText(query);
  const matches = contacts.filter((contact) => {
    const digits = normalizeDigits(contact.phone);
    return (
      digits.includes(needleDigits) ||
      normalizeText(contact.name).includes(needleText) ||
      normalizeText(contact.company).includes(needleText) ||
      normalizeText(contact.note).includes(needleText)
    );
  });

  updateCounts(matches);
  resultStamp.textContent = "eigen register";
  if (!matches.length) {
    renderEmptyResults("Geen eigen contact gevonden voor deze invoer.");
    renderSummary("Geen lokaal contact gevonden.\nProbeer een naam, bedrijf of nummer uit je eigen register.", singleResult);
    return;
  }

  renderSummary(
    [
      `Status: ${matches.length} lokaal contact(en)`,
      `Zoekterm: ${query}`,
      `Bron: eigen register`,
    ].join("\n"),
    singleResult,
  );

  const cards = matches
    .map(
      (contact) => `
        <article class="match-card">
          <div class="match-top">
            <div class="match-tags">
              <span class="tag platform">Eigen contact</span>
              <span class="tag trust-tag official">Toestemming</span>
            </div>
          </div>
          <div class="match-body">
            <strong>Naam</strong><span>${escapeHtml(contact.name || "-")}</span>
            <strong>Telefoon</strong><span>${escapeHtml(contact.phone || "-")}</span>
            <strong>Bedrijf</strong><span>${escapeHtml(contact.company || "-")}</span>
            <strong>Notitie</strong><span>${escapeHtml(contact.note || "-")}</span>
          </div>
        </article>
      `,
    )
    .join("");

  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = cards;
}

function renderSpamReports() {
  const reports = loadSpamReports();
  if (!reports.length) {
    spamReports.innerHTML = `<div class="mini-card"><strong>Geen lokale spamnotities</strong><span>Geen opgeslagen meldingen in deze browser.</span></div>`;
    return;
  }

  spamReports.innerHTML = reports
    .slice()
    .reverse()
    .slice(0, 8)
    .map(
      (report) => `
        <div class="mini-card">
          <strong>${escapeHtml(report.label || "Spamnotitie")}</strong>
          <span>${escapeHtml(report.phone || "-")}</span>
          <p>${escapeHtml(report.reason || "-")}</p>
        </div>
      `,
    )
    .join("");
}

function renderConsentList() {
  const contacts = loadContacts();
  if (!contacts.length) {
    consentResults.innerHTML = `<div class="mini-card"><strong>Geen eigen contacten</strong><span>Voeg een contact toe om hier direct te kunnen zoeken.</span></div>`;
    return;
  }

  consentResults.innerHTML = contacts
    .slice()
    .reverse()
    .slice(0, 8)
    .map(
      (contact) => `
        <div class="mini-card">
          <strong>${escapeHtml(contact.name || "-")}</strong>
          <span>${escapeHtml(contact.phone || "-")} ${contact.company ? `- ${escapeHtml(contact.company)}` : ""}</span>
          <p>${escapeHtml(contact.note || "Toestemming opgeslagen in eigen register")}</p>
        </div>
      `,
    )
    .join("");
}

function updateLocalStats() {
  const contacts = loadContacts();
  const reports = loadSpamReports();
  sourceCountChip.textContent = "10 bronlagen";
  localCountChip.textContent = `${contacts.length} eigen records`;
  localStats.innerHTML = `
    <div class="mini-stat"><span>Contacten</span><strong>${contacts.length}</strong></div>
    <div class="mini-stat"><span>Spamnotities</span><strong>${reports.length}</strong></div>
    <div class="mini-stat"><span>Route</span><strong>${translateRouteLabel(activeRoute)}</strong></div>
    <div class="mini-stat"><span>Modus</span><strong>${apiEnabled ? "Live" : "Preview"}</strong></div>
  `;
}

function translateRouteLabel(route) {
  return {
    business: "Zakelijk",
    spam: "Spam",
    consent: "Eigen data",
    dashboard: "Dashboard",
  }[route] || route;
}

function renderRouteSummary() {
  const cards = Object.entries(ROUTES)
    .map(
      ([route, config]) => `
        <div class="mini-card">
          <strong>${escapeHtml(config.title)}</strong>
          <span>${escapeHtml(config.hint)}</span>
          <p>${escapeHtml(route === activeRoute ? "Actief" : "Beschikbaar")}</p>
        </div>
      `,
    )
    .join("");
  routeSummaryText.innerHTML = cards;
}

function renderDashboard(data, sources) {
  const metrics = data || {};
  const sourceRows = Array.isArray(metrics.sources) ? metrics.sources : [];
  dashboardData = metrics;
  kpiMatches.textContent = `${metrics.request_count ?? 0} scans`;
  kpiHigh.textContent = `${metrics.conflict_count ?? 0} conflicten`;

  dashboardKpis.innerHTML = `
    <div class="kpi-card"><span>Requests</span><strong>${metrics.request_count ?? 0}</strong></div>
    <div class="kpi-card"><span>Conflicten</span><strong>${metrics.conflict_count ?? 0}</strong></div>
    <div class="kpi-card"><span>Conflict ratio</span><strong>${Number(metrics.conflict_ratio ?? 0).toFixed(2)}</strong></div>
    <div class="kpi-card"><span>Bronnen</span><strong>${sourceRows.length}</strong></div>
  `;

  dashboardSources.innerHTML = sourceRows.length
    ? sourceRows
        .slice()
        .sort((a, b) => String(a.source).localeCompare(String(b.source)))
        .map(
          (row) => `
            <div class="source-health-row">
              <header>
                <strong>${escapeHtml(translateSource(row.source))}</strong>
                <span>${Number(row.hit_rate ?? 0).toFixed(1)}%</span>
              </header>
              <p>
                Calls ${row.calls ?? 0} · Hits ${row.hits ?? 0} · Gem. ${Number(row.avg_ms ?? 0).toFixed(0)} ms ·
                Resultaten ${Number(row.avg_results ?? 0).toFixed(1)}
              </p>
              ${row.last_error ? `<p>Laatste fout: ${escapeHtml(row.last_error)}</p>` : ""}
            </div>
          `,
        )
        .join("")
    : `<div class="source-health-row"><header><strong>Geen metrics</strong><span>0%</span></header><p>Geen brondata beschikbaar in dit venster.</p></div>`;

  resultStamp.textContent = `venster ${metrics.window_days ?? 30} dagen`;
  renderSummary(
    [
      `Status: dashboard geladen`,
      `Requests: ${metrics.request_count ?? 0}`,
      `Conflicten: ${metrics.conflict_count ?? 0}`,
      `Conflict ratio: ${Number(metrics.conflict_ratio ?? 0).toFixed(2)}`,
    ].join("\n"),
    singleResult,
  );
  singleResultLayer.className = "result-layer";
  singleResultLayer.innerHTML = `<div class="mini-card"><strong>Dashboard actief</strong><span>Zie rechts de brongezondheid en kernmetrics.</span></div>`;
}

async function loadDashboard() {
  if (!apiEnabled) {
    renderSummary(`Previewmodus\nDashboard is alleen live beschikbaar op ${LIVE_API_BASE}.`, singleResult);
    singleResultLayer.innerHTML = `<div class="mini-card"><strong>Previewmodus</strong><span>Open de live omgeving voor dashboarddata.</span></div>`;
    return;
  }

  setStatus("Dashboard laden", "busy");
  renderSummary("Dashboard wordt geladen...\nBrongezondheid en metrics ophalen.", singleResult);

  const [metricsResponse] = await Promise.all([fetch(`${apiBase}/api/v1/metrics?window_days=30`)]);
  if (!metricsResponse.ok) {
    setStatus("Dashboard mislukt", "err");
    renderSummary("Dashboard kon niet worden geladen.", singleResult);
    return;
  }

  const metrics = await metricsResponse.json();
  renderDashboard(metrics, metrics.sources || []);
  setStatus("Dashboard klaar", "ok");
}

function applyRoute(route) {
  activeRoute = route in ROUTES ? route : "business";
  const config = ROUTES[activeRoute];

  routeCards.forEach((button) => {
    button.classList.toggle("active", button.dataset.route === activeRoute);
  });

  panelKicker.textContent = config.title;
  panelTitle.textContent = config.title;
  panelBadge.textContent = config.badge;
  panelLead.textContent = config.lead;
  routeHint.textContent = config.hint;
  runtimeHint.textContent = apiEnabled
    ? `Live modus actief op ${liveApiHost || window.location.host || window.location.href}. Route: ${translateRouteLabel(activeRoute)}.`
    : `Previewmodus via file://. Open ${LIVE_API_BASE} voor live data.`;

  lookupForm.style.display = config.showForm ? "" : "none";
  lookupInput.disabled = !config.showForm;
  lookupInput.placeholder = config.placeholder;
  lookupButton.textContent = config.button;
  refreshToggleWrap.hidden = !config.showRefresh;
  publicOnlyWrap.hidden = !config.showPublicOnly;
  singleOptions.hidden = !(config.showRefresh || config.showPublicOnly);
  spamPanel.hidden = activeRoute !== "spam";
  consentPanel.hidden = activeRoute !== "consent";
  dashboardPanel.hidden = activeRoute !== "dashboard";

  if (activeRoute === "dashboard") {
    renderSummary("Dashboard klaar om te laden.\nKlik op ververs om de metrics op te halen.", singleResult);
    renderEmptyResults("Dashboard gebruikt geen losse scanresultaten.");
    singleResultLayer.className = "result-layer muted-empty";
    singleResultLayer.innerHTML = `<span class="empty-label">Selecteer verversen om metrics op te halen.</span>`;
    updateCounts([]);
  } else if (activeRoute === "consent") {
    renderSummary("Eigen register actief.\nZoek of voeg lokale contacten toe.", singleResult);
    renderEmptyResults("Nog geen lokaal resultaat geselecteerd.");
  } else {
    renderSummary(
      [
        `Route: ${config.title}`,
        `Hint: ${config.hint}`,
        "Voer een nummer in om te zoeken.",
      ].join("\n"),
      singleResult,
    );
    renderEmptyResults("Nog geen scan uitgevoerd voor deze route.");
  }

  if (activeRoute === "consent") {
    renderConsentList();
    renderConsentSearch(lookupInput.value.trim());
  }

  if (activeRoute === "spam") {
    renderSpamReports();
  }

  if (activeRoute === "dashboard") {
    loadDashboard();
  } else {
    updateCounts([]);
    resultStamp.textContent = activeRoute === "consent" ? "eigen register" : "klaar voor zoeken";
  }

  updateLocalStats();
  renderRouteSummary();
}

async function runSingleLookup(phoneNumber) {
  if (!apiEnabled) {
    setStatus("Previewmodus", "busy");
    renderSummary(`Voorbeeldmodus actief.\nOpen ${LIVE_API_BASE} voor live zoeken.`, singleResult);
    renderEmptyResults("De live API is niet beschikbaar in bestandsmodus.");
    return;
  }

  setStatus("Scan gestart", "busy");
  renderSummary(`Zoekopdracht gestart...\nRoute: ${translateRouteLabel(activeRoute)}`, singleResult);
  renderEmptyResults("Resultaten worden geladen...");

  const response = await fetch(`${apiBase}/api/v1/lookup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      phone_number: phoneNumber,
      force_refresh: refreshToggle ? refreshToggle.checked : false,
      mode: activeRoute,
    }),
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
      `Route: ${translateRouteLabel(payload.mode || activeRoute)}`,
      `Zoek-ID: ${payload.request_id}`,
      `Internationaal formaat: ${payload.phone_e164}`,
      `Gevonden resultaten: ${payload.results.length}`,
    ].join("\n"),
    singleResult,
  );

  if ((payload.mode || activeRoute) === "spam") {
    renderSpamResults(payload.results || [], `laatste scan · ${payload.phone_e164}`);
  } else {
    renderBusinessResults(payload.results || [], `laatste scan · ${payload.phone_e164}`);
  }

  setStatus("Scan klaar", "ok");
  updateLocalStats();
}

function resetBulkState() {
  bulkProgressBar.style.width = "0%";
  bulkProgressText.textContent = "0 / 0 voltooide regels";
  renderSummary("Geen actieve taak.", jobStatus);
}

async function pollJob(jobId) {
  const response = await fetch(`${apiBase}/api/v1/jobs/${jobId}`);
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

function renderSpamReportList() {
  renderSpamReports();
}

function addSpamReport(phoneNumber) {
  const label = spamLabel.value.trim() || "Lokale spamnotitie";
  const reason = spamReason.value.trim() || "Geen toelichting opgegeven";
  const reports = loadSpamReports();
  reports.push({
    phone: phoneNumber,
    label,
    reason,
    createdAt: new Date().toISOString(),
  });
  saveSpamReports(reports.slice(-100));
  spamLabel.value = "";
  spamReason.value = "";
  renderSpamReportList();
  updateLocalStats();
}

function addContact() {
  const name = contactName.value.trim();
  const phone = contactPhone.value.trim();
  if (!phone && !name) {
    renderSummary("Vul minimaal een naam of een nummer in.", singleResult);
    return;
  }
  const contacts = loadContacts();
  contacts.push({
    name,
    phone,
    company: contactCompany.value.trim(),
    note: contactNote.value.trim(),
    createdAt: new Date().toISOString(),
  });
  saveContacts(contacts.slice(-200));
  contactName.value = "";
  contactPhone.value = "";
  contactCompany.value = "";
  contactNote.value = "";
  renderConsentList();
  updateLocalStats();
  showConsentStatus("Contact opgeslagen in lokaal logboek.", "ok");
}

function exportContacts() {
  const contacts = loadContacts();
  if (!contacts.length) {
    showConsentStatus("Geen contacten om te exporteren.", "warn");
    return;
  }
  const payload = {
    version: 1,
    exported_at: new Date().toISOString(),
    records: contacts,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const link = document.createElement("a");
  const timestamp = new Date().toISOString().slice(0, 10);
  link.href = URL.createObjectURL(blob);
  link.download = `belradar_toestemmingslogboek_${timestamp}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
  showConsentStatus(`Export voltooid (${contacts.length} records).`, "ok");
}

async function importContacts() {
  const file = importContactsFile.files ? importContactsFile.files[0] : null;
  if (!file) {
    showConsentStatus("Selecteer eerst een bestand.", "warn");
    return;
  }

  try {
    const raw = await file.text();
    let records = [];
    if (/\.json(\?.*)?$/i.test(file.name) || /^\s*[{[]/.test(raw)) {
      const parsed = JSON.parse(raw);
      records = parseImportedContacts(parsed);
    } else {
      records = parseCsv(raw).map((row) => sanitizeContactRecord(row)).filter(Boolean);
    }

    const before = loadContacts();
    const merged = mergeContacts(before, records);
    if (!merged.length) {
      showConsentStatus("Import bevat geen geldige contacten.", "err");
      return;
    }

    saveContacts(merged.slice(-200));
    renderConsentList();
    updateLocalStats();
    showConsentStatus(`Import voltooid: ${records.length} regels verwerkt, ${merged.length} unieke contactregels actief.`, "ok");
    if (activeRoute === "consent") {
      renderConsentSearch(lookupInput.value.trim() || "");
    }
  } catch (error) {
    showConsentStatus(`Import mislukt: ${error.message}`, "err");
  } finally {
    importContactsFile.value = "";
  }
}

function clearContacts() {
  saveContacts([]);
  renderConsentList();
  updateLocalStats();
  showConsentStatus("Toestemmingslogboek is verwijderd.", "warn");
  if (activeRoute === "consent") {
    renderConsentSearch("");
  }
}

function promptContactImport() {
  if (importContactsFile) {
    importContactsFile.click();
  }
}

function renderBulkSummary(response) {
  if (response.job_id) {
    renderSummary(`Asynchrone batchscan gestart: ${response.job_id}`, bulkResult);
    pollJob(response.job_id);
    return;
  }

  bulkProgressBar.style.width = "100%";
  bulkProgressText.textContent = `${response.request_count} / ${response.request_count} voltooide regels`;
  setStatus("Batch klaar", "ok");
  renderSummary(`Synchrone batch voltooid: ${response.request_count} nummers`, bulkResult);
}

lookupForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const value = lookupInput.value.trim();

  if (!value) {
    setStatus("Invoer ontbreekt", "err");
    renderSummary("Vul eerst een telefoonnummer in.", singleResult);
    return;
  }

  if (activeRoute === "consent") {
    renderConsentSearch(value);
    return;
  }

  if (activeRoute === "dashboard") {
    await loadDashboard();
    return;
  }

  await runSingleLookup(value);
});

routeCards.forEach((button) => {
  button.addEventListener("click", () => applyRoute(button.dataset.route || "business"));
});

refreshDashboard.addEventListener("click", () => loadDashboard());

spamForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const currentPhone = lookupInput.value.trim();
  if (!currentPhone) {
    setStatus("Invoer ontbreekt", "err");
    renderSummary("Gebruik eerst een nummer voordat je een spamnotitie opslaat.", singleResult);
    return;
  }
  addSpamReport(currentPhone);
  setStatus("Spamnotitie opgeslagen", "ok");
});

consentForm.addEventListener("submit", (event) => {
  event.preventDefault();
  addContact();
  setStatus("Eigen contact opgeslagen", "ok");
  renderSummary("Contact opgeslagen in het eigen register.", singleResult);
});

if (exportContactsBtn) {
  exportContactsBtn.addEventListener("click", exportContacts);
}
if (importContactsBtn) {
  importContactsBtn.addEventListener("click", promptContactImport);
}
if (importContactsFile) {
  importContactsFile.addEventListener("change", importContacts);
}
if (clearContactsBtn) {
  clearContactsBtn.addEventListener("click", () => {
    if (window.confirm("Weet je zeker dat je het volledige toestemmingslogboek wilt wissen?")) {
      clearContacts();
    }
  });
}

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
    renderSummary(`Previewmodus actief.\nOpen ${LIVE_API_BASE} voor batchjobs.`, bulkResult);
    return;
  }

  setStatus("Batch gestart", "busy");
  bulkProgressBar.style.width = "0%";
  bulkProgressText.textContent = "0 / 0 voltooide regels";
  renderSummary("Batchscan wordt gestart...", bulkResult);
  renderSummary("Geen actieve taak.", jobStatus);

  const response = await fetch(`${apiBase}/api/v1/lookup/bulk`, {
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

  renderBulkSummary(payload);
});

updateLocalStats();
renderRouteSummary();
renderSpamReportList();
renderConsentList();
resetBulkState();

  if (!apiEnabled) {
  runtimeHint.textContent = `Previewmodus via file://. Open ${LIVE_API_BASE} voor live zoekopdrachten.`;
  setStatus("Previewmodus", "busy");
} else {
  runtimeHint.textContent = `Live modus actief op ${window.location.host || window.location.href}. Resultaten komen direct uit de API en openbare bronnen.`;
  setStatus("Systeem klaar", "idle");
}

applyRoute("business");
