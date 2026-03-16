import { NextRequest, NextResponse } from "next/server";
import { randomUUID } from "crypto";

type Stored = { bytes: Uint8Array; contentType: string };

// In-memory store (dev/local preview). Restarting dev server clears it.
const store: Map<string, Stored> = (globalThis as unknown as { __inksight_uploads?: Map<string, Stored> })
  .__inksight_uploads || new Map();
(globalThis as unknown as { __inksight_uploads?: Map<string, Stored> }).__inksight_uploads = store;

function getPublicOrigin(req: NextRequest): string {
  const forwardedProto = req.headers.get("x-forwarded-proto")?.split(",")[0]?.trim();
  const forwardedHost = req.headers.get("x-forwarded-host")?.split(",")[0]?.trim();
  const host = forwardedHost || req.headers.get("host")?.split(",")[0]?.trim();
  if (host) {
    const protocol = forwardedProto || req.nextUrl.protocol.replace(/:$/, "");
    return `${protocol}://${host}`;
  }
  return req.nextUrl.origin;
}

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
    // simple size guard (10MB)
    if (buf.byteLength > 10 * 1024 * 1024) {
      return NextResponse.json({ error: "file_too_large", message: "max 10MB" }, { status: 413 });
    }
    const id = randomUUID();
    store.set(id, { bytes: buf, contentType: file.type || "application/octet-stream" });
    const origin = getPublicOrigin(req);
    return NextResponse.json({ ok: true, id, url: `${origin}/api/uploads/${id}` });
  } catch (e) {
    const msg = e instanceof Error ? e.message : "upload failed";
    return NextResponse.json({ error: "upload_failed", message: msg }, { status: 500 });
  }
}

