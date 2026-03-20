import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  // forward query params e.g. ?mac=...
  const search = req.nextUrl.search || "";
  return proxyGet(`/api/modes/catalog${search}`, req);
}

