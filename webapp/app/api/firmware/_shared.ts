import { NextResponse } from "next/server";

const backendBase =
  process.env.INKSIGHT_BACKEND_API_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:8080";

export async function proxyFirmwareApi(pathWithQuery: string) {
  const target = `${backendBase}${pathWithQuery}`;
  try {
    const res = await fetch(target, { cache: "no-store" });
    const contentType = res.headers.get("content-type") || "";
    const body = contentType.includes("application/json")
      ? await res.json()
      : { error: "upstream_non_json", message: await res.text() };
    return NextResponse.json(body, { status: res.status });
  } catch (error) {
    const message = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      {
        error: "upstream_unreachable",
        message: `无法访问后端固件接口: ${message}`,
        backend: backendBase,
      },
      { status: 503 }
    );
  }
}
