import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const query = searchParams.toString();
  const path = query ? `/api/discover/modes?${query}` : "/api/discover/modes";
  return proxyGet(path, req);
}
