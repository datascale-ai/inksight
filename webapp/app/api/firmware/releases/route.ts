import { NextRequest } from "next/server";
import { proxyFirmwareApi } from "../_shared";

export async function GET(req: NextRequest) {
  const refresh = req.nextUrl.searchParams.get("refresh");
  const query = refresh ? `?refresh=${encodeURIComponent(refresh)}` : "";
  return proxyFirmwareApi(`/api/firmware/releases${query}`);
}
