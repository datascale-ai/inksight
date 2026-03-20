import { NextRequest } from "next/server";

import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const search = req.nextUrl.search || "";
  return proxyGet(`/api/locations/search${search}`, req);
}
