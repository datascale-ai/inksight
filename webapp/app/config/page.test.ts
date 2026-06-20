import assert from "node:assert/strict";
import test from "node:test";

import { calculateBatteryPct, queueImmediateRefreshIfOnline } from "@/lib/device-utils";

test("calculateBatteryPct uses the lithium battery voltage curve", () => {
  assert.equal(calculateBatteryPct(null), null);
  assert.equal(calculateBatteryPct(Number.NaN), null);
  assert.equal(calculateBatteryPct(2.9), 0);
  assert.equal(calculateBatteryPct(3.0), 0);
  assert.equal(calculateBatteryPct(3.35), 25);
  assert.equal(calculateBatteryPct(3.7), 50);
  assert.equal(calculateBatteryPct(3.85), 65);
  assert.equal(calculateBatteryPct(4.0), 80);
  assert.equal(calculateBatteryPct(4.2), 100);
  assert.equal(calculateBatteryPct(4.3), 100);
});

test("queueImmediateRefreshIfOnline triggers refresh for online device", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state") {
      return {
        ok: true,
        json: async () => ({
          is_online: true,
          last_seen: "2026-03-16T10:00:00",
        }),
      } as Response;
    }
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/refresh") {
      return {
        ok: true,
      } as Response;
    }
    throw new Error(`unexpected url: ${url}`);
  };

  const result = await queueImmediateRefreshIfOnline(fetchImpl, "AA:BB:CC:DD:EE:FF", {
    Authorization: "Bearer test",
  });

  assert.equal(result.onlineNow, true);
  assert.equal(result.refreshQueued, true);
  assert.equal(result.lastSeen, "2026-03-16T10:00:00");
  assert.deepEqual(
    calls.map((call) => call.url),
    [
      "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state",
      "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/refresh",
    ],
  );
});

test("queueImmediateRefreshIfOnline skips refresh for offline device", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state") {
      return {
        ok: true,
        json: async () => ({
          is_online: false,
          last_seen: null,
        }),
      } as Response;
    }
    throw new Error(`unexpected url: ${url}`);
  };

  const result = await queueImmediateRefreshIfOnline(fetchImpl, "AA:BB:CC:DD:EE:FF", {
    Authorization: "Bearer test",
  });

  assert.equal(result.onlineNow, false);
  assert.equal(result.refreshQueued, false);
  assert.equal(result.lastSeen, null);
  assert.deepEqual(
    calls.map((call) => call.url),
    ["/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state"],
  );
});

test("queueImmediateRefreshIfOnline skips refresh for interval runtime mode", async () => {
  const calls: Array<{ url: string; init?: RequestInit }> = [];
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push({ url, init });
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state") {
      return {
        ok: true,
        json: async () => ({
          is_online: true,
          last_seen: "2026-03-16T10:00:00",
          runtime_mode: "interval",
        }),
      } as Response;
    }
    throw new Error(`unexpected url: ${url}`);
  };

  const result = await queueImmediateRefreshIfOnline(fetchImpl, "AA:BB:CC:DD:EE:FF", {
    Authorization: "Bearer test",
  });

  assert.equal(result.onlineNow, false);
  assert.equal(result.refreshQueued, false);
  assert.equal(result.lastSeen, "2026-03-16T10:00:00");
  assert.deepEqual(
    calls.map((call) => call.url),
    ["/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state"],
  );
});

test("queueImmediateRefreshIfOnline reports refresh failure for online device", async () => {
  const fetchImpl = async (url: string) => {
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/state") {
      return {
        ok: true,
        json: async () => ({
          is_online: true,
          last_seen: "2026-03-16T10:00:00",
        }),
      } as Response;
    }
    if (url === "/api/device/AA%3ABB%3ACC%3ADD%3AEE%3AFF/refresh") {
      return {
        ok: false,
      } as Response;
    }
    throw new Error(`unexpected url: ${url}`);
  };

  const result = await queueImmediateRefreshIfOnline(fetchImpl, "AA:BB:CC:DD:EE:FF", {
    Authorization: "Bearer test",
  });

  assert.equal(result.onlineNow, true);
  assert.equal(result.refreshQueued, false);
  assert.equal(result.lastSeen, "2026-03-16T10:00:00");
});

test("queueImmediateRefreshIfOnline leaves online status unknown when state lookup fails", async () => {
  const fetchImpl = async () => {
    throw new Error("network error");
  };

  const result = await queueImmediateRefreshIfOnline(fetchImpl, "AA:BB:CC:DD:EE:FF", {
    Authorization: "Bearer test",
  });

  assert.equal(result.onlineNow, null);
  assert.equal(result.refreshQueued, false);
  assert.equal(result.lastSeen, null);
});
