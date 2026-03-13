import { NextRequest } from "next/server";
import { proxyGet, proxyPost } from "../_proxy";

export async function GET(req: NextRequest) {
  // 保留前端传入的查询参数（例如 ?mac=...），一并转发给后端
  const search = req.nextUrl.search || "";
  return proxyGet(`/api/modes${search}`, req);
}

export async function POST(req: NextRequest) {
  return proxyPost("/api/modes/custom", req);
}
