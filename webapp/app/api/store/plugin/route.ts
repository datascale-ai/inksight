import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const url = request.nextUrl.searchParams.get("url");
  if (!url) {
    return NextResponse.json(
      { error: "Missing url parameter" },
      { status: 400 },
    );
  }

  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      return NextResponse.json(
        { error: `Failed to fetch: ${resp.status}` },
        { status: resp.status },
      );
    }
    const data = await resp.json();
    return NextResponse.json(data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Failed to fetch plugin";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
