#ifndef PORTAL_HTML_H
#define PORTAL_HTML_H

const char PORTAL_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=yes">
<title>InkSight 配置</title>
<style>
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--bk:#1a1a1a;--wh:#f5f5f0;--gy:#888;--lg:#e0e0dc;--bg:#fafaf7;--bd:#d4d4cf;--f:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--fs:'Georgia',serif}
html{font-size:16px;-webkit-font-smoothing:antialiased;overflow-y:scroll;-webkit-overflow-scrolling:touch}
body{font-family:var(--f);background:linear-gradient(135deg,#f5f5f0,#e8e8e0);color:var(--bk);line-height:1.6;min-height:100vh;display:flex;align-items:center;justify-content:center;padding:16px;overflow-y:auto;-webkit-overflow-scrolling:touch}
a{color:inherit;text-decoration:none}
.card{background:#fff;border-radius:20px;box-shadow:0 8px 40px rgba(0,0,0,.08);width:100%;max-width:380px;padding:32px 24px}
.hdr{text-align:center;margin-bottom:24px}
.logo{width:50px;height:50px;background:var(--bk);border-radius:14px;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;color:#fff;font-family:var(--fs);font-size:1.5rem;font-weight:700}
.hdr h1{font-family:var(--fs);font-size:1.4rem;font-weight:700;margin-bottom:2px}
.hdr p{font-size:.82rem;color:var(--gy)}
.steps{display:flex;align-items:center;justify-content:center;margin-bottom:20px}
.dot{width:26px;height:26px;border-radius:50%;border:2px solid var(--bd);display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:600;color:var(--gy);background:#fff;flex-shrink:0}
.dot.a{border-color:var(--bk);background:var(--bk);color:#fff}
.dot.d{border-color:#22c55e;background:#22c55e;color:#fff}
.ln{width:36px;height:2px;background:var(--bd)}
.ln.d{background:#22c55e}
.hidden{display:none!important}
.lbl{display:block;font-size:.78rem;font-weight:500;color:var(--gy);margin-bottom:5px}
.inp{width:100%;padding:10px 12px;font-family:var(--f);font-size:.85rem;border:1px solid var(--bd);border-radius:8px;background:var(--bg);color:var(--bk);outline:none;-webkit-appearance:none}
.inp:focus{border-color:var(--bk);position:relative;z-index:1}
.fg{margin-bottom:12px}
.pw{position:relative}
.pw .inp{padding-right:40px}
.pw-btn{position:absolute;right:10px;top:50%;transform:translateY(-50%);background:none;border:none;cursor:pointer;color:var(--gy);padding:4px}
.btn{display:block;width:100%;padding:12px;font-family:var(--f);font-size:.9rem;font-weight:600;color:#fff;background:var(--bk);border:none;border-radius:10px;cursor:pointer}
.btn:hover{background:#333}
.btn:disabled{opacity:.6;cursor:not-allowed}
.btn .sp{display:none;width:16px;height:16px;border:2px solid rgba(255,255,255,.3);border-top-color:#fff;border-radius:50%;animation:spin .7s linear infinite;margin:0 auto}
.btn.ld .bt{display:none}.btn.ld .sp{display:block}
@keyframes spin{to{transform:rotate(360deg)}}
.wl{list-style:none;margin-bottom:10px}
.wi{display:flex;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--bd);border-radius:8px;margin-bottom:6px;cursor:pointer;background:#fff}
.wi:hover{border-color:var(--bk);background:var(--bg)}
.wi.sel{border-color:var(--bk);background:var(--bg)}
.wn{font-size:.85rem;font-weight:500;display:flex;align-items:center;gap:6px}
.ws{display:flex;align-items:flex-end;gap:1.5px;height:14px}
.ws .b{width:3px;background:var(--lg);border-radius:1px}
.ws .b.a{background:var(--bk)}
.wk{width:12px;height:12px;opacity:.4}
.wtabs{display:flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden;margin-bottom:12px}
.wtab{flex:1;padding:8px 4px;text-align:center;font-size:.78rem;font-weight:500;cursor:pointer;background:#fff;color:var(--gy);border-right:1px solid var(--bd);user-select:none;-webkit-user-select:none}
.wtab:last-child{border-right:none}
.wtab:hover{background:var(--bg)}
.wtab.act{background:var(--bk);color:#fff}
.ps{margin-bottom:14px}
.pl{display:flex;align-items:center;gap:5px;font-size:.78rem;font-weight:600;color:var(--bk);margin-bottom:6px}
.cg{display:flex;flex-wrap:wrap;gap:5px}
.ch{padding:5px 10px;font-family:var(--f);font-size:.75rem;font-weight:500;border:1px solid var(--bd);border-radius:18px;cursor:pointer;background:#fff;color:var(--gy);user-select:none;-webkit-user-select:none}
.ch:hover{border-color:var(--bk);color:var(--bk)}
.ch.sel{background:var(--bk);color:#fff;border-color:var(--bk)}
.pg{display:flex;border:1px solid var(--bd);border-radius:8px;overflow:hidden}
.pi{flex:1;padding:7px 4px;text-align:center;font-family:var(--f);font-size:.75rem;font-weight:500;cursor:pointer;background:#fff;color:var(--gy);border-right:1px solid var(--bd);user-select:none;-webkit-user-select:none}
.pi:last-child{border-right:none}
.pi:hover{background:var(--bg)}
.pi.sel{background:var(--bk);color:#fff}
.tc{margin-bottom:6px}
.tcl{font-size:.68rem;color:var(--gy);margin-bottom:3px;font-weight:500}
.si{width:56px;height:56px;border-radius:50%;background:#22c55e;display:flex;align-items:center;justify-content:center;margin:0 auto 12px;animation:sc .4s cubic-bezier(.175,.885,.32,1.275)}
@keyframes sc{0%{transform:scale(0)}100%{transform:scale(1)}}
.cd{font-family:'SF Mono','Fira Code',monospace;font-size:.82rem;color:var(--gy)}
.cs{text-align:left;background:var(--bg);border-radius:8px;padding:10px 12px;margin:12px 0;font-size:.75rem;color:var(--gy);line-height:1.8}
.cs strong{color:var(--bk);font-weight:600}
hr.dv{border:none;border-top:1px dashed var(--bd);margin:20px 0}
.di{font-size:.75rem;color:var(--gy);line-height:2}
.di dt{display:inline;font-weight:600}
.di dd{display:inline;margin-left:4px;font-family:'SF Mono','Fira Code',monospace}
.st{margin-top:16px;padding:10px 14px;border-radius:8px;font-size:.78rem;font-weight:500;text-align:center}
.st.w{background:var(--bg);color:var(--gy)}
.st.c{background:#fef9c3;color:#a16207}
.st.s{background:#dcfce7;color:#15803d}
.st.e{background:#fef2f2;color:#dc2626}
.ch-desc{font-size:.65rem;color:var(--gy);font-weight:400;margin-left:1px}
.ch.sel .ch-desc{color:rgba(255,255,255,.75)}
.adv-toggle{display:flex;align-items:center;gap:6px;font-size:.78rem;font-weight:500;color:var(--gy);cursor:pointer;padding:8px 0;user-select:none;-webkit-user-select:none}
.adv-toggle:hover{color:var(--bk)}
</style>
</head>
<body>
<div class="card">
<div class="hdr">
<div class="logo">墨</div>
<h1>InkSight <span style="font-weight:400;font-size:.85em">墨鱼</span></h1>
<p>你的智能墨水屏桌面伴侣</p>
</div>

<div class="steps">
<div class="dot a" id="d1">1</div>
<div class="ln" id="l1"></div>
<div class="dot" id="d2">2</div>
<div class="ln" id="l2"></div>
<div class="dot" id="d3"><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
</div>

<!-- Step 1: WiFi -->
<div id="s1">
<div class="wtabs">
<div class="wtab act" id="wtScan" onclick="switchWTab('scan')">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:3px"><path d="M5 12.55a11 11 0 0114.08 0"/><path d="M1.42 9a16 16 0 0121.16 0"/><path d="M8.53 16.11a6 6 0 016.95 0"/><circle cx="12" cy="20" r="1"/></svg>
选择网络
</div>
<div class="wtab" id="wtMan" onclick="switchWTab('manual')">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="vertical-align:-2px;margin-right:3px"><path d="M17 3a2.85 2.85 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
手动输入
</div>
</div>
<div id="wScan">
<ul class="wl" id="wifiList"></ul>
<div id="wSel" class="hidden" style="display:none;align-items:center;justify-content:space-between;padding:10px 12px;border:1px solid var(--bk);border-radius:8px;background:var(--bg);margin-bottom:10px">
<span id="wSelName" style="font-size:.85rem;font-weight:500"></span>
<a onclick="reShowList()" style="font-size:.72rem;color:var(--gy);cursor:pointer">重新选择</a>
</div>
</div>
<div id="wMan" class="hidden">
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
<input type="text" class="inp" id="srvIn" placeholder="例如: http://192.168.1.100:8080">
<div style="font-size:.68rem;color:var(--gy);margin-top:3px">InkSight 后端服务的完整地址（含端口）</div>
</div>
<button class="btn" id="cBtn" onclick="doConnect()"><span class="bt">连接 WiFi</span><div class="sp"></div></button>
</div>

<!-- Step 2: Prefs -->
<div id="s2" class="hidden">

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
昵称
</div>
<input type="text" class="inp" id="nickIn" placeholder="输入昵称（可选）">
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>
内容模式（多选）
</div>
<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:8px" id="presetBar">
<span class="ch" style="background:#f0f9ff;border-color:#93c5fd;color:#1d4ed8;font-size:.7rem" onclick="applyPreset('relax')">轻松模式</span>
<span class="ch" style="background:#fefce8;border-color:#fcd34d;color:#a16207;font-size:.7rem" onclick="applyPreset('news')">资讯模式</span>
<span class="ch" style="background:#f0fdf4;border-color:#86efac;color:#15803d;font-size:.7rem" onclick="applyPreset('all')">全功能体验</span>
</div>
<div class="cg" id="modeC">
<span class="ch sel" data-m="STOIC" onclick="tc(this)"><b>STOIC</b> <span class="ch-desc">哲学箴言+当代解读</span></span>
<span class="ch sel" data-m="ROAST" onclick="tc(this)"><b>ROAST</b> <span class="ch-desc">精准情境吐槽</span></span>
<span class="ch" data-m="ZEN" onclick="tc(this)"><b>ZEN</b> <span class="ch-desc">一字禅+意境</span></span>
<span class="ch sel" data-m="DAILY" onclick="tc(this)"><b>DAILY</b> <span class="ch-desc">语录·书荐·冷知识</span></span>
<span class="ch" data-m="BRIEFING" onclick="tc(this)"><b>BRIEFING</b> <span class="ch-desc">科技热榜简报</span></span>
<span class="ch" data-m="ARTWALL" onclick="tc(this)"><b>ARTWALL</b> <span class="ch-desc">AI 黑白艺术画</span></span>
<span class="ch" data-m="RECIPE" onclick="tc(this)"><b>RECIPE</b> <span class="ch-desc">早中晚三餐</span></span>
<span class="ch" data-m="FITNESS" onclick="tc(this)"><b>FITNESS</b> <span class="ch-desc">居家训练计划</span></span>
<span class="ch" data-m="POETRY" onclick="tc(this)"><b>POETRY</b> <span class="ch-desc">每日古诗词</span></span>
<span class="ch" data-m="COUNTDOWN" onclick="tc(this)"><b>COUNTDOWN</b> <span class="ch-desc">重要日倒计时</span></span>
<span class="ch" data-m="ALMANAC" onclick="tc(this)"><b>ALMANAC</b> <span class="ch-desc">老黄历·宜忌·节气</span></span>
<span class="ch" data-m="LETTER" onclick="tc(this)"><b>LETTER</b> <span class="ch-desc">来自时空的慢信</span></span>
<span class="ch" data-m="THISDAY" onclick="tc(this)"><b>THISDAY</b> <span class="ch-desc">历史上的今天</span></span>
<span class="ch" data-m="RIDDLE" onclick="tc(this)"><b>RIDDLE</b> <span class="ch-desc">谜语·脑筋急转弯</span></span>
<span class="ch" data-m="QUESTION" onclick="tc(this)"><b>QUESTION</b> <span class="ch-desc">每日一问</span></span>
<span class="ch" data-m="BIAS" onclick="tc(this)"><b>BIAS</b> <span class="ch-desc">认知偏差学习</span></span>
<span class="ch" data-m="STORY" onclick="tc(this)"><b>STORY</b> <span class="ch-desc">微型小说</span></span>
<span class="ch" data-m="LIFEBAR" onclick="tc(this)"><b>LIFEBAR</b> <span class="ch-desc">人生进度条</span></span>
<span class="ch" data-m="CHALLENGE" onclick="tc(this)"><b>CHALLENGE</b> <span class="ch-desc">5分钟微挑战</span></span>
<span class="ch" data-m="WEATHER" onclick="tc(this)"><b>WEATHER</b> <span class="ch-desc">天气看板预报</span></span>
<span class="ch" data-m="MEMO" onclick="tc(this)"><b>MEMO</b> <span class="ch-desc">自定义便签</span></span>
<span class="ch" data-m="HABIT" onclick="tc(this)"><b>HABIT</b> <span class="ch-desc">习惯打卡</span></span>
</div>
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0115-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 01-15 6.7L3 16"/></svg>
刷新策略
</div>
<div class="pg" id="rStrat">
<div class="pi sel" data-v="random" onclick="sp(this)">随机轮换</div>
<div class="pi" data-v="cycle" onclick="sp(this)">循环轮换</div>
</div>
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
刷新间隔
</div>
<div style="display:flex;align-items:center;gap:8px">
<input type="number" class="inp" id="riH" min="0" max="24" value="1" style="width:60px;text-align:center" onchange="clampRI()">
<span style="font-size:.85rem;color:var(--gy)">小时</span>
<input type="number" class="inp" id="riM" min="0" max="59" value="0" style="width:60px;text-align:center" onchange="clampRI()">
<span style="font-size:.85rem;color:var(--gy)">分钟</span>
</div>
<div style="font-size:.7rem;color:var(--gy);margin-top:4px">最少 10 分钟，最多 24 小时</div>
</div>

<!-- Advanced settings (collapsed by default) -->
<div class="ps" style="margin-top:8px">
<div class="adv-toggle" onclick="toggleAdvanced()">
<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 01-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>
<span>高级设置</span>
<svg id="advArrow" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="transition:transform .2s"><path d="M6 9l6 6 6-6"/></svg>
</div>
</div>

<div id="advPanel" class="hidden">

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 8V4H8"/><rect x="2" y="2" width="20" height="20" rx="5"/><path d="M2 12h20"/></svg>
角色语气
</div>
<div class="tc"><div class="tcl">文学</div><div class="cg">
<span class="ch" data-t="鲁迅" onclick="tc(this)">鲁迅</span>
<span class="ch" data-t="王小波" onclick="tc(this)">王小波</span>
<span class="ch" data-t="张爱玲" onclick="tc(this)">张爱玲</span>
<span class="ch" data-t="村上春树" onclick="tc(this)">村上春树</span>
</div></div>
<div class="tc"><div class="tcl">影视</div><div class="cg">
<span class="ch" data-t="王家卫" onclick="tc(this)">王家卫</span>
<span class="ch" data-t="周星驰" onclick="tc(this)">周星驰</span>
<span class="ch" data-t="甄嬛" onclick="tc(this)">甄嬛</span>
<span class="ch" data-t="白展堂" onclick="tc(this)">白展堂</span>
</div></div>
<div class="tc"><div class="tcl">哲学</div><div class="cg">
<span class="ch" data-t="苏格拉底" onclick="tc(this)">苏格拉底</span>
<span class="ch" data-t="庄子" onclick="tc(this)">庄子</span>
<span class="ch" data-t="尼采" onclick="tc(this)">尼采</span>
</div></div>
<div class="tc"><div class="tcl">AI / 科幻</div><div class="cg">
<span class="ch" data-t="JARVIS" onclick="tc(this)">JARVIS</span>
<span class="ch" data-t="智子" onclick="tc(this)">智子</span>
<span class="ch" data-t="马文" onclick="tc(this)">马文</span>
</div></div>
<div style="margin-top:6px">
<input type="text" class="inp" id="custTone" placeholder="或自定义：东北大爷、川普...">
</div>
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 014 10 15.3 15.3 0 01-4 10 15.3 15.3 0 01-4-10 15.3 15.3 0 014-10z"/></svg>
语言偏好
</div>
<div class="pg" id="langP">
<div class="pi sel" data-v="zh" onclick="sp(this)">中文为主</div>
<div class="pi" data-v="en" onclick="sp(this)">英文为主</div>
<div class="pi" data-v="mixed" onclick="sp(this)">中英混合</div>
</div>
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><circle cx="9" cy="9" r="1" fill="currentColor"/><circle cx="15" cy="9" r="1" fill="currentColor"/></svg>
内容调性
</div>
<div class="pg" id="cTone">
<div class="pi" data-v="positive" onclick="sp(this)">积极鼓励</div>
<div class="pi sel" data-v="neutral" onclick="sp(this)">中性克制</div>
<div class="pi" data-v="deep" onclick="sp(this)">深沉内省</div>
<div class="pi" data-v="humor" onclick="sp(this)">轻松幽默</div>
</div>
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
地理位置
</div>
<input type="text" class="inp" id="cityIn" placeholder="城市名（最多 20 字符）" value="杭州" maxlength="20">
</div>

<div class="ps">
<div class="pl">
<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
AI 模型
</div>
<select class="inp" id="llmProvider" onchange="updateLLMModels()" style="margin-bottom:6px">
<option value="deepseek">Deepseek</option>
<option value="aliyun">阿里百炼</option>
<option value="moonshot">月之暗面</option>
</select>
<select class="inp" id="llmModel">
<option value="deepseek-chat">DeepSeek Chat</option>
</select>
</div>

</div><!-- /advPanel -->

<button class="btn" style="margin-top:16px" onclick="saveCfg()"><span class="bt">保存配置并重启</span><div class="sp"></div></button>
</div>

<!-- Step 3: Success -->
<div id="s3" class="hidden" style="text-align:center;padding:16px 0">
<div class="si"><svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round"><path d="M20 6L9 17l-5-5"/></svg></div>
<h3 style="font-family:var(--fs);font-size:1.05rem;margin-bottom:4px">配置完成</h3>
<p style="font-size:.82rem;color:var(--gy);margin-bottom:4px">已连接到 <strong id="cSSID"></strong></p>
<div class="cs" id="cSum"></div>
<div style="margin-top:16px;padding:12px;background:#dbeafe;border-radius:8px;font-size:.75rem;color:#1e40af;line-height:1.6;text-align:left">
<strong>💡 提示：</strong>以后想要修改配置，无需重新连接热点，<br>
直接访问以下网址即可在线修改：<br>
<div style="margin-top:8px;padding:8px;background:#fff;border-radius:6px;font-family:monospace;font-size:.7rem;word-break:break-all;color:#1e40af" id="webUrl"></div>
<div style="margin-top:8px;display:flex;gap:8px">
<button onclick="copyUrl()" style="flex:1;padding:6px;font-size:.75rem;background:#3b82f6;color:#fff;border:none;border-radius:6px;cursor:pointer">📋 复制链接</button>
<button onclick="closePortal()" style="flex:1;padding:6px;font-size:.75rem;background:#6b7280;color:#fff;border:none;border-radius:6px;cursor:pointer">✓ 关闭页面</button>
</div>
</div>
<div style="margin-top:12px;display:flex;gap:8px;justify-content:center">
<button class="btn" onclick="doRestart()" style="width:auto;padding:9px 20px;font-size:.82rem">完成并重启</button>
<button class="btn" onclick="cancelCountdown()" id="cdCancelBtn" style="width:auto;padding:9px 16px;font-size:.8rem;background:var(--bg);color:var(--bk)">取消自动重启</button>
</div>
<p class="cd" style="margin-top:8px"><span id="cdN">30</span> 秒后自动重启</p>
<div style="margin-top:10px"><button class="btn" onclick="resetP()" style="background:var(--bg);color:var(--bk);font-size:.8rem;padding:9px">重新配置</button></div>
</div>

<hr class="dv">
<dl class="di">
<div style="margin-bottom:3px"><dt>MAC:</dt><dd id="devMAC">--</dd></div>
<div style="margin-bottom:3px"><dt>固件:</dt><dd>v1.0.0</dd></div>
<div style="margin-bottom:3px"><dt>电池:</dt><dd id="devBat">--</dd></div>
</dl>
<div class="st w" id="pSt">等待配置...</div>
</div>

<script>
var ssid='',ctm=null;

function setStep(n){
var d1=document.getElementById('d1'),d2=document.getElementById('d2'),d3=document.getElementById('d3');
var l1=document.getElementById('l1'),l2=document.getElementById('l2');
d1.className='dot'+(n===1?' a':' d');
d2.className='dot'+(n===2?' a':(n>2?' d':''));
d3.className='dot'+(n===3?' a d':'');
l1.className='ln'+(n>=2?' d':'');
l2.className='ln'+(n>=3?' d':'');
}

function switchWTab(mode){
var ts=document.getElementById('wtScan'),tm=document.getElementById('wtMan');
var ps=document.getElementById('wScan'),pm=document.getElementById('wMan');
if(mode==='scan'){ts.classList.add('act');tm.classList.remove('act');ps.classList.remove('hidden');pm.classList.add('hidden');ssid='';reShowList();}
else{tm.classList.add('act');ts.classList.remove('act');pm.classList.remove('hidden');ps.classList.add('hidden');ssid='';document.getElementById('ssidIn').value='';document.getElementById('ssidIn').focus();}
}

function selW(el){
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
el.classList.add('sel');ssid=el.dataset.ssid;
document.getElementById('wifiList').style.display='none';
var ws=document.getElementById('wSel');ws.style.display='flex';ws.classList.remove('hidden');
document.getElementById('wSelName').textContent=ssid;
}

function reShowList(){
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
var sv=document.getElementById('srvIn').value.trim();
var st=document.getElementById('pSt'),btn=document.getElementById('cBtn');
if(!s){st.className='st e';st.textContent='请选择或输入 WiFi';return;}
if(!p){st.className='st e';st.textContent='请输入密码';return;}
if(p.length<8){st.className='st e';st.textContent='密码至少 8 位';return;}
if(sv&&!sv.match(/^https?:\/\//)){st.className='st e';st.textContent='服务器地址需以 http:// 或 https:// 开头';return;}
btn.classList.add('ld');btn.disabled=true;
st.className='st c';st.textContent='正在连接 '+s+' ...';

var fd=new FormData();fd.append('ssid',s);fd.append('pass',p);if(sv)fd.append('server',sv);
fetch('/save_wifi',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
btn.classList.remove('ld');btn.disabled=false;
if(d.ok){
st.className='st s';st.textContent='WiFi 已连接';
document.getElementById('cSSID').textContent=s;
document.getElementById('s1').classList.add('hidden');
document.getElementById('s2').classList.remove('hidden');
setStep(2);
}else{
st.className='st e';st.textContent=d.msg||'连接失败';
}
}).catch(function(){
btn.classList.remove('ld');btn.disabled=false;
st.className='st e';st.textContent='请求失败，请重试';
});
}

function tc(el){el.classList.toggle('sel')}
function sp(el){var s=el.parentElement.children;for(var i=0;i<s.length;i++)s[i].classList.remove('sel');el.classList.add('sel')}

function toggleAdvanced(){
var p=document.getElementById('advPanel');
var a=document.getElementById('advArrow');
if(p.classList.contains('hidden')){p.classList.remove('hidden');a.style.transform='rotate(180deg)';}
else{p.classList.add('hidden');a.style.transform='';}
}

function setModes(arr){
document.querySelectorAll('#modeC .ch').forEach(function(c){
if(arr.indexOf(c.dataset.m)>=0)c.classList.add('sel');else c.classList.remove('sel');
});
}
function applyPreset(name){
if(name==='relax'){setModes(['ZEN','DAILY','POETRY','LETTER','STORY']);sp(document.querySelector('#rStrat .pi[data-v="random"]'));document.getElementById('riH').value=4;document.getElementById('riM').value=0;}
else if(name==='news'){setModes(['BRIEFING','DAILY','THISDAY','BIAS']);sp(document.querySelector('#rStrat .pi[data-v="cycle"]'));document.getElementById('riH').value=2;document.getElementById('riM').value=0;}
else if(name==='all'){setModes(['STOIC','ROAST','ZEN','DAILY','BRIEFING','ARTWALL','RECIPE','FITNESS','POETRY','COUNTDOWN','ALMANAC','LETTER','THISDAY','RIDDLE','QUESTION','BIAS','STORY','LIFEBAR','CHALLENGE','WEATHER','MEMO','HABIT']);sp(document.querySelector('#rStrat .pi[data-v="random"]'));document.getElementById('riH').value=1;document.getElementById('riM').value=0;}
}

var llmModels={
deepseek:[{v:'deepseek-chat',n:'DeepSeek Chat'}],
aliyun:[{v:'qwen-max',n:'通义千问 Max'},{v:'qwen-plus',n:'通义千问 Plus'},{v:'qwen-turbo',n:'通义千问 Turbo'},{v:'deepseek-v3',n:'DeepSeek V3'},{v:'kimi-2.5',n:'Kimi 2.5'},{v:'glm-4-plus',n:'智谱 GLM-4 Plus'}],
moonshot:[{v:'moonshot-v1-8k',n:'Kimi K1.5'},{v:'moonshot-v1-32k',n:'Kimi K1.5 32K'},{v:'kimi-k2-turbo-preview',n:'Kimi K2 Turbo'}]
};

function updateLLMModels(){
var p=document.getElementById('llmProvider').value;
var m=document.getElementById('llmModel');
m.innerHTML='';
(llmModels[p]||[]).forEach(function(o){
var opt=document.createElement('option');opt.value=o.v;opt.textContent=o.n;m.appendChild(opt);
});
}

function clampRI(){
var h=parseInt(document.getElementById('riH').value)||0;
var m=parseInt(document.getElementById('riM').value)||0;
if(h<0)h=0;if(h>24)h=24;if(m<0)m=0;if(m>59)m=59;
var total=h*60+m;if(total<10){m=10;h=0;}if(total>1440){h=24;m=0;}
document.getElementById('riH').value=h;document.getElementById('riM').value=m;
}

function collectP(){
var m=[];document.querySelectorAll('#modeC .ch.sel').forEach(function(c){m.push(c.dataset.m)});
var t=[];document.querySelectorAll('#s2 .tc .ch.sel').forEach(function(c){t.push(c.dataset.t)});
var ct=document.getElementById('custTone').value.trim();if(ct)t.push(ct);
var rs=document.querySelector('#rStrat .pi.sel');
var lg=document.querySelector('#langP .pi.sel');
var tn=document.querySelector('#cTone .pi.sel');
clampRI();
var riH=parseInt(document.getElementById('riH').value)||0;
var riM=parseInt(document.getElementById('riM').value)||0;
var riTotal=riH*60+riM;if(riTotal<10)riTotal=60;
return{
nickname:document.getElementById('nickIn').value.trim(),
modes:m,
refreshStrategy:rs?rs.dataset.v:'random',
characterTones:t,
language:lg?lg.dataset.v:'zh',
contentTone:tn?tn.dataset.v:'neutral',
city:document.getElementById('cityIn').value.trim()||'杭州',
llmProvider:document.getElementById('llmProvider').value,
llmModel:document.getElementById('llmModel').value,
refreshInterval:riTotal
};
}

function saveCfg(){
var p=collectP();
if(p.modes.length===0){var st=document.getElementById('pSt');st.className='st e';st.textContent='请至少选择一个模式';return;}
var fd=new FormData();fd.append('config',JSON.stringify(p));
fetch('/save_config',{method:'POST',body:fd}).then(function(r){return r.json()}).then(function(d){
if(d.ok){
// Get server URL and MAC from config
fetch('/info').then(function(r){return r.json()}).then(function(info){
showSuccess(p, info.server_url || '', info.mac || '');
}).catch(function(){
showSuccess(p, '', '');
});
}
}).catch(function(){
fetch('/info').then(function(r){return r.json()}).then(function(info){
showSuccess(p, info.server_url || '', info.mac || '');
}).catch(function(){
showSuccess(p, '', '');
});
});
}

function showSuccess(p, serverUrl, mac){
var sl={random:'随机轮换',cycle:'循环轮换'};
var ll={zh:'中文为主',en:'英文为主',mixed:'中英混合'};
var tl={positive:'积极鼓励',neutral:'中性克制',deep:'深沉内省',humor:'轻松幽默'};
var lp={deepseek:'Deepseek',aliyun:'阿里百炼',moonshot:'月之暗面'};
var h='';
if(p.nickname)h+='<strong>昵称:</strong> '+p.nickname+'<br>';
h+='<strong>模式:</strong> '+p.modes.join(', ')+'<br>';
var rh=Math.floor(p.refreshInterval/60),rm=p.refreshInterval%60;
var rt=rh>0?(rh+' 小时'):'';if(rm>0)rt+=(rt?' ':'')+(rm+' 分钟');if(!rt)rt='1 小时';
h+='<strong>刷新:</strong> '+(sl[p.refreshStrategy]||'随机')+' / 每 '+rt+'<br>';
if(p.characterTones.length)h+='<strong>角色:</strong> '+p.characterTones.join(', ')+'<br>';
h+='<strong>语言:</strong> '+(ll[p.language]||'中文')+' · '+(tl[p.contentTone]||'中性')+' <br>';
h+='<strong>城市:</strong> '+p.city+'<br>';
h+='<strong>AI:</strong> '+(lp[p.llmProvider]||'Deepseek');
document.getElementById('cSum').innerHTML=h;
var webConfigUrl=serverUrl+'/config';
if(mac)webConfigUrl+='?mac='+encodeURIComponent(mac);
document.getElementById('webUrl').textContent=webConfigUrl;
window.webConfigUrl=webConfigUrl;
document.getElementById('s2').classList.add('hidden');
document.getElementById('s3').classList.remove('hidden');
setStep(3);
document.getElementById('pSt').className='st s';
document.getElementById('pSt').textContent='配置已保存！';
var c=30;document.getElementById('cdN').textContent=c;
ctm=setInterval(function(){c--;document.getElementById('cdN').textContent=c;
if(c<=0){clearInterval(ctm);ctm=null;doRestart();}
},1000);
}

function copyUrl(){
if(window.webConfigUrl){
navigator.clipboard.writeText(window.webConfigUrl).then(function(){
alert('链接已复制到剪贴板！');
}).catch(function(){
var t=document.createElement('textarea');
t.value=window.webConfigUrl;
document.body.appendChild(t);
t.select();
document.execCommand('copy');
document.body.removeChild(t);
alert('链接已复制到剪贴板！');
});
}
}

function doRestart(){
if(ctm)clearInterval(ctm);
document.getElementById('pSt').className='st c';
document.getElementById('pSt').textContent='设备重启中...';
fetch('/restart',{method:'POST'}).catch(function(){});
setTimeout(function(){
document.body.innerHTML='<div style="text-align:center;padding:50px;font-family:sans-serif"><h2>设备正在重启</h2><p style="color:#888">可以关闭此页面了</p></div>';
},1500);
}

function cancelCountdown(){
if(ctm){clearInterval(ctm);ctm=null;}
document.getElementById('cdN').textContent='--';
document.querySelector('.cd').textContent='自动重启已取消';
document.getElementById('cdCancelBtn').disabled=true;
}

function closePortal(){
if(confirm('确定要关闭页面吗？设备将立即重启。')){
fetch('/restart',{method:'POST'}).then(function(){
window.close();
if(!window.closed){
document.body.innerHTML='<div style="text-align:center;padding:50px;font-family:sans-serif"><h2>设备正在重启</h2><p style="color:#888">可以关闭此页面了</p></div>';
}
}).catch(function(){
window.close();
if(!window.closed){
document.body.innerHTML='<div style="text-align:center;padding:50px;font-family:sans-serif"><h2>设备正在重启</h2><p style="color:#888">可以关闭此页面了</p></div>';
}
});
}
}

function resetP(){
if(ctm)clearInterval(ctm);
document.getElementById('s1').classList.remove('hidden');
document.getElementById('s2').classList.add('hidden');
document.getElementById('s3').classList.add('hidden');
document.getElementById('pwIn').value='';
document.getElementById('pSt').className='st w';
document.getElementById('pSt').textContent='等待配置...';
setStep(1);
document.querySelectorAll('.wi').forEach(function(i){i.classList.remove('sel')});
ssid='';
}

// On load: fetch WiFi scan list and device info from ESP32
(function(){
// Initialize LLM models
updateLLMModels();

// Add session lock to prevent multiple pages from conflicting
var sessionId = Date.now() + '-' + Math.random().toString(36).substr(2, 9);
localStorage.setItem('portalSession', sessionId);
localStorage.setItem('portalSessionTime', Date.now());

// Check if another page is active
window.addEventListener('storage', function(e) {
if (e.key === 'portalSession' && e.newValue !== sessionId) {
alert('检测到其他页面正在配置\n请返回原页面继续操作');
document.querySelectorAll('.btn').forEach(function(b) { b.disabled = true; });
document.getElementById('pSt').className = 'st e';
document.getElementById('pSt').textContent = '请返回原页面操作';
}
});

// Heartbeat to keep session alive
setInterval(function() {
if (localStorage.getItem('portalSession') === sessionId) {
localStorage.setItem('portalSessionTime', Date.now());
}
}, 2000);

// Fix iOS Captive Portal scroll issue - more aggressive approach
var isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
if (isIOS) {
document.body.style.position = 'relative';
document.body.style.overflow = 'auto';
document.querySelector('.card').style.position = 'relative';
}

document.querySelectorAll('.inp').forEach(function(inp) {
inp.addEventListener('focus', function() {
if (isIOS) {
document.body.scrollTop = 0;
setTimeout(function() {
inp.scrollIntoView({ behavior: 'smooth', block: 'center' });
}, 100);
}
});
inp.addEventListener('blur', function() {
if (isIOS) {
window.scrollTo(0, 0);
}
});
});

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
if(d.mac)document.getElementById('devMAC').textContent=d.mac;
if(d.battery)document.getElementById('devBat').textContent=d.battery;
if(d.server_url)document.getElementById('srvIn').value=d.server_url;
}).catch(function(){});
})();
</script>
</body>
</html>)rawliteral";

#endif

