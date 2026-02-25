import { NextResponse } from "next/server";

const PLUGIN_INDEX_URL =
  process.env.PLUGIN_INDEX_URL ||
  "https://raw.githubusercontent.com/datascale-ai/inksight-plugins/main/index.json";

export async function GET() {
  try {
    const resp = await fetch(PLUGIN_INDEX_URL, {
      next: { revalidate: 300 },
    });
    if (!resp.ok) {
      return NextResponse.json(
        { error: "Failed to fetch plugin index" },
        { status: resp.status },
      );
    }
    const data = await resp.json();
    return NextResponse.json(data);
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : "Failed to fetch plugins";
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
