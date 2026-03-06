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
<div class="hdr">
<div class="logo">墨</div>
<h1>InkSight <span style="font-weight:400;font-size:.85em">墨鱼</span></h1>
<p>WiFi 配网</p>
</div>

<div class="steps">
<div class="dot a" id="d1">1</div>
<div class="ln" id="l1"></div>
<div class="dot" id="d2"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
</div>

<!-- Step 1: WiFi + Server -->
<div id="s1">
<div class="wtabs">
<div class="wtab" id="wtScan" onclick="switchWTab('scan')">选择网络</div>
<div class="wtab act" id="wtMan" onclick="switchWTab('manual')">手动输入</div>
</div>
<div id="wScan" class="hidden">
<ul class="wl" id="wifiList"></ul>
<div id="wSel" class="hidden" style="display:none;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--bk);border-radius:8px;background:var(--bg);margin-bottom:10px">
<span id="wSelName" style="font-size:.85rem;font-weight:500"></span>
<a onclick="reShowList()" style="font-size:.72rem;color:var(--gy);cursor:pointer">重新选择</a>
</div>
</div>
<div id="wMan">
<div class="fg">
<label class="lbl">WiFi 名称 (SSID)</label>
<input type="text" class="inp" id="ssidIn" placeholder="输入 SSID">
</div>
</div>
<div class="fg">
<label class="lbl">WiFi 密码</label>
<div class="pw">
<input type="password" class="inp" id="pwIn" placeholder="输入密码">
<button class="pw-btn" onclick="togglePw()" type="button" id="tpb">
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
</button>
</div>
</div>
<div class="fg">
<label class="lbl">服务器地址</label>
<div class="wtabs" style="margin-bottom:8px">
<div class="wtab act" id="srvOfficial" onclick="switchSrvMode('official')">官方服务</div>
<div class="wtab" id="srvCustom" onclick="switchSrvMode('custom')">自定义服务</div>
</div>
<div id="srvOfficialTip" style="font-size:.72rem;color:var(--gy)"></div>
<div id="srvCustomWrap" class="hidden">
<input type="text" class="inp" id="srvIn" value="http://本地服务IP:8080" placeholder="例如: http://192.168.1.100:8080">
<div style="font-size:.68rem;color:var(--gy);margin-top:3px">输入你自己部署的 InkSight 后端地址（含端口）</div>
</div>
</div>
<button class="btn btn-ghost" id="cBtn" onclick="doConnect()"><span class="bt">连接并保存</span><div class="sp"></div></button>
</div>

<!-- Step 2: Success -->
<div id="s2" class="hidden" style="text-align:center;padding:16px 0">
<div class="si"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
<h3 style="font-family:var(--fs);font-size:1.05rem;margin-bottom:4px">配网完成</h3>
<p style="font-size:.82rem;color:var(--gy)">已连接到 <strong id="cSSID"></strong></p>

<div class="link-box">
<strong>下一步：</strong>设备将自动重启并联网，届时将为您跳转至配置页面完成个性化设置。<br>
<div style="margin-top:8px;padding:8px 10px;background:#fef3c7;border-radius:6px;font-size:.75rem;color:#92400e;font-weight:500">⚠ 跳转前请先断开 InkSight 热点，重新连接您的家庭 / 办公 WiFi</div>
</div>

<div style="margin-top:16px;display:flex;gap:8px;justify-content:center">
<button class="btn" onclick="doRestart()" style="width:auto;padding:9px 20px;font-size:.82rem">立即重启并跳转</button>
<button class="btn" onclick="cancelCountdown()" id="cdCancelBtn" style="width:auto;padding:9px 16px;font-size:.8rem;background:var(--bg);color:var(--bk)">取消</button>
</div>
<p class="cd"><span id="cdN">10</span> 秒后自动重启并跳转</p>
<div style="margin-top:10px"><button class="btn" onclick="resetP()" style="background:var(--bg);color:var(--bk);font-size:.8rem;padding:9px">重新配网</button></div>
</div>

<hr style="border:none;border-top:1px dashed var(--bd);margin:20px 0">
<dl class="di">
<div style="margin-bottom:3px"><dt>MAC:</dt><dd id="devMAC">--</dd></div>
<div style="margin-bottom:3px"><dt>固件:</dt><dd>v1.0.0</dd></div>
<div style="margin-bottom:3px"><dt>电池:</dt><dd id="devBat">--</dd></div>
</dl>
<div class="st w" id="pSt">等待配网...</div>
</div>

<script>
var OFFICIAL_SERVER='https://web.inksight.site/';
var LOCAL_DEFAULT_SERVER='http://本地服务IP:8080';
var ssid='',ctm=null,devMac='',srvUrl='',srvMode='official';
var hiddenSsids=[];

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

function switchSrvMode(mode){
var o=document.getElementById('srvOfficial'),c=document.getElementById('srvCustom');
var tip=document.getElementById('srvOfficialTip'),wrap=document.getElementById('srvCustomWrap');
var input=document.getElementById('srvIn');
srvMode=mode==='custom'?'custom':'official';
if(srvMode==='official'){
o.classList.add('act');c.classList.remove('act');
tip.classList.remove('hidden');wrap.classList.add('hidden');
srvUrl=normalizeServerUrl(OFFICIAL_SERVER);
}else{
c.classList.add('act');o.classList.remove('act');
wrap.classList.remove('hidden');tip.classList.add('hidden');
if(!input.value||normalizeServerUrl(input.value)===normalizeServerUrl(OFFICIAL_SERVER))input.value=LOCAL_DEFAULT_SERVER;
srvUrl=normalizeServerUrl(input.value.trim());
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
document.getElementById('wifiList').style.display='';
var ws=document.getElementById('wSel');ws.style.display='none';ws.classList.add('hidden');
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
ssid='';
}

function togglePw(){
var i=document.getElementById('pwIn'),b=document.getElementById('tpb');
if(i.type==='password'){i.type='text';b.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/></svg>';}
else{i.type='password';b.innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';}
}

function doConnect(){
var s=ssid||document.getElementById('ssidIn').value.trim();
var p=document.getElementById('pwIn').value;
var sv=srvMode==='official'?OFFICIAL_SERVER:document.getElementById('srvIn').value.trim();
var st=document.getElementById('pSt'),btn=document.getElementById('cBtn');
if(!s){st.className='st e';st.textContent='请选择或输入 WiFi';return;}
if(!p){st.className='st e';st.textContent='请输入密码';return;}
if(p.length<8){st.className='st e';st.textContent='密码至少 8 位';return;}
if(sv&&!sv.match(/^https?:\/\//)){st.className='st e';st.textContent='服务器地址需以 http:// 或 https:// 开头';return;}
btn.classList.add('ld');btn.disabled=true;
st.className='st c';st.textContent='正在连接 '+s+' ...';
srvUrl=normalizeServerUrl(sv);

var fd=new FormData();fd.append('ssid',s);fd.append('pass',p);if(srvUrl)fd.append('server',srvUrl);
fetch('/save_wifi',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
btn.classList.remove('ld');btn.disabled=false;
if(d.ok){
st.className='st s';st.textContent='WiFi 已连接';
document.getElementById('cSSID').textContent=s;
showSuccess();
}else{
st.className='st e';st.textContent=d.msg||'连接失败';
}
}).catch(function(){
btn.classList.remove('ld');btn.disabled=false;
st.className='st e';st.textContent='请求失败，请重试';
});
}

function getConfigUrl(){
if(!srvUrl)return'https://www.inksight.site/config'+(devMac?'?mac='+encodeURIComponent(devMac):'');
try{
var u=new URL(srvUrl);
var h=(u.hostname||'').toLowerCase();
var isPrivate=(h==='localhost'||h==='127.0.0.1'||h==='::1'||/^10\./.test(h)||/^192\.168\./.test(h)||/^172\.(1[6-9]|2\d|3[0-1])\./.test(h));
if(isPrivate){
return u.protocol+'//localhost:3000/config'+(devMac?'?mac='+encodeURIComponent(devMac):'');
}
if(h==='web.inksight.site'||h==='inksight.site'||h==='www.inksight.site'){
return'https://www.inksight.site/config'+(devMac?'?mac='+encodeURIComponent(devMac):'');
}
return u.origin+'/config'+(devMac?'?mac='+encodeURIComponent(devMac):'');
}catch(e){
return srvUrl.replace(/\/$/,'')+'/config'+(devMac?'?mac='+encodeURIComponent(devMac):'');
}
}

function showSuccess(){
document.getElementById('s1').classList.add('hidden');
document.getElementById('s2').classList.remove('hidden');
setStep(2);
document.getElementById('pSt').className='st s';
document.getElementById('pSt').textContent='配网完成！';
var c=30;document.getElementById('cdN').textContent=c;
ctm=setInterval(function(){c--;document.getElementById('cdN').textContent=c;
if(c<=0){clearInterval(ctm);ctm=null;doRestart();}
},1000);
}

function doRestart(){
if(ctm)clearInterval(ctm);
document.getElementById('pSt').className='st c';
document.getElementById('pSt').textContent='设备重启中，即将跳转至配置页...';
fetch('/restart',{method:'POST'}).catch(function(){});
var url=getConfigUrl();
setTimeout(function(){
document.body.innerHTML='<div style="text-align:center;padding:50px;font-family:sans-serif"><h2>正在跳转至配置页</h2><p style="color:#888">请确保已切换回家庭 WiFi</p><p style="margin-top:12px"><a href="'+url+'" style="color:#3b82f6">点击此处手动跳转</a></p></div>';
window.location.href=url;
},3000);
}

function cancelCountdown(){
if(ctm){clearInterval(ctm);ctm=null;}
document.getElementById('cdN').textContent='--';
document.querySelector('.cd').textContent='自动重启已取消';
document.getElementById('cdCancelBtn').disabled=true;
}

function resetP(){
if(ctm)clearInterval(ctm);
document.getElementById('s1').classList.remove('hidden');
document.getElementById('s2').classList.add('hidden');
document.getElementById('pwIn').value='';
document.getElementById('pSt').className='st w';
document.getElementById('pSt').textContent='等待配网...';
setStep(1);
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
ssid='';
}

(function(){
switchWTab('manual');
fetch('/scan').then(function(r){return r.json()}).then(function(d){
var ul=document.getElementById('wifiList');ul.innerHTML='';
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
}).catch(function(){});

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
