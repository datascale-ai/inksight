import { NextRequest } from "next/server";
import { proxyGet } from "../../../_proxy";

export async function GET(req: NextRequest) {
  return proxyGet("/api/admin/analytics/overview", req);
}
