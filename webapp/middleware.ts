import type { NextRequest } from "next/server";
import { proxy } from "./proxy";

export function middleware(req: NextRequest) {
  return proxy(req);
}

export { config } from "./proxy";
