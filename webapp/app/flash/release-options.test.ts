import assert from "node:assert/strict";
import test from "node:test";

import { buildReleaseKey, buildReleaseLabel, getPreferredBuild } from "./release-options";

test("buildReleaseKey uses version and asset name", () => {
  assert.equal(
    buildReleaseKey({ version: "0.3", asset_name: "epd_42_wroom32e.bin" }),
    "0.3::epd_42_wroom32e.bin",
  );
});

test("buildReleaseLabel shows version with asset stem", () => {
  assert.equal(
    buildReleaseLabel({ version: "0.3", asset_name: "epd_42_wroom32e.bin" }),
    "v0.3(epd_42_wroom32e)",
  );
});

test("getPreferredBuild returns first build for selected asset", () => {
  const build = getPreferredBuild({
    version: "0.3",
    manifest: {
      builds: [
        { chipFamily: "ESP32", parts: [{ path: "https://example.com/fw.bin", offset: 0 }] },
      ],
    },
  });

  assert.equal(build?.chipFamily, "ESP32");
  assert.equal(build?.parts[0]?.path, "https://example.com/fw.bin");
});
