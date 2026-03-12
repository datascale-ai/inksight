import { NextRequest, NextResponse } from "next/server";

type Stored = { bytes: Uint8Array; contentType: string };

const store: Map<string, Stored> = (globalThis as unknown as { __inksight_uploads?: Map<string, Stored> })
  .__inksight_uploads || new Map();
(globalThis as unknown as { __inksight_uploads?: Map<string, Stored> }).__inksight_uploads = store;

export async function GET(_req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  const item = store.get(id);
  if (!item) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  const body = item.bytes.buffer.slice(
    item.bytes.byteOffset,
    item.bytes.byteOffset + item.bytes.byteLength,
  ) as ArrayBuffer;
  return new NextResponse(body, {
    status: 200,
    headers: {
      "content-type": item.contentType,
      "cache-control": "no-store",
    },
  });
}

