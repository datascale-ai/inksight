import { NextRequest } from "next/server";
import { proxyGet } from "../../_proxy";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ mac: string }> },
) {
  const { mac } = await params;
  // Next.js 13+ 动态路由参数已经自动解码，需要重新编码
  // MAC 地址格式：88:56:A6:7B:C7:0C，需要编码冒号
  const encodedMac = encodeURIComponent(mac);
  return proxyGet(`/api/config/${encodedMac}`, req);
}
