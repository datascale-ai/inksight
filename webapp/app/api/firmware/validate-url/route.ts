import { NextRequest } from "next/server";
import { proxyFirmwareApi } from "../_shared";

export async function GET(req: NextRequest) {
  const url = req.nextUrl.searchParams.get("url");
  if (!url) {
    return Response.json(
      { error: "invalid_request", message: "missing url query param" },
      { status: 400 }
    );
  }
  return proxyFirmwareApi(`/api/firmware/validate-url?url=${encodeURIComponent(url)}`);
}
