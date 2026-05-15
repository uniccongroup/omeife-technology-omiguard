const dashboardConfig = window.OMIGUARD_CONFIG || {};
const DATABASE_URL = dashboardConfig.databaseUrl || "https://YOUR_PROJECT_ID-default-rtdb.firebaseio.com";
const DEVICE_ID = dashboardConfig.deviceId || "node_01";
const REFRESH_MS = 10000;
const HISTORY_REFRESH_MS = 60000;
const ALERT_REFRESH_MS = 60000;
const HISTORY_LIMIT = 24;
const HISTORY_FETCH_LIMIT = 30;
const ALERT_FETCH_LIMIT = 20;
const CHAT_API_URL =
  window.location.hostname
    ? `${window.location.protocol}//${window.location.hostname}:8000/chat`
    : "http://127.0.0.1:8000/chat";

const latestUrls = [
  `${DATABASE_URL}/predictions/${DEVICE_ID}/latest.json`,
  `${DATABASE_URL}/sensor_data/${DEVICE_ID}/predictions/latest.json`,
];

const historyUrls = [
  firebaseLimitQuery(`${DATABASE_URL}/predictions/${DEVICE_ID}/history.json`, HISTORY_FETCH_LIMIT),
  firebaseLimitQuery(`${DATABASE_URL}/sensor_data/${DEVICE_ID}/predictions/history.json`, HISTORY_FETCH_LIMIT),
];

const alertHistoryUrls = [
  firebaseLimitQuery(`${DATABASE_URL}/alerts/${DEVICE_ID}/history.json`, ALERT_FETCH_LIMIT),
  firebaseLimitQuery(`${DATABASE_URL}/sensor_data/${DEVICE_ID}/alerts/history.json`, ALERT_FETCH_LIMIT),
];

const els = {};
let lastRenderedData = null;
let cachedHistory = [];
let cachedAlerts = [];
let lastHistoryFetch = 0;
let lastAlertFetch = 0;

function byId(id) {
  return document.getElementById(id);
}

function firebaseLimitQuery(url, limit) {
  const params = new URLSearchParams({
    orderBy: '"$key"',
    limitToLast: String(limit),
  });
  return `${url}?${params.toString()}`;
}

function cacheElements() {
  [
    "connectionState",
    "lastUpdated",
    "navRiskCount",
    "deviceNavLabel",
    "riskCard",
    "riskVisual",
    "riskBadge",
    "riskClass",
    "riskAction",
    "riskScore",
    "riskScoreDelta",
    "riskScoreRing",
    "ringScore",
    "predictionTime",
    "sensorTime",
    "anomalyFlag",
    "ruleRiskValue",
    "dominantPollutant",
    "coValue",
    "so2Value",
    "no2Value",
    "pm1Value",
    "pm25Value",
    "pm10Value",
    "temperatureValue",
    "humidityValue",
    "coLevel",
    "so2Level",
    "no2Level",
    "pm1Level",
    "pm25Level",
    "pm10Level",
    "temperatureLevel",
    "humidityLevel",
    "childExposureScore",
    "gasLoad",
    "pmLoad",
    "humidityFlag",
    "deviceId",
    "historyCount",
    "historyBody",
    "navAlertCount",
    "notificationButton",
    "notificationBadge",
    "alertsNavLink",
    "alertsModal",
    "alertsModalClose",
    "alertCount",
    "alertLastSent",
    "alertList",
    "aqiTrendChart",
    "riskTrendChart",
  ].forEach((id) => {
    els[id] = byId(id);
  });
}

function initIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function initSidebarNavigation() {
  const sidebar = byId("sidebar");
  const menuToggle = byId("mobileMenuToggle");

  function syncMenuVisibility() {
    if (!sidebar || !menuToggle) return;
    const isMobile = window.matchMedia("(max-width: 900px)").matches;
    menuToggle.hidden = !isMobile;
    if (!isMobile) {
      sidebar.classList.remove("menu-open");
      menuToggle.setAttribute("aria-expanded", "false");
      menuToggle.setAttribute("aria-label", "Open navigation menu");
      menuToggle.innerHTML = '<i data-lucide="menu"></i>';
      initIcons();
    }
  }

  if (sidebar && menuToggle) {
    syncMenuVisibility();
    window.addEventListener("resize", syncMenuVisibility);

    menuToggle.addEventListener("click", () => {
      const isOpen = sidebar.classList.toggle("menu-open");
      menuToggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
      menuToggle.setAttribute("aria-label", isOpen ? "Close navigation menu" : "Open navigation menu");
      menuToggle.innerHTML = `<i data-lucide="${isOpen ? "x" : "menu"}"></i>`;
      initIcons();
    });
  }

  document.querySelectorAll(".nav-link").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      document.querySelectorAll(".nav-link.active").forEach((activeLink) => {
        activeLink.classList.remove("active");
        activeLink.removeAttribute("aria-current");
      });
      link.classList.add("active");
      link.setAttribute("aria-current", "page");
      if (link.dataset.panel === "alerts") {
        setAlertsModalOpen(true);
      }
      if (sidebar && menuToggle && window.matchMedia("(max-width: 900px)").matches) {
        sidebar.classList.remove("menu-open");
        menuToggle.setAttribute("aria-expanded", "false");
        menuToggle.setAttribute("aria-label", "Open navigation menu");
        menuToggle.innerHTML = '<i data-lucide="menu"></i>';
        initIcons();
      }
    });
  });
}

function dashboardSearchTargets() {
  return [
    { id: "riskCard", terms: "dashboard overview risk prediction safe caution dangerous anomaly alerts live prediction" },
    { id: "riskScoreCard", terms: "risk score model confidence percentage" },
    { id: "coCard", terms: "co carbon monoxide gas ppm" },
    { id: "so2Card", terms: "so2 sulphur sulfur dioxide gas ppm" },
    { id: "aqiCard", terms: "aqi air quality trend chart 30 day graph" },
    { id: "no2Card", terms: "no2 nitrogen dioxide gas ppm" },
    { id: "pm1Card", terms: "pm1 pm1.0 particulate matter dust" },
    { id: "pmCard", terms: "pm2.5 pm25 pm10 particulate matter dust" },
    { id: "weatherCard", terms: "temperature humidity weather heat moisture" },
    { id: "confidenceCard", terms: "confidence device node ring score model" },
    { id: "summaryCard", terms: "summary exposure dominant pollutant child score gas load pm load humidity flag" },
    { id: "riskHistoryCard", terms: "timeline risk history chart prediction history" },
    { id: "predictionsCard", terms: "recent predictions table records history anomaly dominant" },
  ];
}

function normalizeSearchTerm(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function scoreSearchTarget(query, target) {
  const element = byId(target.id);
  if (!element) return 0;

  const haystack = normalizeSearchTerm(
    `${target.terms} ${element.dataset.searchLabel || ""} ${element.textContent || ""}`
  );

  if (!haystack) return 0;
  if (haystack.includes(query)) return 100 + query.length;

  return query
    .split(" ")
    .filter((word) => word.length > 1 && haystack.includes(word))
    .length;
}

function highlightSearchTarget(element) {
  if (!element) return;
  document.querySelectorAll(".search-highlight").forEach((item) => {
    item.classList.remove("search-highlight");
  });
  element.classList.add("search-highlight");
  window.setTimeout(() => element.classList.remove("search-highlight"), 1800);
}

function scrollToSearchTarget(element) {
  if (!element) return;
  element.scrollIntoView({ behavior: "smooth", block: "start", inline: "nearest" });
  highlightSearchTarget(element);
}

function runDashboardSearch(query) {
  const searchTerm = normalizeSearchTerm(query);
  if (!searchTerm) return;

  if (["chat", "assistant", "omi chat", "omiguard chat"].some((term) => searchTerm.includes(term))) {
    setChatOpen(true);
    return;
  }

  if (["device", "node", "sensor node", "settings"].some((term) => searchTerm.includes(term))) {
    const target = byId("confidenceCard") || byId("deviceNavLink");
    scrollToSearchTarget(target);
    return;
  }

  const match = dashboardSearchTargets()
    .map((target) => ({
      ...target,
      score: scoreSearchTarget(searchTerm, target),
    }))
    .sort((a, b) => b.score - a.score)[0];

  if (match?.score > 0) {
    scrollToSearchTarget(byId(match.id));
    return;
  }

  const fallback = byId("overviewSection") || byId("riskCard");
  scrollToSearchTarget(fallback);
}

function initDashboardSearch() {
  const searchInput = byId("dashboardSearch");
  const searchBox = document.querySelector(".search-box");
  if (!searchInput) return;

  searchInput.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    runDashboardSearch(searchInput.value);
  });

  searchInput.addEventListener("search", () => {
    runDashboardSearch(searchInput.value);
  });

  searchBox?.querySelector("kbd")?.addEventListener("click", () => {
    runDashboardSearch(searchInput.value);
  });
}

function toNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatNumber(value, digits = 2) {
  const number = toNumber(value);
  if (number === null) return "--";
  if (Math.abs(number) >= 100) return number.toFixed(0);
  return number.toFixed(digits).replace(/\.?0+$/, "");
}

function formatTime(value) {
  if (!value) return "--";
  let date;
  if (typeof value === "number") {
    date = new Date(value < 10000000000 ? value * 1000 : value);
  } else {
    date = new Date(value);
  }
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function formatDateTime(value) {
  if (!value) return "--";
  let date;
  if (typeof value === "number") {
    date = new Date(value < 10000000000 ? value * 1000 : value);
  } else {
    date = new Date(value);
  }
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCompactDateTime(value) {
  if (!value) return "--";
  let date;
  if (typeof value === "number") {
    date = new Date(value < 10000000000 ? value * 1000 : value);
  } else {
    date = new Date(value);
  }
  if (Number.isNaN(date.getTime())) return String(value);
  const day = String(date.getDate()).padStart(2, "0");
  const month = date.toLocaleString([], { month: "short" });
  const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return `${month} ${day} ${time}`;
}

function riskClassName(risk) {
  const value = String(risk || "").toLowerCase();
  if (value === "safe") return "safe";
  if (value === "moderate") return "moderate";
  if (value === "caution") return "caution";
  if (value === "dangerous" || value === "danger") return "dangerous";
  return "neutral";
}

function riskIconName(className) {
  if (className === "safe") return "shield-check";
  if (className === "moderate") return "shield-alert";
  if (className === "caution") return "triangle-alert";
  if (className === "dangerous") return "siren";
  return "shield-alert";
}

function riskLevelName(level) {
  const value = toNumber(level);
  if (value === 3) return "Dangerous";
  if (value === 2) return "Caution";
  if (value === 1) return "Moderate";
  if (value === 0) return "Safe";
  return "--";
}

function escapeHtml(value) {
  return String(value ?? "--")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function mergeSensorData(record) {
  const preparedPayload = record.prepared_payload || {};
  const sensorData = record.sensor_data || {};
  const preparedFeatures = record.prepared_features || {};
  const inputData = record.input_data || {};

  return {
    ...preparedPayload,
    ...inputData,
    ...sensorData,
    ...preparedFeatures,
    co: record.co ?? sensorData.co ?? preparedPayload.co ?? inputData.co,
    so2: record.so2 ?? sensorData.so2 ?? preparedPayload.so2 ?? inputData.so2,
    no2: record.no2 ?? sensorData.no2 ?? preparedPayload.no2 ?? inputData.no2,
    pm1_0: record.pm1_0 ?? sensorData.pm1_0 ?? preparedPayload.pm1_0 ?? inputData.pm1_0,
    pm2_5: record.pm2_5 ?? sensorData.pm2_5 ?? preparedPayload.pm2_5 ?? inputData.pm2_5,
    pm10: record.pm10 ?? sensorData.pm10 ?? preparedPayload.pm10 ?? inputData.pm10,
    temperature:
      record.temperature ?? sensorData.temperature ?? preparedPayload.temperature ?? inputData.temperature,
    humidity: record.humidity ?? sensorData.humidity ?? preparedPayload.humidity ?? inputData.humidity,
    total_gas_load:
      record.total_gas_load ??
      sensorData.total_gas_load ??
      preparedFeatures.total_gas_load ??
      preparedPayload.total_gas_load,
    total_pm_load:
      record.total_pm_load ??
      sensorData.total_pm_load ??
      preparedFeatures.total_pm_load ??
      preparedPayload.total_pm_load,
    child_exposure_score:
      record.child_exposure_score ??
      sensorData.child_exposure_score ??
      preparedFeatures.child_exposure_score ??
      preparedPayload.child_exposure_score,
    high_humidity_flag:
      record.high_humidity_flag ??
      sensorData.high_humidity_flag ??
      preparedFeatures.high_humidity_flag ??
      preparedPayload.high_humidity_flag,
    rule_based_risk_level:
      record.rule_based_risk_level ?? sensorData.rule_based_risk_level ?? preparedPayload.rule_based_risk_level,
    rule_based_risk_class:
      record.rule_based_risk_class ?? sensorData.rule_based_risk_class ?? preparedPayload.rule_based_risk_class,
    dominant_risk_factor:
      record.dominant_risk_factor ??
      record.who_dominant_pollutant ??
      sensorData.dominant_risk_factor ??
      sensorData.who_dominant_pollutant ??
      preparedPayload.dominant_risk_factor ??
      preparedPayload.who_dominant_pollutant,
    co_risk_level: record.co_risk_level ?? sensorData.co_risk_level ?? preparedPayload.co_risk_level,
    so2_risk_level: record.so2_risk_level ?? sensorData.so2_risk_level ?? preparedPayload.so2_risk_level,
    no2_risk_level: record.no2_risk_level ?? sensorData.no2_risk_level ?? preparedPayload.no2_risk_level,
    pm2_5_risk_level:
      record.pm2_5_risk_level ?? sensorData.pm2_5_risk_level ?? preparedPayload.pm2_5_risk_level,
    pm10_risk_level: record.pm10_risk_level ?? sensorData.pm10_risk_level ?? preparedPayload.pm10_risk_level,
    temperature_risk_level:
      record.temperature_risk_level ??
      sensorData.temperature_risk_level ??
      preparedPayload.temperature_risk_level,
  };
}

function normalizeRecord(record, key = "") {
  if (!record) return null;

  const prediction = record.prediction || {};
  const sensor = mergeSensorData(record);
  const risk = record.risk_class ?? prediction.risk_class ?? sensor.rule_based_risk_class ?? "Unknown";
  const score = record.risk_score ?? prediction.risk_score;
  const anomaly = record.anomaly_flag ?? prediction.anomaly_flag;
  const action =
    record.llm_action_recommendation ??
    prediction.llm_action_recommendation ??
    record.action_recommendation ??
    prediction.action_recommendation ??
    "Waiting for the next LLM recommendation.";

  return {
    key,
    raw: record,
    sensor,
    device_id: record.device_id ?? sensor.device_id ?? DEVICE_ID,
    prediction_time: record.prediction_time ?? record.prediction_timestamp ?? record.created_at,
    sensor_timestamp:
      record.sensor_timestamp ?? record.timestamp ?? sensor.timestamp ?? record.input_data?.timestamp,
    risk_class: risk,
    risk_score: score,
    anomaly_flag: Boolean(anomaly),
    action_recommendation: action,
    rule_based_risk_level: sensor.rule_based_risk_level,
    rule_based_risk_class: sensor.rule_based_risk_class,
    dominant: sensor.dominant_risk_factor,
  };
}

function normalizeAlertRecord(record, key = "") {
  if (!record) return null;
  const prediction = normalizeRecord(record, key);
  return {
    ...prediction,
    sent_at: record.sent_at ?? record.alert_sent_at ?? record.created_at,
    subject: record.subject ?? "OmiGuard gas risk alert",
    from_name: record.from_name,
    from_email: record.from_email,
    to_emails: Array.isArray(record.to_emails)
      ? record.to_emails
      : String(record.to_emails || "")
          .split(",")
          .map((email) => email.trim())
          .filter(Boolean),
  };
}

async function fetchJson(url) {
  const separator = url.includes("?") ? "&" : "?";
  const response = await fetch(`${url}${separator}ts=${Date.now()}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Firebase request failed: ${response.status}`);
  return response.json();
}

async function fetchFirst(urls) {
  let lastError = null;

  for (const url of urls) {
    try {
      const data = await fetchJson(url);
      if (data !== null && data !== undefined) return data;
    } catch (error) {
      lastError = error;
    }
  }

  if (lastError) throw lastError;
  return null;
}

function normalizeHistoryRecords(historyRaw) {
  return Object.entries(historyRaw || {})
    .map(([key, value]) => normalizeRecord(value, key))
    .filter(Boolean)
    .sort((a, b) => {
      const aTime = new Date(a.prediction_time || a.sensor_timestamp || 0).getTime();
      const bTime = new Date(b.prediction_time || b.sensor_timestamp || 0).getTime();
      return bTime - aTime;
    })
    .slice(0, HISTORY_LIMIT);
}

function normalizeAlertRecords(alertsRaw) {
  return Object.entries(alertsRaw || {})
    .map(([key, value]) => normalizeAlertRecord(value, key))
    .filter(Boolean)
    .sort((a, b) => {
      const aTime = new Date(a.sent_at || a.prediction_time || a.sensor_timestamp || 0).getTime();
      const bTime = new Date(b.sent_at || b.prediction_time || b.sensor_timestamp || 0).getTime();
      return bTime - aTime;
    });
}

async function loadData(options = {}) {
  const now = Date.now();
  const shouldFetchHistory =
    options.forceHistory || !lastHistoryFetch || now - lastHistoryFetch >= HISTORY_REFRESH_MS;
  const shouldFetchAlerts = options.forceAlerts || !lastAlertFetch || now - lastAlertFetch >= ALERT_REFRESH_MS;

  const latestRaw = await fetchFirst(latestUrls);
  const latest = normalizeRecord(latestRaw, "latest");

  if (shouldFetchHistory) {
    try {
      const historyRaw = await fetchFirst(historyUrls);
      cachedHistory = normalizeHistoryRecords(historyRaw);
      lastHistoryFetch = now;
    } catch (error) {
      console.warn("Prediction history unavailable:", error);
    }
  }

  if (shouldFetchAlerts) {
    try {
      const alertsRaw = await fetchFirst(alertHistoryUrls);
      cachedAlerts = normalizeAlertRecords(alertsRaw);
      lastAlertFetch = now;
    } catch (error) {
      console.warn("Alert history unavailable:", error);
    }
  }

  return { latest, history: cachedHistory, alerts: cachedAlerts };
}

function setConnection(state, text) {
  if (!els.connectionState) return;
  els.connectionState.textContent = text;
  els.connectionState.className = `status-pill ${state}`;
}

function setText(id, value) {
  if (els[id]) els[id].textContent = value;
}

function updateRisk(latest) {
  const className = riskClassName(latest?.risk_class);
  const risk = latest?.risk_class || "--";
  const score = toNumber(latest?.risk_score);
  const scorePercent = score === null ? null : Math.max(0, Math.min(100, score * 100));

  setText("riskClass", risk);
  setText("riskAction", latest?.action_recommendation || "Waiting for the next LLM recommendation.");
  setText("riskBadge", risk);
  setText("riskScore", scorePercent === null ? "--" : `${formatNumber(scorePercent, 0)}%`);
  setText("ringScore", scorePercent === null ? "--" : `${formatNumber(scorePercent, 0)}%`);
  setText("riskScoreDelta", scorePercent === null ? "--" : "model confidence");
  setText("predictionTime", formatCompactDateTime(latest?.prediction_time));
  setText("sensorTime", formatCompactDateTime(latest?.sensor_timestamp));
  setText("anomalyFlag", latest?.anomaly_flag ? "Detected" : "Clear");

  if (els.riskBadge) els.riskBadge.className = `status-pill ${className}`;
  if (els.riskVisual) {
    els.riskVisual.className = `hero-visual ${className}`;
    const orbit = els.riskVisual.querySelector(".shield-orbit");
    if (orbit) orbit.innerHTML = `<i id="riskVisualIcon" data-lucide="${riskIconName(className)}"></i>`;
  }
  if (els.riskScoreRing) {
    const degrees = scorePercent === null ? 0 : scorePercent * 3.6;
    els.riskScoreRing.style.setProperty("--progress", `${degrees}deg`);
  }
  if (els.navRiskCount) {
    els.navRiskCount.textContent = className === "dangerous" || className === "caution" ? "1" : "0";
  }
}

function updateSensorValues(sensor) {
  setText("coValue", formatNumber(sensor?.co, 2));
  setText("so2Value", formatNumber(sensor?.so2, 3));
  setText("no2Value", formatNumber(sensor?.no2, 3));
  setText("pm1Value", formatNumber(sensor?.pm1_0, 0));
  setText("pm25Value", formatNumber(sensor?.pm2_5, 0));
  setText("pm10Value", formatNumber(sensor?.pm10, 0));
  setText("temperatureValue", `${formatNumber(sensor?.temperature, 1)} `);
  setText("humidityValue", `${formatNumber(sensor?.humidity, 0)}%`);

  updateLevelText("coLevel", sensor?.co_risk_level, "ppm");
  updateLevelText("so2Level", sensor?.so2_risk_level, "ppm");
  updateLevelText("no2Level", sensor?.no2_risk_level, "ppm");
  updateLevelText("pm1Level", null, "ug/m3");
  updateLevelText("pm25Level", sensor?.pm2_5_risk_level, "ug/m3");
  updateLevelText("pm10Level", sensor?.pm10_risk_level, "ug/m3");
  updateLevelText("temperatureLevel", sensor?.temperature_risk_level, "°C");
  updateHumidityLevel(sensor);
}

function updateLevelText(id, level, fallbackUnit) {
  const element = els[id];
  if (!element) return;

  const label = riskLevelName(level);
  const className = riskClassName(label);
  element.textContent = label === "--" ? fallbackUnit : label;
  element.className = `delta ${label === "--" ? "neutral" : className}`;
}

function updateHumidityLevel(sensor) {
  const element = els.humidityLevel;
  if (!element) return;

  if (!sensor || sensor.high_humidity_flag === undefined || sensor.high_humidity_flag === null) {
    element.textContent = "%";
    element.className = "delta neutral";
    return;
  }

  const isHigh = toNumber(sensor.high_humidity_flag) === 1;
  element.textContent = isHigh ? "High" : "Normal";
  element.className = `delta ${isHigh ? "caution" : "safe"}`;
}

function updateSummary(latest) {
  const sensor = latest?.sensor || {};
  const ruleLabel = sensor.rule_based_risk_class || riskLevelName(sensor.rule_based_risk_level);

  setText("ruleRiskValue", ruleLabel);
  setText("dominantPollutant", sensor.dominant_risk_factor || latest?.dominant || "--");
  setText("childExposureScore", formatNumber(sensor.child_exposure_score, 2));
  setText("gasLoad", formatNumber(sensor.total_gas_load, 2));
  setText("pmLoad", formatNumber(sensor.total_pm_load, 0));
  setText("humidityFlag", toNumber(sensor.high_humidity_flag) === 1 ? "High" : "Normal");
  setText("deviceId", latest?.device_id || DEVICE_ID);
  setText("deviceNavLabel", latest?.device_id || DEVICE_ID);
}

function updateHistory(history) {
  const rows = history.slice(0, HISTORY_LIMIT);
  setText("historyCount", `${rows.length} records`);

  if (!rows.length) {
    els.historyBody.innerHTML =
      '<tr><td colspan="5" class="empty-cell">Waiting for prediction history...</td></tr>';
    return;
  }

  els.historyBody.innerHTML = rows
    .map((item) => {
      const riskClass = riskClassName(item.risk_class);
      const score = toNumber(item.risk_score);
      const scoreText = score === null ? "--" : `${formatNumber(score * 100, 0)}%`;
      return `
        <tr>
          <td>${escapeHtml(formatTime(item.prediction_time || item.sensor_timestamp))}</td>
          <td><span class="status-pill ${riskClass}">${escapeHtml(item.risk_class)}</span></td>
          <td>${escapeHtml(scoreText)}</td>
          <td>${item.anomaly_flag ? "Yes" : "No"}</td>
          <td>${escapeHtml(item.dominant || "--")}</td>
        </tr>
      `;
    })
    .join("");
}

function activeRiskAlert(latest) {
  const className = riskClassName(latest?.risk_class);
  return className === "dangerous" || className === "caution";
}

function updateAlertIndicators(latest, alerts) {
  const sentCount = alerts.length;
  const hasActiveRisk = activeRiskAlert(latest);
  const visibleCount = Math.max(sentCount, hasActiveRisk ? 1 : 0);

  setText("navAlertCount", String(visibleCount));
  if (els.notificationBadge) {
    els.notificationBadge.textContent = String(visibleCount);
    els.notificationBadge.hidden = visibleCount === 0;
  }
  if (els.notificationButton) {
    els.notificationButton.classList.toggle("alerting", hasActiveRisk || sentCount > 0);
    els.notificationButton.setAttribute(
      "aria-label",
      hasActiveRisk ? `${latest.risk_class} notification active` : "Notifications"
    );
  }
}

function renderAlertList(latest, alerts) {
  setText("alertCount", String(alerts.length));
  setText("alertLastSent", alerts.length ? formatCompactDateTime(alerts[0].sent_at) : "--");

  if (!els.alertList) return;
  if (!alerts.length) {
    if (activeRiskAlert(latest)) {
      els.alertList.innerHTML = `
        <article class="alert-item ${riskClassName(latest.risk_class)}">
          <div class="alert-item-head">
            <h3>${escapeHtml(latest.risk_class)} condition active</h3>
            <span class="status-pill ${riskClassName(latest.risk_class)}">Not sent yet</span>
          </div>
          <div class="alert-meta">
            <span>Prediction: <strong>${escapeHtml(formatCompactDateTime(latest.prediction_time))}</strong></span>
            <span>Risk score: <strong>${escapeHtml(formatNumber(toNumber(latest.risk_score) * 100, 0))}%</strong></span>
          </div>
          <p class="alert-recommendation">${escapeHtml(latest.action_recommendation)}</p>
        </article>
      `;
      return;
    }

    els.alertList.innerHTML = '<p class="empty-cell">No sent alerts yet.</p>';
    return;
  }

  els.alertList.innerHTML = alerts
    .map((alert) => {
      const riskClass = riskClassName(alert.risk_class);
      const score = toNumber(alert.risk_score);
      const scoreText = score === null ? "--" : `${formatNumber(score * 100, 0)}%`;
      const recipients = alert.to_emails.length ? alert.to_emails.join(", ") : "--";
      return `
        <article class="alert-item ${riskClass}">
          <div class="alert-item-head">
            <h3>${escapeHtml(alert.subject)}</h3>
            <span class="status-pill ${riskClass}">${escapeHtml(alert.risk_class)}</span>
          </div>
          <div class="alert-meta">
            <span>Sent: <strong>${escapeHtml(formatCompactDateTime(alert.sent_at))}</strong></span>
            <span>Prediction: <strong>${escapeHtml(formatCompactDateTime(alert.prediction_time))}</strong></span>
            <span>Risk score: <strong>${escapeHtml(scoreText)}</strong></span>
            <span>Anomaly: <strong>${alert.anomaly_flag ? "Detected" : "Clear"}</strong></span>
          </div>
          <p class="alert-recipients">To: <strong>${escapeHtml(recipients)}</strong></p>
          <p class="alert-recommendation">${escapeHtml(alert.action_recommendation)}</p>
        </article>
      `;
    })
    .join("");
}

function setupCanvas(canvas) {
  const ctx = canvas.getContext("2d");
  const rect = canvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.max(1, rect.width * dpr);
  canvas.height = Math.max(1, rect.height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { ctx, width: rect.width, height: rect.height };
}

function roundedRectPath(ctx, x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height / 2);
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + width - r, y);
  ctx.quadraticCurveTo(x + width, y, x + width, y + r);
  ctx.lineTo(x + width, y + height - r);
  ctx.quadraticCurveTo(x + width, y + height, x + width - r, y + height);
  ctx.lineTo(x + r, y + height);
  ctx.quadraticCurveTo(x, y + height, x, y + height - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
}

function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function aqiFromRecord(item) {
  return toNumber(
    item?.sensor?.aqi ??
      item?.raw?.aqi ??
      item?.raw?.prepared_payload?.aqi ??
      item?.raw?.prepared_features?.aqi ??
      item?.raw?.sensor_data?.aqi
  );
}

function dateFromRecord(item) {
  const value =
    item?.prediction_time ??
    item?.sensor_timestamp ??
    item?.raw?.prediction_timestamp ??
    item?.raw?.created_at;
  if (!value) return null;

  const date =
    typeof value === "number"
      ? new Date(value < 10000000000 ? value * 1000 : value)
      : new Date(value);

  return Number.isNaN(date.getTime()) ? null : date;
}

function formatShortDate(value) {
  return value.toLocaleDateString([], { month: "short", day: "numeric" });
}

function drawAqiTrendChart(records) {
  const canvas = els.aqiTrendChart;
  if (!canvas) return;

  const { ctx, width, height } = setupCanvas(canvas);
  const pad = { top: 18, right: 22, bottom: 40, left: 54 };
  const chartWidth = width - pad.left - pad.right;
  const chartHeight = height - pad.top - pad.bottom;
  const rangeEnd = new Date();
  const rangeStart = new Date(rangeEnd);
  rangeStart.setDate(rangeEnd.getDate() - 30);
  const points = records
    .map((item) => ({
      date: dateFromRecord(item),
      value: aqiFromRecord(item),
    }))
    .filter((item) => item.date && item.value !== null && item.date >= rangeStart && item.date <= rangeEnd)
    .sort((a, b) => a.date - b.date);

  ctx.clearRect(0, 0, width, height);

  const maxAqi = Math.max(100, ...points.map((point) => point.value));
  const yMax = Math.max(100, Math.ceil(maxAqi / 100) * 100);

  ctx.font = "11px Segoe UI";
  ctx.textAlign = "right";
  ctx.fillStyle = cssVar("--muted");
  for (let i = 0; i <= 4; i += 1) {
    const value = yMax - (yMax / 4) * i;
    const y = pad.top + (chartHeight / 4) * i;
    ctx.strokeStyle = "#f0edf6";
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.fillText(formatNumber(value, 0), pad.left - 10, y + 4);
  }

  ctx.strokeStyle = cssVar("--line");
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, height - pad.bottom);
  ctx.lineTo(width - pad.right, height - pad.bottom);
  ctx.stroke();

  if (!points.length) {
    ctx.fillStyle = cssVar("--muted");
    ctx.font = "13px Segoe UI";
    ctx.textAlign = "left";
    ctx.fillText("Waiting for AQI history", pad.left + 10, height / 2);
    return;
  }

  const xFor = (date) =>
    pad.left + ((date.getTime() - rangeStart.getTime()) / (rangeEnd.getTime() - rangeStart.getTime())) * chartWidth;
  const yFor = (value) => height - pad.bottom - Math.max(0, Math.min(yMax, value)) / yMax * chartHeight;

  [
    { value: 100, color: cssVar("--green") },
    { value: 200, color: cssVar("--amber") },
    { value: 400, color: cssVar("--red") },
  ].forEach((threshold) => {
    if (threshold.value > yMax) return;
    const y = yFor(threshold.value);
    ctx.setLineDash([5, 5]);
    ctx.strokeStyle = threshold.color;
    ctx.globalAlpha = 0.45;
    ctx.beginPath();
    ctx.moveTo(pad.left, y);
    ctx.lineTo(width - pad.right, y);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.setLineDash([]);
  });

  if (points.length > 1) {
    const gradient = ctx.createLinearGradient(0, pad.top, 0, height - pad.bottom);
    gradient.addColorStop(0, "rgba(105, 108, 255, 0.2)");
    gradient.addColorStop(1, "rgba(105, 108, 255, 0)");

    ctx.beginPath();
    points.forEach((point, index) => {
      const x = xFor(point.date);
      const y = yFor(point.value);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.lineTo(xFor(points[points.length - 1].date), height - pad.bottom);
    ctx.lineTo(xFor(points[0].date), height - pad.bottom);
    ctx.closePath();
    ctx.fillStyle = gradient;
    ctx.fill();

    ctx.beginPath();
    points.forEach((point, index) => {
      const x = xFor(point.date);
      const y = yFor(point.value);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = cssVar("--primary");
    ctx.lineWidth = 3;
    ctx.stroke();
  }

  ctx.fillStyle = cssVar("--primary");
  points.forEach((point) => {
    ctx.beginPath();
    ctx.arc(xFor(point.date), yFor(point.value), 3.5, 0, Math.PI * 2);
    ctx.fill();
  });

  const latestPoint = points[points.length - 1];
  ctx.fillStyle = cssVar("--muted");
  ctx.font = "11px Segoe UI";
  ctx.textAlign = "left";
  ctx.fillText(formatShortDate(rangeStart), pad.left, height - 10);
  ctx.textAlign = "right";
  ctx.fillText(formatShortDate(rangeEnd), width - pad.right, height - 10);
  ctx.fillText(`Latest AQI ${formatNumber(latestPoint.value, 0)}`, width - pad.right, pad.top + 8);
  ctx.textAlign = "left";
}

function drawTrendChart(history) {
  const canvas = els.riskTrendChart;
  if (!canvas) return;

  const { ctx, width, height } = setupCanvas(canvas);
  const pad = { top: 34, right: 18, bottom: 20, left: 18 };
  const records = history
    .slice(0, 8)
    .reverse()
    .map((item) => ({
      time: item.prediction_time || item.sensor_timestamp,
      value: toNumber(item.risk_score),
      riskClass: item.risk_class || "Unknown",
      riskStyle: riskClassName(item.risk_class),
      anomaly: item.anomaly_flag,
    }))
    .filter((item) => item.value !== null);

  ctx.clearRect(0, 0, width, height);

  if (!records.length) {
    ctx.fillStyle = cssVar("--muted");
    ctx.font = "13px Segoe UI";
    ctx.textAlign = "left";
    ctx.fillText("Waiting for prediction history", pad.left + 10, height / 2);
    return;
  }

  const riskColors = {
    safe: cssVar("--safe"),
    moderate: cssVar("--moderate"),
    caution: cssVar("--caution"),
    dangerous: cssVar("--dangerous"),
    neutral: cssVar("--purple"),
  };
  const rowGap = 10;
  const rowHeight = Math.min(30, (height - pad.top - pad.bottom - rowGap * (records.length - 1)) / records.length);
  const timeWidth = 58;
  const riskWidth = 92;
  const scoreTextWidth = 48;
  const barX = pad.left + timeWidth + riskWidth + 24;
  const barWidth = Math.max(80, width - barX - scoreTextWidth - pad.right);

  ctx.textBaseline = "middle";
  ctx.textAlign = "left";
  ctx.font = "700 11px Segoe UI";
  ctx.fillStyle = cssVar("--muted");
  ctx.fillText("Time", pad.left, 16);
  ctx.fillText("Prediction", pad.left + timeWidth + 12, 16);
  ctx.fillText("Risk score", barX, 16);

  records.forEach((record, index) => {
    const y = pad.top + index * (rowHeight + rowGap);
    const scorePercent = Math.max(0, Math.min(100, record.value * 100));
    const riskColor = riskColors[record.riskStyle] || riskColors.neutral;
    const riskLabel = record.riskClass || "Unknown";

    ctx.fillStyle = "#fbfafc";
    ctx.beginPath();
    roundedRectPath(ctx, pad.left, y, width - pad.left - pad.right, rowHeight, 8);
    ctx.fill();

    ctx.fillStyle = cssVar("--text");
    ctx.font = "700 12px Segoe UI";
    ctx.fillText(formatTime(record.time), pad.left + 10, y + rowHeight / 2);

    ctx.fillStyle = riskColor;
    ctx.beginPath();
    roundedRectPath(ctx, pad.left + timeWidth + 12, y + 5, riskWidth, rowHeight - 10, 999);
    ctx.fill();

    ctx.fillStyle = "#ffffff";
    ctx.font = "700 11px Segoe UI";
    ctx.textAlign = "center";
    ctx.fillText(riskLabel, pad.left + timeWidth + 12 + riskWidth / 2, y + rowHeight / 2);
    ctx.textAlign = "left";

    ctx.fillStyle = "#ebe8f1";
    ctx.beginPath();
    roundedRectPath(ctx, barX, y + 8, barWidth, rowHeight - 16, 999);
    ctx.fill();

    ctx.fillStyle = riskColor;
    ctx.beginPath();
    roundedRectPath(ctx, barX, y + 8, Math.max(8, (barWidth * scorePercent) / 100), rowHeight - 16, 999);
    ctx.fill();

    ctx.fillStyle = cssVar("--text");
    ctx.font = "700 12px Segoe UI";
    ctx.fillText(`${formatNumber(scorePercent, 0)}%`, barX + barWidth + 12, y + rowHeight / 2);

    if (record.anomaly) {
      ctx.fillStyle = cssVar("--dangerous");
      ctx.font = "700 11px Segoe UI";
      ctx.fillText("Anomaly", Math.max(barX, width - pad.right - 66), y + rowHeight / 2);
    }
  });
}

function render(data) {
  const { latest, history, alerts = [] } = data;
  if (!latest) return;

  lastRenderedData = data;
  updateRisk(latest);
  updateSensorValues(latest.sensor);
  updateSummary(latest);
  updateHistory(history);
  updateAlertIndicators(latest, alerts);
  renderAlertList(latest, alerts);
  drawAqiTrendChart([latest, ...history]);
  drawTrendChart(history);

  setText("lastUpdated", `Last update: ${formatDateTime(new Date())}`);
  initIcons();
}

function setAlertsModalOpen(open) {
  if (!els.alertsModal) return;
  if (lastRenderedData?.latest) {
    renderAlertList(lastRenderedData.latest, lastRenderedData.alerts || []);
  }
  els.alertsModal.hidden = !open;
  els.alertsModal.toggleAttribute("hidden", !open);
  if (open) {
    refresh({ forceAlerts: true });
    els.alertsModalClose?.focus();
  }
}

function initAlerts() {
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest?.("#alertsNavLink, #notificationButton");
    if (!trigger) return;
    event.preventDefault();
    setAlertsModalOpen(true);
  });
  els.alertsModalClose?.addEventListener("click", () => setAlertsModalOpen(false));
  els.alertsModal?.addEventListener("click", (event) => {
    if (event.target === els.alertsModal) setAlertsModalOpen(false);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setAlertsModalOpen(false);
  });
}

function chatElements() {
  return {
    toggle: byId("chatToggle"),
    panel: byId("chatPanel"),
    close: byId("chatClose"),
    form: byId("chatForm"),
    input: byId("chatInput"),
    messages: byId("chatMessages"),
    submit: document.querySelector("#chatForm button"),
  };
}

function setChatOpen(open) {
  const chat = chatElements();
  if (!chat.panel || !chat.toggle) return;

  chat.panel.hidden = !open;
  chat.toggle.setAttribute("aria-expanded", open ? "true" : "false");
  chat.toggle.setAttribute("aria-label", open ? "Close OmiGuard assistant" : "Open OmiGuard assistant");

  if (open && chat.input) {
    chat.input.focus();
  }
}

function addChatMessage(role, text) {
  const chat = chatElements();
  if (!chat.messages) return null;

  const message = document.createElement("div");
  message.className = `chat-message ${role}`;
  message.textContent = text;
  chat.messages.appendChild(message);
  chat.messages.scrollTop = chat.messages.scrollHeight;
  return message;
}

function setChatBusy(isBusy) {
  const chat = chatElements();
  if (chat.input) chat.input.disabled = isBusy;
  if (chat.submit) chat.submit.disabled = isBusy;
}

function buildChatContext() {
  const latest = lastRenderedData?.latest;
  if (!latest) return {};

  return {
    device_id: latest.device_id,
    prediction_time: latest.prediction_time,
    sensor_timestamp: latest.sensor_timestamp,
    risk_class: latest.risk_class,
    risk_score: latest.risk_score,
    anomaly_flag: latest.anomaly_flag,
    action_recommendation: latest.action_recommendation,
    llm_recommendation: latest.raw?.llm_recommendation ?? latest.raw?.prediction?.llm_recommendation,
    prediction: {
      risk_class: latest.risk_class,
      risk_score: latest.risk_score,
      anomaly_flag: latest.anomaly_flag,
      action_recommendation: latest.action_recommendation,
      llm_action_recommendation:
        latest.raw?.llm_action_recommendation ?? latest.raw?.prediction?.llm_action_recommendation,
      llm_recommendation: latest.raw?.llm_recommendation ?? latest.raw?.prediction?.llm_recommendation,
    },
    sensor: {
      co: latest.sensor?.co,
      so2: latest.sensor?.so2,
      no2: latest.sensor?.no2,
      pm1_0: latest.sensor?.pm1_0,
      pm2_5: latest.sensor?.pm2_5,
      pm10: latest.sensor?.pm10,
      temperature: latest.sensor?.temperature,
      humidity: latest.sensor?.humidity,
      aqi: latest.sensor?.aqi,
      aqi_category: latest.sensor?.aqi_category,
      who_dominant_pollutant: latest.sensor?.dominant_risk_factor ?? latest.dominant,
      child_exposure_score: latest.sensor?.child_exposure_score,
      total_gas_load: latest.sensor?.total_gas_load,
      total_pm_load: latest.sensor?.total_pm_load,
      high_humidity_flag: latest.sensor?.high_humidity_flag,
      rule_based_risk_class: latest.sensor?.rule_based_risk_class,
    },
  };
}

async function sendChatMessage(text) {
  addChatMessage("user", text);
  const status = addChatMessage("status", "Assistant is checking the live context...");
  setChatBusy(true);

  try {
    const response = await fetch(CHAT_API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: text,
        context: buildChatContext(),
      }),
    });

    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Chat request failed");
    }

    if (status) status.remove();
    addChatMessage("assistant", data.reply || "I could not generate a reply.");
  } catch (error) {
    if (status) status.remove();
    addChatMessage("assistant", `Chat service unavailable: ${error.message}`);
  } finally {
    setChatBusy(false);
    const chat = chatElements();
    if (chat.input) chat.input.focus();
  }
}

function initChat() {
  const chat = chatElements();
  if (!chat.toggle || !chat.panel || !chat.form || !chat.input) return;

  chat.toggle.addEventListener("click", () => {
    setChatOpen(chat.panel.hidden);
  });

  if (chat.close) {
    chat.close.addEventListener("click", () => setChatOpen(false));
  }

  chat.form.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = chat.input.value.trim();
    if (!text) return;
    chat.input.value = "";
    sendChatMessage(text);
  });
}

async function refresh(options = {}) {
  try {
    setConnection("moderate", "Refreshing");
    const data = await loadData(options);
    render(data);
    setConnection("safe", "Live");
  } catch (error) {
    console.error(error);
    setConnection("dangerous", "Offline");
    setText("lastUpdated", `Last error: ${error.message}`);
    if (!lastRenderedData) {
      drawAqiTrendChart([]);
      drawTrendChart([]);
    }
  }
}

window.addEventListener("resize", () => {
  if (lastRenderedData) render(lastRenderedData);
});

cacheElements();
initSidebarNavigation();
initIcons();
initDashboardSearch();
initAlerts();
initChat();
refresh({ forceHistory: true, forceAlerts: true });
setInterval(refresh, REFRESH_MS);
