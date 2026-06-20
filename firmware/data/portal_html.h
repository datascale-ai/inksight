#ifndef PORTAL_HTML_H
#define PORTAL_HTML_H

const char PORTAL_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=yes">
<title>InkSight 配网</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bk:#1a1a1a;--gy:#888;--bg:#fafaf7;--bd:#d4d4cf;--f:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--fs:'Georgia',serif}
html{font-size:16px;-webkit-font-smoothing:antialiased;overflow-y:scroll}
body{font-family:var(--f);background:linear-gradient(135deg,#f5f5f0,#e8e8e0);color:var(--bk);line-height:1.6;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px}
.card{background:#fff;border-radius:20px;box-shadow:0 8px 40px rgba(0,0,0,.08);width:100%;max-width:380px;padding:32px 24px}
.hdr{text-align:center;margin-bottom:24px}
.logo{width:50px;height:50px;background:var(--bk);border-radius:14px;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;color:#fff;font-family:var(--fs);font-size:1.5rem;font-weight:700}
.hdr h1{font-family:var(--fs);font-size:1.4rem;font-weight:700;margin-bottom:2px}
.hdr p{font-size:.82rem;color:var(--gy)}
.steps{display:flex;align-items:center;justify-content:center;margin-bottom:20px}
.dot{width:26px;height:26px;border-radius:50%;border:2px solid var(--bd);display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:600;color:var(--gy);background:#fff;flex-shrink:0}
.dot.a{border-color:var(--bk);background:var(--bk);color:#fff}
.dot.d{border-color:#22c55e;background:#22c55e;color:#fff}
.ln{width:48px;height:2px;background:var(--bd)}
.ln.d{background:#22c55e}
.hidden{display:none!important}
.lbl{display:block;font-size:.78rem;font-weight:500;color:var(--gy);margin-bottom:5px}
.inp{width:100%;padding:10px 12px;font-family:var(--f);font-size:.85rem;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--bk);outline:none;-webkit-appearance:none}
.inp:focus{border-color:var(--bk)}
.fg{margin-bottom:12px}
.pw{position:relative}
.pw .inp{padding-right:40px}
.pw-btn{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:var(--gy);padding:4px}
.btn{display:block;width:100%;padding:12px;font-family:var(--f);font-size:.9rem;font-weight:600;color:#fff;background:var(--bk);border:none;border-radius:10px;cursor:pointer}
.btn:hover{background:#333}
.btn:disabled{opacity:.6;cursor:not-allowed}
.btn .sp{display:none;width:16px;height:16px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;margin:0 auto}
.btn.ld .bt{display:none}.btn.ld .sp{display:block}
.btn-ghost{color:var(--bk);background:#fff;border:1px solid var(--bd)}
.btn-ghost:hover,.btn-ghost:active{color:#fff;background:var(--bk);border-color:var(--bk)}
.btn-ghost.ld .sp{border-color:rgba(0,0,0,.25);border-top-color:var(--bk)}
.btn-ghost.ld:hover .sp,.btn-ghost.ld:active .sp{border-color:rgba(255,255,255,.3);border-top-color:#fff}
@keyframes spin{to{transform:rotate(360deg)}}
.wl{list-style:none;margin-bottom:10px}
.wi{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--bd);border-radius:8px;margin-bottom:6px;cursor:pointer;background:#fff}
.wi:hover{border-color:var(--bk);background:var(--bg)}
.wi.sel{border-color:var(--bk);background:var(--bg)}
.wn{font-size:.85rem;font-weight:500;display:flex;align-items:center;gap:6px}
.wa{display:flex;align-items:center;gap:6px;flex-shrink:0}
.wc{background:var(--bk);border:none;cursor:pointer;color:#fff;padding:5px 8px;border-radius:6px;font-size:.72rem;font-weight:600;line-height:1;flex-shrink:0}
.wc:hover{background:#333}
.wc:disabled,.wx:disabled{opacity:.6;cursor:not-allowed}
.wx{background:none;border:none;cursor:pointer;color:var(--gy);padding:4px 6px;border-radius:6px;font-size:1.1rem;line-height:1;flex-shrink:0}
.wx:hover{color:#dc2626;background:#fef2f2}
.si-ord{display:inline-flex;align-items:center;justify-content:center;width:18px;height:18px;border-radius:50%;background:var(--bg);border:1px solid var(--bd);font-size:.66rem;color:var(--gy);flex-shrink:0}
.ws{display:flex;align-items:flex-end;gap:1.5px;height:14px}
.ws .b{width:3px;background:#e0e0dc;border-radius:1px}
.ws .b.a{background:var(--bk)}
.wk{width:12px;height:12px;opacity:.4}
.wtabs{display:flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden;margin-bottom:12px}
.wtab{flex:1;padding:8px 4px;text-align:center;font-size:.78rem;font-weight:500;cursor:pointer;background:#fff;color:var(--gy);border-right:1px solid var(--bd);user-select:none}
.wtab:last-child{border-right:none}
.wtab:hover{background:var(--bg)}
.wtab.act{background:var(--bk);color:#fff}
.si{width:56px;height:56px;border-radius:50%;background:#22c55e;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;animation:sc .4s cubic-bezier(.175,.885,.32,1.275)}
@keyframes sc{0%{transform:scale(0)}100%{transform:scale(1)}}
.di{font-size:.75rem;color:var(--gy);line-height:2}
.di dt{display:inline;font-weight:600}
.di dd{display:inline;margin-left:4px;font-family:'SF Mono','Fira Code',monospace}
.st{margin-top:16px;padding:10px 14px;border-radius:8px;font-size:.78rem;font-weight:500;text-align:center}
.st.w{background:var(--bg);color:var(--gy)}
.st.s{background:#dcfce7;color:#15803d}
.st.e{background:#fef2f2;color:#dc2626}
.st.c{background:#fef9c3;color:#a16207}
.link-box{margin-top:16px;padding:14px;background:#dbeafe;border-radius:10px;font-size:.78rem;color:#1e40af;line-height:1.6;text-align:left}
.cd{font-family:'SF Mono','Fira Code',monospace;font-size:.82rem;color:var(--gy);margin-top:8px}
</style>
</head>
<body>
<div class="card">
<div style="position:absolute;top:16px;right:16px;">
<button id="langBtn" onclick="toggleLang()" style="background:none;border:1px solid var(--bd);border-radius:6px;padding:4px 8px;font-size:0.75rem;cursor:pointer;color:var(--gy)">EN</button>
</div>
<div class="hdr">
<div class="logo">墨</div>
<h1 id="logoText">InkSight <span style="font-weight:400;font-size:.85em">墨鱼</span></h1>
<p id="subtitle">WiFi 配网</p>
</div>

<div class="steps">
<div class="dot a" id="d1">1</div>
<div class="ln" id="l1"></div>
<div class="dot" id="d2"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
</div>

<!-- Step 1: WiFi + Server -->
<div id="s1">
<div id="savedWrap" class="hidden" style="margin-bottom:16px">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">
<span class="lbl" id="savedTitle" style="margin-bottom:0">已保存网络</span>
<span id="savedCount" style="font-size:.72rem;color:var(--gy)">0/5</span>
</div>
<ul class="wl" id="savedList" style="margin-bottom:0"></ul>
</div>
<div class="wtabs">
<div class="wtab" id="wtScan" onclick="switchWTab('scan')">选择网络</div>
<div class="wtab act" id="wtMan" onclick="switchWTab('manual')">手动输入</div>
</div>
<div id="wScan" class="hidden">
<div id="wScanLoading" style="text-align:center;padding:20px 0;color:var(--gy);font-size:.85rem">
<div class="sp" style="display:inline-block;width:16px;height:16px;border:2px solid rgba(0,0,0,.1);border-top-color:var(--bk);border-radius:50%;animation:spin .7s linear infinite;vertical-align:middle;margin-right:8px"></div>
<span id="scanText">正在扫描附近网络...</span>
</div>
<ul class="wl" id="wifiList" style="display:none"></ul>
<div id="wSel" class="hidden" style="display:none;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--bk);border-radius:8px;background:var(--bg);margin-bottom:10px">
<span id="wSelName" style="font-size:.85rem;font-weight:500"></span>
<a id="reselectBtn" onclick="reShowList()" style="font-size:.72rem;color:var(--gy);cursor:pointer">重新选择</a>
</div>
</div>
<div id="wMan">
<div class="fg">
<label class="lbl" id="lblSsid">WiFi 名称 (SSID)</label>
<input type="text" class="inp" id="ssidIn" placeholder="输入 SSID">
</div>
</div>
<div class="fg">
<label class="lbl" id="lblPw">WiFi 密码</label>
<div class="pw">
<input type="password" class="inp" id="pwIn" placeholder="输入密码">
<button class="pw-btn" onclick="togglePw()" type="button" id="tpb">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
</button>
</div>
</div>
<div class="fg">
<label class="lbl" id="srvTitle">服务器地址</label>
<div class="wtabs" style="margin-bottom:8px">
<div class="wtab act" id="srvOfficial" onclick="switchSrvMode('official')">官方服务</div>
<div class="wtab" id="srvCustom" onclick="switchSrvMode('custom')">自定义服务</div>
</div>
<div id="srvOfficialTip" style="font-size:.72rem;color:var(--gy)">将使用官方云服务生成内容</div>
<div id="srvCustomWrap" class="hidden">
<input type="text" class="inp" id="srvIn" value="http://本地服务IP:8080" placeholder="例如: http://192.168.1.100:8080">
<div id="srvCusTip1" style="font-size:.68rem;color:var(--gy);margin-top:3px">输入你自己部署的 InkSight 后端地址（含端口）</div>
<div style="margin-top:10px">
<input type="text" class="inp" id="frontendPortIn" value="3000" placeholder="例如: 3000">
<div id="srvCusTip2" style="font-size:.68rem;color:var(--gy);margin-top:3px">前端配置页端口，用于重启后跳转到 localhost:端口/config</div>
</div>
</div>
</div>
<button class="btn btn-ghost" id="cBtn" onclick="doConnect()"><span class="bt" id="btnConnText">连接并保存</span><div class="sp"></div></button>
<button class="btn" id="addBtn" onclick="doAddOnly()" style="margin-top:8px;background:var(--bg);color:var(--bk);border:1px solid var(--bd);font-size:.82rem;padding:10px"><span class="bt" id="btnAddText">仅保存到列表</span><div class="sp"></div></button>
<div id="addHint" style="font-size:.68rem;color:var(--gy);margin-top:5px;text-align:center">连不上的网络（如办公室/手机热点）可仅保存，开机会按顺序尝试</div>
</div>

<!-- Step 2: Success -->
<div id="s2" class="hidden" style="text-align:center;padding:16px 0">
<div class="si"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
<h3 id="s2Title" style="font-family:var(--fs);font-size:1.05rem;margin-bottom:4px">配网完成</h3>
<p style="font-size:.82rem;color:var(--gy)">已连接到 <strong id="cSSID"></strong></p>

<div class="link-box">
<strong id="s2Next">下一步：</strong><span id="s2Auto">设备将自动重启并联网，请使用配对码继续完成认领与配置。</span><br>
<div id="s2Warn" style="margin-top:8px;padding:8px 10px;background:#fef3c7;border-radius:6px;font-size:.75rem;color:#92400e;font-weight:500">⚠ 跳转前请先断开 InkSight 热点，重新连接您的家庭 / 办公 WiFi</div>
</div>

<div id="pairWrap" class="hidden" style="margin-top:12px;padding:12px;border:1px solid var(--bd);border-radius:8px;background:#f8fafc">
<div id="s2CodeLbl" style="font-size:.76rem;color:var(--gy)">配对码</div>
<div id="pairCode" style="margin-top:6px;font-size:1.3rem;letter-spacing:.18em;font-weight:700">--------</div>
</div>

<div style="margin-top:16px;display:flex;gap:8px;justify-content:center">
<button class="btn" onclick="doRestart()" id="btnRest" style="width:auto;padding:9px 20px;font-size:.82rem">立即重启</button>
<button class="btn" onclick="cancelCountdown()" id="cdCancelBtn" style="width:auto;padding:9px 16px;font-size:.8rem;background:var(--bg);color:var(--bk)">取消</button>
</div>
<p class="cd"><span id="cdN">10</span><span id="cdSuffix"> 秒后自动重启</span></p>
<div style="margin-top:10px"><button class="btn" onclick="resetP()" id="btnReSetup" style="background:var(--bg);color:var(--bk);font-size:.8rem;padding:9px">重新配网</button></div>
</div>

<hr style="border:none;border-top:1px dashed var(--bd);margin:20px 0">
<dl class="di">
<div style="margin-bottom:3px"><dt>MAC:</dt><dd id="devMAC">--</dd></div>
<div style="margin-bottom:3px"><dt id="lblFirmware">固件:</dt><dd>v1.0.0</dd></div>
<div style="margin-bottom:3px"><dt id="lblBat">电池:</dt><dd id="devBat">--</dd></div>
</dl>
<div class="st w" id="pSt">等待配网...</div>
</div>

<script>
var lang=localStorage.getItem('ink_lang')||'zh';
var i18n={
zh:{
title:"InkSight 配网",
logoText:"InkSight <span style=\"font-weight:400;font-size:.85em\">墨鱼</span>",
subtitle:"WiFi 配网",
tabScan:"选择网络",
tabMan:"手动输入",
scanning:"正在扫描附近网络...",
reselect:"重新选择",
ssidPh:"输入 SSID",
pwPh:"输入密码",
srvTitle:"服务器地址",
srvOff:"官方服务",
srvCus:"自定义服务",
srvOffTip:"将使用官方云服务生成内容",
srvCusTip1:"输入你自己部署的 InkSight 后端地址（含端口）",
srvCusTip2:"前端配置页端口，用于重启后跳转到 localhost:端口/config",
srvUrlPh:"例如: http://192.168.1.100:8080",
srvPortPh:"例如: 3000",
btnConn:"连接并保存",
btnAdd:"仅保存到列表",
btnSavedConn:"连接",
savedTitle:"已保存网络",
addHint:"连不上的网络（如办公室/手机热点）可仅保存，开机会按顺序尝试",
msgAddOk:"已保存到列表",
msgFull:"最多保存 5 个网络",
msgDelOk:"已删除",
msgSavedConnFail:"连接失败，密码可能已变更，请重新输入密码后连接并保存",
msgSavedNotFound:"未找到该已保存网络",
s2Title:"配网完成",
s2Next:"下一步：",
s2Auto:"设备将自动重启并联网，请使用配对码继续完成认领与配置。",
s2Warn:"⚠ 跳转前请先断开 InkSight 热点，重新连接您的家庭 / 办公 WiFi",
s2CodeLbl:"配对码",
btnRest:"立即重启",
btnCancel:"取消",
cdSuffix:" 秒后自动重启",
btnReSetup:"重新配网",
lblFirmware:"固件:",
lblBat:"电池:",
lblSsid:"WiFi 名称 (SSID)",
lblPw:"WiFi 密码",
stWait:"等待配网...",
errSsid:"请选择或输入 WiFi",
errPw:"请输入密码",
errPwLen:"密码至少 8 位",
errUrl:"服务器地址需以 http:// 或 https:// 开头",
errPort:"前端端口需为 2 到 5 位数字",
msgConn:"正在连接 ",
msgConnOk:"WiFi 已连接",
msgConnFail:"连接失败",
msgReqFail:"请求失败，请重试",
msgSetupOk:"配网完成！",
msgRest1:"设备重启中，即将跳转至配置页...",
msgRest2:"设备重启中，请稍后在配置页输入配对码...",
htmlRedir:"<h2>正在跳转至配置页</h2><p style=\"color:#888\">请确保已切换回家庭 WiFi</p>",
htmlRedirLink:"点击此处手动跳转",
htmlRestOk:"<h2>设备已重启</h2><p style=\"color:#888\">请切换回家庭 WiFi 后打开配置页，输入以下配对码继续认领设备。</p>",
htmlRestFail:"<h2>配对码生成失败</h2><p style=\"color:#888\">请稍后重试配网流程。</p>",
msgCancel:"自动重启已取消",
msgScanFail:"扫描失败，请刷新页面重试或手动输入"
},
en:{
title:"InkSight Setup",
logoText:"InkSight",
subtitle:"WiFi Setup",
tabScan:"Scan",
tabMan:"Manual",
scanning:"Scanning for networks...",
reselect:"Reselect",
ssidPh:"Enter SSID",
pwPh:"Enter Password",
srvTitle:"Server URL",
srvOff:"Official",
srvCus:"Custom",
srvOffTip:"Will use official cloud service",
srvCusTip1:"Enter your self-hosted backend URL (with port)",
srvCusTip2:"Frontend port, used for redirecting to localhost:port/config",
srvUrlPh:"e.g. http://192.168.1.100:8080",
srvPortPh:"e.g. 3000",
btnConn:"Connect & Save",
btnAdd:"Save to List",
btnSavedConn:"Connect",
savedTitle:"Saved Networks",
addHint:"Networks not reachable here (office / phone hotspot) can be saved only; tried in order on boot",
msgAddOk:"Saved to list",
msgFull:"Up to 5 networks allowed",
msgDelOk:"Removed",
msgSavedConnFail:"Connection failed. The password may have changed; enter it again and use Connect & Save.",
msgSavedNotFound:"Saved network not found",
s2Title:"Setup Complete",
s2Next:"Next Step: ",
s2Auto:"Device will restart and connect. Use the pairing code to bind.",
s2Warn:"⚠ Please disconnect from InkSight hotspot and reconnect to your home WiFi before redirecting.",
s2CodeLbl:"Pairing Code",
btnRest:"Restart Now",
btnCancel:"Cancel",
cdSuffix:"s to auto-restart",
btnReSetup:"Restart Setup",
lblFirmware:"Firmware:",
lblBat:"Battery:",
lblSsid:"WiFi Name (SSID)",
lblPw:"WiFi Password",
stWait:"Waiting for setup...",
errSsid:"Please select or enter WiFi",
errPw:"Please enter password",
errPwLen:"Password must be at least 8 chars",
errUrl:"Server URL must start with http:// or https://",
errPort:"Frontend port must be 2-5 digits",
msgConn:"Connecting to ",
msgConnOk:"WiFi Connected",
msgConnFail:"Connection Failed",
msgReqFail:"Request failed, try again",
msgSetupOk:"Setup Complete!",
msgRest1:"Restarting, redirecting to config page...",
msgRest2:"Restarting, please enter pairing code on config page later...",
htmlRedir:"<h2>Redirecting to config</h2><p style=\"color:#888\">Please ensure you are connected to your home WiFi</p>",
htmlRedirLink:"Click here to redirect manually",
htmlRestOk:"<h2>Device Restarted</h2><p style=\"color:#888\">Please switch to your home WiFi, open the config page, and enter the pairing code below.</p>",
htmlRestFail:"<h2>Pairing Code Failed</h2><p style=\"color:#888\">Please retry the setup process later.</p>",
msgCancel:"Auto-restart cancelled",
msgScanFail:"Scan failed, please refresh or enter manually"
}
};

function t(k){return i18n[lang][k];}

function applyLang(){
document.title=t('title');
document.getElementById('logoText').innerHTML=t('logoText');
document.getElementById('subtitle').textContent=t('subtitle');
document.getElementById('wtScan').textContent=t('tabScan');
document.getElementById('wtMan').textContent=t('tabMan');
document.getElementById('scanText').textContent=t('scanning');
document.getElementById('reselectBtn').textContent=t('reselect');
document.getElementById('lblSsid').textContent=t('lblSsid');
document.getElementById('ssidIn').placeholder=t('ssidPh');
document.getElementById('lblPw').textContent=t('lblPw');
document.getElementById('pwIn').placeholder=t('pwPh');
document.getElementById('srvTitle').textContent=t('srvTitle');
document.getElementById('srvOfficial').textContent=t('srvOff');
document.getElementById('srvCustom').textContent=t('srvCus');
document.getElementById('srvOfficialTip').textContent=t('srvOffTip');
document.getElementById('srvCusTip1').textContent=t('srvCusTip1');
document.getElementById('srvCusTip2').textContent=t('srvCusTip2');
document.getElementById('srvIn').placeholder=t('srvUrlPh');
document.getElementById('frontendPortIn').placeholder=t('srvPortPh');
document.getElementById('btnConnText').textContent=t('btnConn');
document.getElementById('btnAddText').textContent=t('btnAdd');
document.getElementById('savedTitle').textContent=t('savedTitle');
document.getElementById('addHint').textContent=t('addHint');
document.getElementById('s2Title').textContent=t('s2Title');
document.getElementById('s2Next').textContent=t('s2Next');
document.getElementById('s2Auto').textContent=t('s2Auto');
document.getElementById('s2Warn').textContent=t('s2Warn');
document.getElementById('s2CodeLbl').textContent=t('s2CodeLbl');
document.getElementById('btnRest').textContent=t('btnRest');
document.getElementById('cdCancelBtn').textContent=t('btnCancel');
document.getElementById('cdSuffix').textContent=t('cdSuffix');
document.getElementById('btnReSetup').textContent=t('btnReSetup');
document.getElementById('lblFirmware').textContent=t('lblFirmware');
document.getElementById('lblBat').textContent=t('lblBat');
var pSt=document.getElementById('pSt');
if(pSt.textContent===i18n[lang==='zh'?'en':'zh'].stWait)pSt.textContent=t('stWait');
document.getElementById('langBtn').textContent=lang==='zh'?'EN':'中';
}

function toggleLang(){
lang=lang==='zh'?'en':'zh';
localStorage.setItem('ink_lang',lang);
applyLang();
}

var OFFICIAL_SERVER='https://web.inksight.site/';
var OFFICIAL_CONFIG_URL='https://www.inksight.site/config';
var LOCAL_DEFAULT_SERVER='http://本地服务IP:8080';
var LOCAL_DEFAULT_FRONTEND_PORT='3000';
var ssid='',ctm=null,devMac='',srvUrl='',srvMode='official',pairCode='',frontendPort=LOCAL_DEFAULT_FRONTEND_PORT;
var hiddenSsids=[];
var savedMax=5;

function setStep(n){
var d1=document.getElementById('d1'),d2=document.getElementById('d2');
var l1=document.getElementById('l1');
d1.className='dot'+(n===1?' a':' d');
d2.className='dot'+(n===2?' a d':'');
l1.className='ln'+(n>=2?' d':'');
}

function switchWTab(mode){
var ts=document.getElementById('wtScan'),tm=document.getElementById('wtMan');
var ps=document.getElementById('wScan'),pm=document.getElementById('wMan');
if(mode==='scan'){ts.classList.add('act');tm.classList.remove('act');ps.classList.remove('hidden');pm.classList.add('hidden');ssid='';reShowList();}
else{tm.classList.add('act');ts.classList.remove('act');pm.classList.remove('hidden');ps.classList.add('hidden');ssid='';document.getElementById('ssidIn').value='';document.getElementById('ssidIn').focus();}
}

function normalizeServerUrl(url){
return (url||'').replace(/\/+$/,'');
}

function getConfigUrl(){
var normalized=normalizeServerUrl(srvUrl);
var base='';
if(!normalized)return'';
if(normalized===normalizeServerUrl(OFFICIAL_SERVER))base=OFFICIAL_CONFIG_URL;
else{
if(!frontendPort||!/^\d{2,5}$/.test(frontendPort))return'';
base='http://localhost:'+frontendPort+'/config';
}
var qs=[];
if(devMac)qs.push('prefer_mac='+encodeURIComponent(devMac));
if(pairCode)qs.push('code='+encodeURIComponent(pairCode));
return qs.length?base+'?'+qs.join('&'):base;
}

function switchSrvMode(mode){
var o=document.getElementById('srvOfficial'),c=document.getElementById('srvCustom');
var tip=document.getElementById('srvOfficialTip'),wrap=document.getElementById('srvCustomWrap');
var input=document.getElementById('srvIn'),portInput=document.getElementById('frontendPortIn');
srvMode=mode==='custom'?'custom':'official';
if(srvMode==='official'){
o.classList.add('act');c.classList.remove('act');
tip.classList.remove('hidden');wrap.classList.add('hidden');
srvUrl=normalizeServerUrl(OFFICIAL_SERVER);
frontendPort=LOCAL_DEFAULT_FRONTEND_PORT;
}else{
c.classList.add('act');o.classList.remove('act');
wrap.classList.remove('hidden');tip.classList.add('hidden');
if(!input.value||normalizeServerUrl(input.value)===normalizeServerUrl(OFFICIAL_SERVER))input.value=LOCAL_DEFAULT_SERVER;
if(!portInput.value)portInput.value=LOCAL_DEFAULT_FRONTEND_PORT;
srvUrl=normalizeServerUrl(input.value.trim());
frontendPort=(portInput.value||'').trim();
}
}

function selW(el){
var nextSsid=el.dataset.ssid;
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
el.classList.add('sel');ssid=nextSsid;
document.getElementById('wtScan').classList.add('act');
document.getElementById('wtMan').classList.remove('act');
document.getElementById('pwIn').value='';
document.getElementById('wifiList').style.display='none';
var ws=document.getElementById('wSel');ws.style.display='flex';ws.classList.remove('hidden');
document.getElementById('wSelName').textContent=ssid;
}

function reShowList(){
document.getElementById('wtScan').classList.add('act');
document.getElementById('wtMan').classList.remove('act');
document.getElementById('wifiList').style.display='block';
var ws=document.getElementById('wSel');ws.style.display='none';ws.classList.add('hidden');
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
ssid='';
}

function togglePw(){
var i=document.getElementById('pwIn'),b=document.getElementById('tpb');
if(i.type==='password'){i.type='text';b.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';}
else{i.type='password';b.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';}
}

function setServerForConnect(st){
var sv=srvMode==='official'?OFFICIAL_SERVER:document.getElementById('srvIn').value.trim();
var fp=srvMode==='official'?LOCAL_DEFAULT_FRONTEND_PORT:document.getElementById('frontendPortIn').value.trim();
if(sv&&!sv.match(/^https?:\/\//)){st.className='st e';st.textContent=t('errUrl');return false;}
if(srvMode==='custom'&&!/^\d{2,5}$/.test(fp)){st.className='st e';st.textContent=t('errPort');return false;}
srvUrl=normalizeServerUrl(sv);
frontendPort=fp;
return true;
}

function doConnect(){
var s=ssid||document.getElementById('ssidIn').value.trim();
var p=document.getElementById('pwIn').value;
var st=document.getElementById('pSt'),btn=document.getElementById('cBtn');
if(!s){st.className='st e';st.textContent=t('errSsid');return;}
if(!p){st.className='st e';st.textContent=t('errPw');return;}
if(p.length<8){st.className='st e';st.textContent=t('errPwLen');return;}
if(!setServerForConnect(st))return;
btn.classList.add('ld');btn.disabled=true;
st.className='st c';st.textContent=t('msgConn')+s+' ...';

var fd=new FormData();fd.append('ssid',s);fd.append('pass',p);if(srvUrl)fd.append('server',srvUrl);
fetch('/save_wifi',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
btn.classList.remove('ld');btn.disabled=false;
if(d.ok){
st.className='st s';st.textContent=t('msgConnOk');
document.getElementById('cSSID').textContent=s;
pairCode=(d.pair_code||'').toUpperCase();
showSuccess();
}else{
st.className='st e';st.textContent=d.msg||t('msgConnFail');
}
}).catch(function(){
btn.classList.remove('ld');btn.disabled=false;
st.className='st e';st.textContent=t('msgReqFail');
});
}

function showSuccess(){
document.getElementById('s1').classList.add('hidden');
document.getElementById('s2').classList.remove('hidden');
setStep(2);
document.getElementById('pSt').className='st s';
document.getElementById('pSt').textContent=t('msgSetupOk');
if(pairCode){
document.getElementById('pairWrap').classList.remove('hidden');
document.getElementById('pairCode').textContent=pairCode;
}
var c=30;document.getElementById('cdN').textContent=c;
ctm=setInterval(function(){c--;document.getElementById('cdN').textContent=c;
if(c<=0){clearInterval(ctm);ctm=null;doRestart();}
},1000);
}

function doRestart(){
if(ctm)clearInterval(ctm);
var url=getConfigUrl();
document.getElementById('pSt').className='st c';
document.getElementById('pSt').textContent=url?t('msgRest1'):t('msgRest2');
fetch('/restart',{method:'POST'}).catch(function(){});
setTimeout(function(){
if(url){
document.body.innerHTML='<div style="text-align:center;padding:50px;font-family:sans-serif">'+t('htmlRedir')+(pairCode?'<div style="margin:18px auto 0;max-width:260px;padding:14px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc"><div style="font-size:.8rem;color:#6b7280">'+t('s2CodeLbl')+'</div><div style="margin-top:6px;font-size:1.5rem;letter-spacing:.18em;font-weight:700">'+pairCode+'</div></div>':'')+'<p style="margin-top:12px"><a href="'+url+'" style="color:#3b82f6">'+t('htmlRedirLink')+'</a></p></div>';
window.location.href=url;
return;
}
document.body.innerHTML=pairCode?'<div style="text-align:center;padding:50px;font-family:sans-serif">'+t('htmlRestOk')+'<div style="margin:18px auto 0;max-width:260px;padding:14px;border:1px solid #e5e7eb;border-radius:10px;background:#f8fafc;font-size:1.5rem;letter-spacing:.18em;font-weight:700">'+pairCode+'</div></div>':'<div style="text-align:center;padding:50px;font-family:sans-serif">'+t('htmlRestFail')+'</div>';
},3000);
}

function cancelCountdown(){
if(ctm){clearInterval(ctm);ctm=null;}
document.getElementById('cdN').textContent='--';
document.querySelector('.cd').textContent=t('msgCancel');
document.getElementById('cdCancelBtn').disabled=true;
}

function resetP(){
if(ctm)clearInterval(ctm);
fetch('/reset_portal',{method:'POST'}).catch(function(){});
document.getElementById('s1').classList.remove('hidden');
document.getElementById('s2').classList.add('hidden');
document.getElementById('pwIn').value='';
document.getElementById('pSt').className='st w';
document.getElementById('pSt').textContent=t('stWait');
setStep(1);
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
ssid='';
pairCode='';
document.getElementById('pairWrap').classList.add('hidden');
document.getElementById('pairCode').textContent='--------';
document.getElementById('cdN').textContent='10';
loadSaved();
}

// ── Saved networks (multi-WiFi) ─────────────────────────────
function renderSaved(d){
if(d&&typeof d.max==='number')savedMax=d.max;
var names=(d&&d.networks)||[];
var wrap=document.getElementById('savedWrap');
var ul=document.getElementById('savedList');
var cnt=document.getElementById('savedCount');
var addBtn=document.getElementById('addBtn');
ul.innerHTML='';
names.forEach(function(name,idx){
var li=document.createElement('li');li.className='wi';li.style.cursor='default';
var left=document.createElement('span');left.className='wn';
var ord=document.createElement('span');ord.className='si-ord';ord.textContent=(idx+1);
var nm=document.createElement('span');nm.textContent=name;
left.appendChild(ord);left.appendChild(nm);
var actions=document.createElement('span');actions.className='wa';
var conn=document.createElement('button');conn.className='wc';conn.type='button';conn.textContent=t('btnSavedConn');
conn.onclick=function(){connectSaved(name,conn)};
var del=document.createElement('button');del.className='wx';del.type='button';del.innerHTML='&times;';
del.onclick=function(){delNet(name)};
actions.appendChild(conn);actions.appendChild(del);
li.appendChild(left);li.appendChild(actions);
ul.appendChild(li);
});
cnt.textContent=names.length+'/'+savedMax;
if(names.length>0)wrap.classList.remove('hidden');else wrap.classList.add('hidden');
var full=names.length>=savedMax;
addBtn.disabled=full;
}

function loadSaved(){
fetch('/wifi_list').then(function(r){return r.json()}).then(renderSaved).catch(function(){});
}

function delNet(name){
var st=document.getElementById('pSt');
var fd=new FormData();fd.append('ssid',name);
fetch('/delete_wifi',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
if(d&&d.list){renderSaved(d.list);}else{loadSaved();}
st.className='st w';st.textContent=t('msgDelOk');
}).catch(function(){st.className='st e';st.textContent=t('msgReqFail');});
}

function connectSaved(name,btn){
var st=document.getElementById('pSt');
if(!setServerForConnect(st))return;
btn.disabled=true;
st.className='st c';st.textContent=t('msgConn')+name+' ...';
var fd=new FormData();fd.append('ssid',name);if(srvUrl)fd.append('server',srvUrl);
fetch('/connect_saved',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
btn.disabled=false;
if(d&&d.list){renderSaved(d.list);}
if(d.ok){
st.className='st s';st.textContent=t('msgConnOk');
document.getElementById('cSSID').textContent=name;
pairCode=(d.pair_code||'').toUpperCase();
showSuccess();
}else if(d.msg==='SAVED_CONNECT_FAILED'){
st.className='st e';st.textContent=t('msgSavedConnFail');
}else if(d.msg==='NOT_FOUND'){
st.className='st e';st.textContent=t('msgSavedNotFound');
}else{
st.className='st e';st.textContent=d.msg||t('msgConnFail');
}
}).catch(function(){
btn.disabled=false;
st.className='st e';st.textContent=t('msgReqFail');
});
}

function doAddOnly(){
var s=ssid||document.getElementById('ssidIn').value.trim();
var p=document.getElementById('pwIn').value;
var st=document.getElementById('pSt'),btn=document.getElementById('addBtn');
if(!s){st.className='st e';st.textContent=t('errSsid');return;}
if(p.length>0&&p.length<8){st.className='st e';st.textContent=t('errPwLen');return;}
btn.classList.add('ld');btn.disabled=true;
var fd=new FormData();fd.append('ssid',s);fd.append('pass',p);
fetch('/add_wifi',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
btn.classList.remove('ld');btn.disabled=false;
if(d.ok){
st.className='st s';st.textContent=t('msgAddOk');
document.getElementById('ssidIn').value='';document.getElementById('pwIn').value='';
ssid='';reShowList();
renderSaved(d.list);
}else{
st.className='st e';st.textContent=d.msg==='FULL'?t('msgFull'):(d.msg||t('msgReqFail'));
}
}).catch(function(){
btn.classList.remove('ld');btn.disabled=false;
st.className='st e';st.textContent=t('msgReqFail');
});
}

(function(){
applyLang();
switchWTab('manual');
loadSaved();
fetch('/scan').then(function(r){return r.json()}).then(function(d){
document.getElementById('wScanLoading').style.display='none';
var ul=document.getElementById('wifiList');
ul.style.display='block';
ul.innerHTML='';
(d.networks||[]).forEach(function(n){
var bars='';var s=n.rssi||0;
var lvl=s>-50?4:s>-65?3:s>-75?2:1;
for(var i=1;i<=4;i++){
var h=[4,7,10,14][i-1];
bars+='<span class="b'+(i<=lvl?' a':'')+'" style="height:'+h+'px"></span>';
}
var lock=n.secure?'<svg class="wk" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>':'';
var li=document.createElement('li');li.className='wi';li.dataset.ssid=n.ssid;
li.onclick=function(){selW(this)};
li.innerHTML='<span class="wn">'+lock+n.ssid+'</span><span class="ws">'+bars+'</span>';
ul.appendChild(li);
});
}).catch(function(){
document.getElementById('wScanLoading').innerHTML='扫描失败，请刷新页面重试或手动输入';
});

fetch('/info').then(function(r){return r.json()}).then(function(d){
if(d.mac){devMac=d.mac;document.getElementById('devMAC').textContent=d.mac;}
if(d.battery)document.getElementById('devBat').textContent=d.battery;
if(d.server_url){
srvUrl=normalizeServerUrl(d.server_url);
if(/(^|\/\/)(web\.|www\.)?inksight\.site(:|\/|$)/i.test(srvUrl)){
switchSrvMode('official');
}else{
document.getElementById('srvIn').value=srvUrl||LOCAL_DEFAULT_SERVER;
switchSrvMode('custom');
}
}else{
switchSrvMode('official');
}
}).catch(function(){});
})();
</script>
</body>
</html>)rawliteral";

#endif
