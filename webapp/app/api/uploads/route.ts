import { NextRequest, NextResponse } from "next/server";

const backendBaseEnv = process.env.INKSIGHT_BACKEND_API_BASE?.replace(/\/$/, "") || "";
const backendTargets = backendBaseEnv
  ? [backendBaseEnv]
  : ["http://127.0.0.1:8080", "http://127.0.0.1:8000"];

export async function POST(req: NextRequest) {
  try {
    const form = await req.formData();
    const file = form.get("file");
    if (!(file instanceof File)) {
      return NextResponse.json({ error: "invalid_request", message: "missing file" }, { status: 400 });
    }
    if (!file.type.startsWith("image/")) {
      return NextResponse.json({ error: "invalid_file", message: "only image/* is allowed" }, { status: 400 });
    }
    const buf = new Uint8Array(await file.arrayBuffer());
    if (buf.byteLength > 10 * 1024 * 1024) {
      return NextResponse.json({ error: "file_too_large", message: "max 10MB" }, { status: 413 });
    }

    const forwardedProto = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim()
      || req.nextUrl.protocol.replace(/:$/, "");
    const forwardedHost = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim()
      || req.headers.get("host")?.split(",")[0]?.trim()
      || "";

    let lastError: string | null = null;
    for (const backendBase of backendTargets) {
      try {
        const res = await fetch(`${backendBase}/api/uploads`, {
          method: "POST",
          headers: {
            "content-type": "application/octet-stream",
            "x-upload-content-type": file.type || "application/octet-stream",
            ...(forwardedProto ? { "x-forwarded-proto": forwardedProto } : {}),
            ...(forwardedHost ? { "x-forwarded-host": forwardedHost } : {}),
          },
          body: buf,
        });
        const ct = res.headers.get("content-type") || "";
        if (ct.includes("application/json")) {
          const data = await res.json();
          return NextResponse.json(data, { status: res.status });
        }
        return new NextResponse(await res.text(), {
          status: res.status,
          headers: { "content-type": ct || "text/plain" },
        });
      } catch (error) {
        lastError = error instanceof Error ? error.message : "upload failed";
      }
    }
    return NextResponse.json(
      { error: "upstream_unreachable", message: lastError || "upload failed" },
      { status: 503 },
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : "upload failed";
    return NextResponse.json({ error: "upload_failed", message: msg }, { status: 500 });
  }
}
