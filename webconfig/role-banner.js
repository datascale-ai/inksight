(function () {
  function mountBanner() {
    if (document.getElementById("legacy-console-banner")) return;

    const banner = document.createElement("div");
    banner.id = "legacy-console-banner";
    banner.style.cssText = [
      "position:sticky",
      "top:0",
      "z-index:9999",
      "display:flex",
      "gap:12px",
      "align-items:flex-start",
      "padding:10px 14px",
      "background:#fff7ed",
      "border-bottom:1px solid #fdba74",
      "font:12px/1.5 system-ui,sans-serif",
      "color:#9a3412",
    ].join(";");

    const title = document.createElement("strong");
    title.textContent = "Legacy webconfig";
    title.style.cssText = "font-weight:700;white-space:nowrap";

    const text = document.createElement("div");
    text.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;align-items:center";

    const copy = document.createElement("span");
    copy.textContent =
      "This console is reserved for diagnostics, preview, and custom mode authoring. Daily device configuration now belongs in the main web app.";

    const currentUrl = new URL(window.location.href);
    const mac = currentUrl.searchParams.get("mac");
    const appLink = document.createElement("a");
    appLink.href = mac ? `/config?mac=${encodeURIComponent(mac)}` : "/config";
    appLink.textContent = "Open primary config";
    appLink.style.cssText =
      "display:inline-flex;align-items:center;padding:4px 8px;border:1px solid #fb923c;border-radius:999px;color:#9a3412;text-decoration:none;background:#ffedd5";

    banner.appendChild(title);
    text.appendChild(copy);
    text.appendChild(appLink);
    banner.appendChild(text);
    document.body.prepend(banner);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountBanner);
  } else {
    mountBanner();
  }
})();
