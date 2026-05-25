const $ = (id) => document.getElementById(id);

const I18N = {
  zh: {
    pageTitle: "InkSight 控制台",
    eyebrow: "InkSight Console",
    title: "后端运营看板",
    subtitle: "汇总 InkSight 的用户增长、设备活跃、渲染质量、内容创作与访问埋点。",
    username: "用户名",
    password: "密码",
    signIn: "登录",
    signOut: "退出",
    statusIdle: "请使用 root 账号登录以加载受保护的指标。设备 API 仍可通过 /api/* 访问。",
    statusLoading: "正在加载指标...",
    statusNeedLogin: "请使用 root 账号登录以加载指标。",
    statusNotRoot: "当前账号不是 root。",
    statusLoaded: "Root 会话已在此后端域名生效，已于 {time} 加载。",
    statusLoginRequired: "用户名和密码不能为空。",
    statusSigningIn: "正在登录...",
    statusSignInFailed: "登录失败：{message}",
    statusSignedOut: "已在此后端域名退出登录。",
    statusLoadFailed: "加载看板指标失败：{message}",
    metricUsers: "用户",
    metricDau: "日活",
    metricLoginUsers: "今日登录用户",
    metricActiveDevices: "今日活跃设备",
    metricRenders: "今日渲染",
    metricHeartbeats: "设备心跳",
    metricRenderHealth: "今日渲染健康",
    metricContent: "内容创作",
    metricDeviceUsers: "今日活跃设备用户",
    metricNewUsers: "14 日新增用户",
    metricRendersSeries: "14 日渲染量",
    metricActiveDeviceSeries: "14 日活跃设备",
    metricActivitySeries: "14 日用户活跃",
    metricTopModes: "7 日热门模式",
    metricTopEvents: "7 日用户事件",
    metricEventSummary: "用户事件总览",
    metricHistoricalVisits: "历史访问量",
    metricHistoricalVisitors: "历史访客数",
    metricEventsToday: "今日用户事件",
    metricEvents7d: "7 日用户事件",
    metricEventsTotal: "历史用户事件",
    trackingDataTitle: "埋点数据 · 统计自 2026-05-25",
    metricNotes: "统计口径",
    notesBody: "注册数来自 users；DAU/WAU/MAU 来自 user_activity_events；设备活跃来自心跳和渲染日志；渲染量、错误与 fallback 来自 render_logs。历史访问量和历史访客数含一次性 Nginx 粗估基线，后续增长以 page.view 埋点为准。",
    noData: "暂无数据",
    usersNote: "今日 +{today} / 7日 +{week} / 30日 +{month}",
    activeNote: "WAU {wau} / MAU {mau}",
    loginUsersNote: "DAU {dau} / WAU {wau} / MAU {mau}",
    devicesNote: "已绑定 {bound} / 7日活跃 {week}",
    rendersNote: "7日 {week} / 今日平均耗时 {avg}ms",
    heartbeatsNote: "今日设备心跳请求",
    renderHealthNote: "今日错误 {errors} / fallback 占比 {rate}",
    contentNote: "共享 {shared} / BYOK {byok}",
    deviceUsersNote: "已绑定用户 {withDevice} / 设备反推 24h 活跃",
    historicalVisitsNote: "统计自 {start}；后续使用埋点",
    historicalVisitorsNote: "IP+UA 去重；统计自 {start}",
    eventRows: "事件记录",
    colMode: "模式",
    colEvent: "事件",
    colRenders: "渲染次数",
    colCount: "次数",
    colEvents: "事件数",
    colPeriod: "周期",
    colPageviews: "访问量",
    colVisitors: "访客数",
    colLogins: "登录",
    periodToday: "今日",
    period7d: "7 日",
    periodTotal: "历史",
  },
  en: {
    pageTitle: "InkSight Console",
    eyebrow: "InkSight Console",
    title: "Backend pulse.",
    subtitle: "A daily operations view for InkSight user growth, device activity, render health, content creation, and tracking data.",
    username: "Username",
    password: "Password",
    signIn: "Sign in",
    signOut: "Sign out",
    statusIdle: "Sign in with a root account to load protected metrics. Device APIs remain available under /api/*.",
    statusLoading: "Loading metrics...",
    statusNeedLogin: "Sign in with a root account to load metrics.",
    statusNotRoot: "Current account is not root.",
    statusLoaded: "Root session is active on this backend domain. Loaded at {time}.",
    statusLoginRequired: "Username and password are required.",
    statusSigningIn: "Signing in...",
    statusSignInFailed: "Sign-in failed: {message}",
    statusSignedOut: "Signed out on this backend domain.",
    statusLoadFailed: "Failed to load console metrics: {message}",
    metricUsers: "Users",
    metricDau: "DAU",
    metricLoginUsers: "Login Users Today",
    metricActiveDevices: "Active Devices Today",
    metricRenders: "Renders Today",
    metricHeartbeats: "Heartbeats",
    metricRenderHealth: "Render Health Today",
    metricContent: "Content",
    metricDeviceUsers: "Active Device Users Today",
    metricNewUsers: "New Users 14d",
    metricRendersSeries: "Renders 14d",
    metricActiveDeviceSeries: "Active Devices 14d",
    metricActivitySeries: "User Activity 14d",
    metricTopModes: "Top Modes 7d",
    metricTopEvents: "User Events 7d",
    metricEventSummary: "Event Summary",
    metricHistoricalVisits: "Historical Visits",
    metricHistoricalVisitors: "Historical Visitors",
    metricEventsToday: "Events Today",
    metricEvents7d: "User Events 7d",
    metricEventsTotal: "Historical Events",
    trackingDataTitle: "Tracking Data · Since 2026-05-25",
    metricNotes: "Notes",
    notesBody: "Users come from users; DAU/WAU/MAU come from user_activity_events; device activity comes from heartbeats and render logs; renders, errors, and fallback counts come from render_logs. Historical visits and visitors include one-time Nginx estimate baselines; future growth uses page.view events.",
    noData: "No data yet.",
    usersNote: "+{today} today / +{week} 7d / +{month} 30d",
    activeNote: "WAU {wau} / MAU {mau}",
    loginUsersNote: "DAU {dau} / WAU {wau} / MAU {mau}",
    devicesNote: "{bound} bound / {week} active 7d",
    rendersNote: "{week} 7d / {avg}ms avg today",
    heartbeatsNote: "device heartbeats today",
    renderHealthNote: "{errors} errors today / {rate} fallback",
    contentNote: "{shared} shared / {byok} BYOK",
    deviceUsersNote: "{withDevice} bound users / device-derived 24h active",
    historicalVisitsNote: "since {start}; tracked going forward",
    historicalVisitorsNote: "distinct IP+UA since {start}",
    eventRows: "event rows",
    colMode: "Mode",
    colEvent: "Event",
    colRenders: "Renders",
    colCount: "Count",
    colEvents: "Events",
    colPeriod: "Period",
    colPageviews: "Views",
    colVisitors: "Visitors",
    colLogins: "Logins",
    periodToday: "Today",
    period7d: "7d",
    periodTotal: "All time",
  },
};

let lang = localStorage.getItem("inksight_console_lang") || "";
if (!I18N[lang]) {
  lang = (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}

let lastData = null;

function t(key, vars = {}) {
  let text = (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
  Object.entries(vars).forEach(([name, value]) => {
    text = text.replaceAll(`{${name}}`, String(value));
  });
  return text;
}

function fmt(n) {
  if (n === null || n === undefined) return "--";
  return Number(n || 0).toLocaleString(lang === "zh" ? "zh-CN" : "en-US");
}

function pct(numerator, denominator) {
  const den = Number(denominator || 0);
  if (!den) return "0%";
  return `${((Number(numerator || 0) / den) * 100).toFixed(1)}%`;
}

function setStatus(text, isError = false) {
  const el = $("status");
  el.textContent = text;
  el.className = isError ? "status error" : "status";
}

function applyLang() {
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });
  $("langZh").classList.toggle("active", lang === "zh");
  $("langEn").classList.toggle("active", lang === "en");
}

function setLang(next) {
  if (!I18N[next] || next === lang) return;
  lang = next;
  localStorage.setItem("inksight_console_lang", lang);
  applyLang();
  if (lastData) render(lastData);
  else setStatus(t("statusIdle"));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    "\"": "&quot;",
    "'": "&#39;",
  })[char]);
}

function renderTable(rows, columns) {
  if (!rows || rows.length === 0) return `<p class="empty">${t("noData")}</p>`;
  const head = columns.map((c) => `<th>${escapeHtml(c.label)}</th>`).join("");
  const body = rows.map((row) => (
    `<tr>${columns.map((c) => `<td>${escapeHtml(row[c.key] || "")}</td>`).join("")}</tr>`
  )).join("");
  return `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderBars(id, rows, key = "count") {
  if (!rows || rows.length === 0) {
    $(id).innerHTML = `<p class="empty">${t("noData")}</p>`;
    return;
  }
  const ordered = [...rows].reverse();
  const max = Math.max(...ordered.map((d) => Number(d[key] || 0)), 1);
  $(id).innerHTML = ordered.map((d) => {
    const value = Number(d[key] || 0);
    const height = Math.max(8, Math.round((value / max) * 116));
    const day = String(d.day || "");
    return `<div class="bar" title="${escapeHtml(`${day}: ${value}`)}" style="height:${height}px"><b>${escapeHtml(fmt(value))}</b><span>${escapeHtml(day.slice(5))}</span></div>`;
  }).join("");
}

function eventRows(rows, fallbackTotal) {
  if (Array.isArray(rows)) return rows;
  if (fallbackTotal === null || fallbackTotal === undefined) return [];
  return [{ event_name: "all", count: fallbackTotal }];
}

function renderSummaryTable(rows) {
  const columns = [
    { key: "period", label: t("colPeriod") },
    { key: "pageviews", label: t("colPageviews") },
    { key: "visitors", label: t("colVisitors") },
    { key: "logins", label: t("colLogins") },
    { key: "events", label: t("colEvents") },
  ];
  return renderTable(rows, columns);
}

function render(data) {
  lastData = data;
  $("usersTotal").textContent = fmt(data.users.total);
  $("usersNote").textContent = t("usersNote", {
    today: fmt(data.users.today_new),
    week: fmt(data.users.new_7d),
    month: fmt(data.users.new_30d),
  });
  $("deviceUsers").textContent = fmt(data.users.device_active_24h);
  $("deviceUsersNote").textContent = t("deviceUsersNote", {
    withDevice: fmt(data.users.with_device),
  });
  $("devicesActive").textContent = fmt(data.devices.active_today);
  $("devicesNote").textContent = t("devicesNote", {
    bound: fmt(data.devices.bound),
    week: fmt(data.devices.active_7d),
  });
  $("rendersToday").textContent = fmt(data.rendering.today);
  $("rendersNote").textContent = t("rendersNote", {
    week: fmt(data.rendering.last_7d),
    avg: fmt(data.rendering.avg_ms_today),
  });
  $("heartbeatsToday").textContent = fmt(data.devices.heartbeats_today);
  $("heartbeatsNote").textContent = t("heartbeatsNote");
  $("renderErrors").innerHTML = `${fmt(data.rendering.fallback_today)} <span class="metric-unit">fallback</span>`;
  $("renderHealthNote").textContent = t("renderHealthNote", {
    errors: fmt(data.rendering.errors_today),
    rate: pct(data.rendering.fallback_today, data.rendering.today),
  });
  $("customModes").textContent = fmt(data.content.custom_modes);
  $("contentNote").textContent = t("contentNote", {
    shared: fmt(data.content.shared_modes),
    byok: fmt(data.content.users_with_llm_config),
  });
  $("loginUsersToday").textContent = fmt(data.users.login_users_today);
  $("loginUsersNote").textContent = t("loginUsersNote", {
    dau: fmt(data.users.dau),
    wau: fmt(data.users.wau),
    mau: fmt(data.users.mau),
  });

  renderBars("userBars", data.series.new_users);
  renderBars("renderBars", data.series.renders);
  renderBars("deviceBars", data.series.active_devices);
  renderBars("activityBars", data.series.activity_events, "active_users");
  $("topModes").innerHTML = renderTable(data.top.modes, [
    { key: "mode", label: t("colMode") },
    { key: "count", label: t("colRenders") },
  ]);
  $("historicalVisits").textContent = fmt(data.traffic.historical_visits.total);
  $("historicalVisitsNote").textContent = t("historicalVisitsNote", {
    start: data.traffic.historical_visits.start_date,
  });
  $("historicalVisitors").textContent = fmt(data.traffic.historical_visitors.total);
  $("historicalVisitorsNote").textContent = t("historicalVisitorsNote", {
    start: data.traffic.historical_visitors.start_date,
  });
  $("eventSummaryTable").innerHTML = renderSummaryTable([
    {
      period: t("periodToday"),
      pageviews: fmt(data.activity.pageviews_today),
      visitors: fmt(data.activity.visitors_today),
      logins: fmt(data.activity.logins_today),
      events: fmt(data.activity.events_today),
    },
    {
      period: t("period7d"),
      pageviews: fmt(data.activity.pageviews_7d),
      visitors: fmt(data.activity.visitors_7d),
      logins: fmt(data.activity.logins_7d),
      events: fmt(data.activity.events_7d),
    },
    {
      period: t("periodTotal"),
      pageviews: fmt(data.activity.pageviews_total),
      visitors: fmt(data.activity.visitors_total),
      logins: fmt(data.activity.logins_total),
      events: fmt(data.activity.events_total),
    },
  ]);
  setStatus(t("statusLoaded", { time: new Date().toLocaleString(lang === "zh" ? "zh-CN" : "en-US") }));
}

async function loadConsole() {
  setStatus(t("statusLoading"));
  try {
    const res = await fetch("/api/admin/console/summary", { cache: "no-store", credentials: "same-origin" });
    if (res.status === 401) {
      setStatus(t("statusNeedLogin"));
      return;
    }
    if (res.status === 403) throw new Error(t("statusNotRoot"));
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    render(await res.json());
  } catch (err) {
    setStatus(t("statusLoadFailed", { message: err.message }), true);
  }
}

async function login(event) {
  event.preventDefault();
  const username = $("username").value.trim();
  const password = $("password").value;
  if (!username || !password) {
    setStatus(t("statusLoginRequired"), true);
    return;
  }
  setStatus(t("statusSigningIn"));
  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      credentials: "same-origin",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    $("password").value = "";
    await loadConsole();
  } catch (err) {
    setStatus(t("statusSignInFailed", { message: err.message }), true);
  }
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => {});
  lastData = null;
  setStatus(t("statusSignedOut"));
}

function trackPageview() {
  fetch("/api/analytics/pageview", {
    method: "POST",
    credentials: "same-origin",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ path: location.pathname, source: "backend_console" }),
    keepalive: true,
  }).catch(() => {});
}

$("loginForm").addEventListener("submit", login);
$("logout").addEventListener("click", logout);
$("langZh").addEventListener("click", () => setLang("zh"));
$("langEn").addEventListener("click", () => setLang("en"));
applyLang();
trackPageview();
loadConsole();
