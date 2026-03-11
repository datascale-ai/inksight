(function () {
  const STORAGE_KEY = "ink_lang";
  const SUPPORTED = ["zh-CN", "en-US"];
  const fallbackDict = {
    "zh-CN": {},
    "en-US": {}
  };

  function normalizeLang(value) {
    if (!value) return "zh-CN";
    const v = String(value).toLowerCase();
    if (v.startsWith("en")) return "en-US";
    return "zh-CN";
  }

  function getCurrentLang() {
    const fromQuery = new URLSearchParams(window.location.search).get("lang");
    if (fromQuery) return normalizeLang(fromQuery);
    const fromStorage = localStorage.getItem(STORAGE_KEY);
    if (fromStorage) return normalizeLang(fromStorage);
    return normalizeLang(navigator.language);
  }

  async function loadDict(lang) {
    try {
      const res = await fetch(`/webconfig/locales/${lang}.json`, { cache: "no-store" });
      if (res.ok) {
        const remote = await res.json();
        return { ...(fallbackDict[lang] || {}), ...(remote || {}) };
      }
    } catch (_) {}
    return fallbackDict[lang] || {};
  }

  function translatePlain(text, dict) {
    const raw = String(text || "");
    if (!raw.trim()) return raw;
    if (dict[raw] !== undefined) return dict[raw];
    return raw
      .replace(/(\d+)\s*秒/g, "$1s")
      .replace(/(\d+)\s*分钟/g, "$1m")
      .replace(/(\d+)\s*小时/g, "$1h")
      .replace(/(\d+)\s*天/g, "$1d");
  }

  function translateNode(node, dict) {
    if (!node) return;
    if (node.nodeType === Node.TEXT_NODE) {
      const translated = translatePlain(node.nodeValue, dict);
      if (translated !== node.nodeValue) node.nodeValue = translated;
      return;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    const el = node;
    ["placeholder", "title", "aria-label", "data-tip"].forEach((attr) => {
      if (el.hasAttribute(attr)) {
        const val = el.getAttribute(attr);
        const next = translatePlain(val, dict);
        if (next !== val) el.setAttribute(attr, next);
      }
    });
    el.childNodes.forEach((child) => translateNode(child, dict));
  }

  function injectSwitcher(lang, onChange) {
    const host = document.createElement("div");
    host.style.cssText =
      "position:fixed;right:14px;top:14px;z-index:10000;background:#fff;border:1px solid #ddd;border-radius:8px;padding:4px 8px;box-shadow:0 2px 12px rgba(0,0,0,.08)";
    const select = document.createElement("select");
    select.style.cssText = "border:none;outline:none;font-size:12px;background:transparent";
    SUPPORTED.forEach((code) => {
      const opt = document.createElement("option");
      opt.value = code;
      opt.textContent = code === "en-US" ? "English" : "中文";
      if (code === lang) opt.selected = true;
      select.appendChild(opt);
    });
    select.addEventListener("change", () => onChange(select.value));
    host.appendChild(select);
    document.body.appendChild(host);
  }

  function patchDateLocale(lang) {
    if (lang !== "en-US") return;
    const p = Date.prototype;
    const _toLocaleString = p.toLocaleString;
    const _toLocaleDateString = p.toLocaleDateString;
    const _toLocaleTimeString = p.toLocaleTimeString;
    p.toLocaleString = function (locales, options) {
      const locale = locales === "zh-CN" || locales == null ? "en-US" : locales;
      return _toLocaleString.call(this, locale, options);
    };
    p.toLocaleDateString = function (locales, options) {
      const locale = locales === "zh-CN" || locales == null ? "en-US" : locales;
      return _toLocaleDateString.call(this, locale, options);
    };
    p.toLocaleTimeString = function (locales, options) {
      const locale = locales === "zh-CN" || locales == null ? "en-US" : locales;
      return _toLocaleTimeString.call(this, locale, options);
    };
  }

  async function apply() {
    const lang = getCurrentLang();
    const dict = await loadDict(lang);
    document.documentElement.setAttribute("lang", lang);
    patchDateLocale(lang);
    translateNode(document.body, dict);
    const observer = new MutationObserver((mutations) => {
      for (const m of mutations) {
        if (m.type === "childList") {
          m.addedNodes.forEach((n) => translateNode(n, dict));
        } else if (m.type === "characterData" && m.target) {
          translateNode(m.target, dict);
        } else if (m.type === "attributes" && m.target) {
          translateNode(m.target, dict);
        }
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["placeholder", "title", "aria-label", "data-tip"]
    });

    injectSwitcher(lang, (next) => {
      localStorage.setItem(STORAGE_KEY, normalizeLang(next));
      window.location.reload();
    });
  }

  window.InkI18n = { apply, getCurrentLang };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }
})();
