import { NextRequest } from "next/server";
import { proxyPost } from "../../../../_proxy";

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  return proxyPost(`/api/discover/modes/${id}/install`, req);
}
