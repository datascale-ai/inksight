import assert from "node:assert/strict";
import test from "node:test";
import { NextRequest } from "next/server";

import { POST } from "./route";

test("POST returns public upload URL from forwarded host and proto", async () => {
  const form = new FormData();
  form.append("file", new File([new Uint8Array([137, 80, 78, 71])], "tiny.png", { type: "image/png" }));

  const req = new NextRequest("http://localhost:3000/api/uploads", {
    method: "POST",
    body: form,
    headers: {
      host: "localhost:3000",
      "x-forwarded-host": "www.inksight.site",
      "x-forwarded-proto": "https",
    },
  });

  const res = await POST(req);
  const data = await res.json();

  assert.equal(res.status, 200);
  assert.match(String(data.url), /^https:\/\/www\.inksight\.site\/api\/uploads\/.+$/);
});
