import { NextRequest } from "next/server";
import { proxyStream } from "../../_proxy";

export async function GET(req: NextRequest) {
  const qs = req.nextUrl.search;
  return proxyStream(`/api/preview/stream${qs}`, req);
}
