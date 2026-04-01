import { NextRequest } from "next/server";
import { proxyGet, proxyDelete } from "../../../_proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ modeId: string }> },
) {
  const { modeId } = await params;
  return proxyGet(`/api/modes/custom/${encodeURIComponent(modeId)}${req.nextUrl.search}`, req);
}

export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ modeId: string }> },
) {
  const { modeId } = await params;
  return proxyDelete(`/api/modes/custom/${encodeURIComponent(modeId)}${req.nextUrl.search}`, req);
}
