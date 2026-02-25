"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function WidgetContent() {
  const searchParams = useSearchParams();
  const mac = searchParams.get("mac") || "";
  const mode = searchParams.get("mode") || "";
  const size = searchParams.get("size") || "medium";
  const error = mac ? "" : "Missing mac parameter";
  const imgSrc = (() => {
    if (!mac) return "";
    const apiBase = process.env.NEXT_PUBLIC_API_BASE || "";
    const params = new URLSearchParams();
    if (mode) params.set("mode", mode);
    if (size) params.set("size", size);
    return `${apiBase}/api/widget/${encodeURIComponent(mac)}?${params.toString()}`;
  })();

  if (error) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "100vh",
          background: "#fafaf7",
          color: "#888",
          fontFamily: "sans-serif",
          fontSize: "14px",
        }}
      >
        {error}
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        background: "#fafaf7",
        padding: "8px",
      }}
    >
      {imgSrc ? (
        <img
          src={imgSrc}
          alt="InkSight Widget"
          style={{
            maxWidth: "100%",
            maxHeight: "100%",
            borderRadius: "8px",
          }}
        />
      ) : (
        <div style={{ color: "#888", fontFamily: "sans-serif" }}>
          Loading...
        </div>
      )}
    </div>
  );
}

export default function WidgetPage() {
  return (
    <Suspense
      fallback={
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100vh",
            color: "#888",
          }}
        >
          Loading...
        </div>
      }
    >
      <WidgetContent />
    </Suspense>
  );
}
