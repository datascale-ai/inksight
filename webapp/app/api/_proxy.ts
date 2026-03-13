import { NextRequest, NextResponse } from "next/server";

const backendBase =
  process.env.INKSIGHT_BACKEND_API_BASE?.replace(/\/$/, "") ||
  "http://127.0.0.1:8080";

function imageHeadersFromUpstream(res: Response, contentType: string): HeadersInit {
  const headers: Record<string, string> = { "content-type": contentType };
  const passthrough = ["x-cache-hit", "x-preview-bypass", "x-pending-refresh", "x-preview-status"];
  for (const key of passthrough) {
    const value = res.headers.get(key);
    if (value !== null) headers[key] = value;
  }
  return headers;
}

function passthroughHeaders(req?: NextRequest, extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = { ...(extra || {}) };
  if (!req) return headers;
  const authorization = req.headers.get("authorization");
  const cookie = req.headers.get("cookie");
  const deviceToken = req.headers.get("x-device-token");
  if (authorization) headers.authorization = authorization;
  if (cookie) headers.cookie = cookie;
  if (deviceToken) headers["x-device-token"] = deviceToken;
  return headers;
}

export async function proxyGet(pathWithQuery: string, req?: NextRequest) {
  const target = `${backendBase}${pathWithQuery}`;
  try {
    const res = await fetch(target, { cache: "no-store", headers: passthroughHeaders(req) });
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("image/")) {
      const buf = await res.arrayBuffer();
      return new NextResponse(buf, {
        status: res.status,
        headers: imageHeadersFromUpstream(res, ct),
      });
    }
    if (ct.includes("application/json")) {
      return NextResponse.json(await res.json(), { status: res.status });
    }
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: { "content-type": ct || "text/plain" },
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      { error: "upstream_unreachable", message: msg, backend: backendBase },
      { status: 503 },
    );
  }
}

export async function proxyStream(pathWithQuery: string, req?: NextRequest) {
  const target = `${backendBase}${pathWithQuery}`;
  try {
    const res = await fetch(target, { cache: "no-store", headers: passthroughHeaders(req) });
    return new NextResponse(res.body, {
      status: res.status,
      headers: {
        "content-type": res.headers.get("content-type") || "text/event-stream",
        "cache-control": "no-cache",
        "connection": "keep-alive",
      },
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      { error: "upstream_unreachable", message: msg, backend: backendBase },
      { status: 503 },
    );
  }
}

export async function proxyPost(
  path: string,
  req: NextRequest,
  extraHeaders?: Record<string, string>,
) {
  const target = `${backendBase}${path}`;
  try {
    const ct = req.headers.get("content-type") || "application/json";
    const body = await req.arrayBuffer();
    const res = await fetch(target, {
      method: "POST",
      headers: passthroughHeaders(req, { "content-type": ct, ...(extraHeaders || {}) }),
      body,
    });
    const resCt = res.headers.get("content-type") || "";
    if (resCt.includes("image/")) {
      const buf = await res.arrayBuffer();
      return new NextResponse(buf, {
        status: res.status,
        headers: imageHeadersFromUpstream(res, resCt),
      });
    }
    if (resCt.includes("application/json")) {
      return NextResponse.json(await res.json(), { status: res.status });
    }
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: { "content-type": resCt || "text/plain" },
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      { error: "upstream_unreachable", message: msg, backend: backendBase },
      { status: 503 },
    );
  }
}

export async function proxyPut(path: string, req: NextRequest) {
  const target = `${backendBase}${path}`;
  try {
    const ct = req.headers.get("content-type") || "application/json";
    const body = await req.arrayBuffer();
    const res = await fetch(target, {
      method: "PUT",
      headers: passthroughHeaders(req, { "content-type": ct }),
      body,
    });
    const resCt = res.headers.get("content-type") || "";
    if (resCt.includes("application/json")) {
      return NextResponse.json(await res.json(), { status: res.status });
    }
    return new NextResponse(await res.text(), {
      status: res.status,
      headers: { "content-type": resCt || "text/plain" },
    });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      { error: "upstream_unreachable", message: msg, backend: backendBase },
      { status: 503 },
    );
  }
}

export async function proxyDelete(path: string, req?: NextRequest) {
  const target = `${backendBase}${path}`;
  try {
    const res = await fetch(target, { method: "DELETE", headers: passthroughHeaders(req) });
    const ct = res.headers.get("content-type") || "";
    if (ct.includes("application/json")) {
      return NextResponse.json(await res.json(), { status: res.status });
    }
    return new NextResponse(await res.text(), { status: res.status });
  } catch (error) {
    const msg = error instanceof Error ? error.message : "upstream fetch failed";
    return NextResponse.json(
      { error: "upstream_unreachable", message: msg, backend: backendBase },
      { status: 503 },
    );
  }
}
