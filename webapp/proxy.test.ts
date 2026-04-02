import assert from "node:assert/strict";
import test from "node:test";
import { NextRequest } from "next/server";

import { proxy } from "./proxy";

test("proxy rejects unknown hosts", () => {
  const req = new NextRequest("https://zhigu.chat/api/preview", {
    headers: {
      host: "zhigu.chat",
      "x-forwarded-host": "zhigu.chat",
      "x-forwarded-proto": "https",
    },
  });

  const res = proxy(req);

  assert.equal(res.status, 404);
});

test("proxy rejects backend-only host on the web app", () => {
  const req = new NextRequest("https://web.inksight.site/config", {
    headers: {
      host: "web.inksight.site",
      "x-forwarded-host": "web.inksight.site",
      "x-forwarded-proto": "https",
    },
  });

  const res = proxy(req);

  assert.equal(res.status, 404);
});

test("proxy allows official hosts", () => {
  const req = new NextRequest("https://www.inksight.site/config", {
    headers: {
      host: "www.inksight.site",
      "x-forwarded-host": "www.inksight.site",
      "x-forwarded-proto": "https",
    },
  });

  const res = proxy(req);

  assert.equal(res.status, 307);
  assert.equal(res.headers.get("location"), "https://www.inksight.site/zh/config");
});

test("proxy allows localhost development hosts", () => {
  const req = new NextRequest("http://localhost:3000/api/preview", {
    headers: {
      host: "localhost:3000",
    },
  });

  const res = proxy(req);

  assert.equal(res.status, 200);
});
