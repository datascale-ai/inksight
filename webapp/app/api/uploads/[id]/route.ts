import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest, ctx: { params: Promise<{ id: string }> }) {
  const { id } = await ctx.params;
  return proxyGet(`/api/uploads/${encodeURIComponent(id)}`, req);
}
