// backend-lite 管理页逻辑。原生 JS，无构建。
const $ = (id) => document.getElementById(id);
const API = "/api/admin";
let selectedModes = new Set();

function flash(el, msg, ok=true){
  if(!el) return;
  el.textContent = msg;
  el.classList.remove("is-ok", "is-error", "ok", "err");
  el.classList.add(ok ? "is-ok" : "is-error");
  setTimeout(()=>{ el.textContent=""; el.classList.remove("is-ok", "is-error"); }, 2500);
}

function escapeHtml(value){
  return String(value ?? "").replace(/[&<>\"']/g, (char) => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", "\"":"&quot;", "'":"&#39;"
  }[char]));
}

function stateValue(value, fallback="—"){
  const text = value === undefined || value === null || value === "" ? fallback : value;
  return escapeHtml(text);
}

async function jget(url){
  const r = await fetch(url);
  if(!r.ok) throw new Error(`${url} ${r.status}`);
  return r.json();
}
async function jpost(url, body, method="POST"){
  const r = await fetch(url, {method, headers:{"Content-Type":"application/json"}, body: JSON.stringify(body||{})});
  return r;
}

async function loadStatus(){
  try{
    const s = await jget(`${API}/state`);
    const st = s.state || {};
    const status = $("status");
    const deviceState = $("device-state");

    if(!s.mac){
      status.innerHTML = `<div class="status-empty">尚无设备连接过，等待设备首次心跳。</div>`;
      if(deviceState){
        deviceState.innerHTML = `<div class="device-state-empty">设备尚未上报状态。</div>`;
      }
      return;
    }

    const online = !!s.online;
    const onlineText = online ? "在线" : "离线";
    const statusTitle = online ? "InkSight 设备在线" : "最近连接过的设备";
    const mode = st.last_persona || "未记录";
    const runtime = st.runtime_mode || "interval";
    const pendingMode = st.pending_mode || "无";
    const refreshedAt = st.last_refresh_at || "未记录";

    status.innerHTML = `
      <div class="status-main">
        <span class="status-badge ${online ? "is-online" : "is-offline"}">${onlineText}</span>
        <span class="status-title">${statusTitle}</span>
        <span class="status-mac">${stateValue(s.mac)}</span>
      </div>
      <div class="status-facts">
        <span>运行 <strong>${stateValue(runtime)}</strong></span>
        <span>当前模式 <strong>${stateValue(mode)}</strong></span>
        <span>待刷新 <strong>${stateValue(st.pending_refresh || 0)}</strong></span>
        <span>待切换 <strong>${stateValue(pendingMode)}</strong></span>
      </div>`;

    if(deviceState){
      deviceState.innerHTML = `
        <div class="device-state-grid">
          <div class="state-item">
            <span class="state-label">设备 MAC</span>
            <span class="state-value mono">${stateValue(s.mac)}</span>
          </div>
          <div class="state-item">
            <span class="state-label">连接状态</span>
            <span class="state-value ${online ? "ok" : "err"}">${onlineText}</span>
          </div>
          <div class="state-item">
            <span class="state-label">运行模式</span>
            <span class="state-value">${stateValue(runtime)}</span>
          </div>
          <div class="state-item">
            <span class="state-label">当前内容</span>
            <span class="state-value">${stateValue(mode)}</span>
          </div>
          <div class="state-item">
            <span class="state-label">待刷新 / 待切换</span>
            <span class="state-value">${stateValue(st.pending_refresh || 0)} / ${stateValue(pendingMode)}</span>
          </div>
          <div class="state-item">
            <span class="state-label">最近刷新</span>
            <span class="state-value">${stateValue(refreshedAt)}</span>
          </div>
        </div>`;
    }
  }catch(e){
    $("status").innerHTML = `<div class="status-empty">状态读取失败：${escapeHtml(e.message)}</div>`;
    const deviceState = $("device-state");
    if(deviceState){
      deviceState.innerHTML = `<div class="device-state-empty">暂时无法读取设备状态。</div>`;
    }
  }
}

async function loadModes(){
  const data = await jget(`${API}/modes`);
  const chips = $("modes");
  chips.innerHTML = "";
  for(const m of data.modes){
    const c = document.createElement("div");
    c.className = "chip";
    c.textContent = m.display_name || m.mode_id;
    c.dataset.id = m.mode_id;
    c.onclick = ()=>{ c.classList.toggle("on"); selectedModes.has(m.mode_id)?selectedModes.delete(m.mode_id):selectedModes.add(m.mode_id); };
    chips.appendChild(c);
  }
  // 同时填预览下拉
  const sel = $("prev-mode");
  sel.innerHTML = "";
  for(const m of data.modes){ const o=document.createElement("option"); o.value=m.mode_id; o.textContent=m.display_name||m.mode_id; sel.appendChild(o); }
}

async function loadConfig(){
  const cfg = await jget(`${API}/config`);
  selectedModes = new Set(cfg.modes||[]);
  document.querySelectorAll("#modes .chip").forEach(c=>{ if(selectedModes.has(c.dataset.id)) c.classList.add("on"); });
  $("cfg-strategy").value = cfg.refresh_strategy||"random";
  $("cfg-interval").value = cfg.refresh_interval||60;
  $("cfg-city").value = cfg.city||"";
  $("cfg-language").value = cfg.language||"zh";
  $("cfg-tone").value = cfg.content_tone||"neutral";
  $("cfg-memo").value = cfg.memo_text||"";
  $("cfg-focus").checked = !!cfg.focus_listening;
  $("cfg-active").checked = !!cfg.always_active;
  const llmModel = $("llm-model");
  if(llmModel) llmModel.value = cfg.llm_model || "";
}

async function saveConfig(){
  const patch = {
    modes: [...selectedModes],
    refresh_strategy: $("cfg-strategy").value,
    refresh_interval: parseInt($("cfg-interval").value||60),
    city: $("cfg-city").value,
    language: $("cfg-language").value,
    content_tone: $("cfg-tone").value,
    memo_text: $("cfg-memo").value,
    focus_listening: $("cfg-focus").checked?1:0,
    always_active: $("cfg-active").checked?1:0,
  };
  const r = await jpost(`${API}/config`, patch, "PUT");
  flash($("cfg-status"), r.ok?"已保存":"失败", r.ok);
}

async function loadKey(){
  const k = await jget(`${API}/llm-key`);
  $("llm-provider").value = k.provider||"deepseek";
  $("llm-baseurl").value = k.base_url||"";
  const llmModel = $("llm-model");
  if(llmModel) llmModel.value = k.model || "";
  $("llm-key").placeholder = k.has_api_key ? "（已保存，留空保留）" : "";
  $("llm-imgkey").placeholder = k.has_image_api_key ? "（已保存，留空保留）" : "";
}

async function saveKey(){
  const provider = $("llm-provider").value;
  const baseUrl = $("llm-baseurl").value.trim();
  const model = $("llm-model")?.value.trim() || "";

  if(provider === "openai_compat"){
    if(!baseUrl){
      flash($("key-status"), "openai_compat 需要填写 Base URL", false);
      return;
    }
    if(!model){
      flash($("key-status"), "openai_compat 需要填写模型名", false);
      return;
    }
  }

  const patch = { provider, base_url: baseUrl, model };
  if($("llm-key").value) patch.api_key = $("llm-key").value;
  if($("llm-imgkey").value) patch.image_api_key = $("llm-imgkey").value;

  const r = await jpost(`${API}/llm-key`, patch, "PUT");
  flash($("key-status"), r.ok ? "已保存" : "保存失败", r.ok);
  if(r.ok){
    $("llm-key").value = "";
    $("llm-imgkey").value = "";
    loadKey();
    loadConfig();
  }
}

async function doPreview(){
  $("preview").src = `/api/preview?mode=${encodeURIComponent($("prev-mode").value)}&as_png=1&_=${Date.now()}`;
}

async function doRefresh(){
  const r = await jpost(`${API}/refresh`, {});
  flash($("op-status"), r.ok?"已触发":"失败", r.ok);
  setTimeout(loadStatus, 500);
}
async function exitActive(){
  const r = await jpost(`${API}/runtime`, {mode:"interval"});
  flash($("op-status"), r.ok?"已退出活跃":"失败", r.ok);
  setTimeout(loadStatus, 500);
}

async function loadAlert(){
  try{
    const a = await jget(`${API}/alert`);
    $("alert-active").checked = !!a.active;
    $("alert-text").value = a.text || "";
  }catch(e){}
}
async function saveAlert(){
  const r = await jpost(`${API}/alert`, {active:$("alert-active").checked, text:$("alert-text").value}, "PUT");
  flash($("alert-status"), r.ok?"已保存":"失败", r.ok);
}

async function otaSet(){
  const fileInput = $("ota-file");
  if(fileInput.files.length){
    const fd = new FormData();
    fd.append("file", fileInput.files[0]);
    const r = await fetch(`${API}/ota/upload`, {method:"POST", body:fd});
    const data = await r.json().catch(()=>({}));
    flash($("ota-status"), r.ok?`已下发: ${data.url||''}`:`失败 ${r.status}`, r.ok);
    return;
  }
  const url = $("ota-url").value.trim();
  if(!url){ flash($("ota-status"),"请选择文件或填 URL",false); return; }
  const r = await jpost(`${API}/ota/set`, {ota_url:url, ota_version:$("ota-version").value||""});
  flash($("ota-status"), r.ok?"已下发":"失败", r.ok);
}

(async function init(){
  await loadModes();
  await Promise.all([loadConfig(), loadKey(), loadAlert(), loadStatus()]);
  doPreview();
  setInterval(loadStatus, 10000);
})();