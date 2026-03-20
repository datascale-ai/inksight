import { NextRequest } from "next/server";
import { proxyPatch } from "../../../_proxy";

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ mac: string }> },
) {
  const { mac } = await params;
  const encodedMac = encodeURIComponent(mac);
  const search = req.nextUrl.search || "";
  return proxyPatch(`/api/config/${encodedMac}/focus-listening${search}`, req);
}

