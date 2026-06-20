export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

export function calculateBatteryPct(voltage: number | null | undefined): number | null {
  if (typeof voltage !== "number" || !Number.isFinite(voltage)) return null;

  const fullVoltage = 4.2;
  const highVoltage = 3.7;
  const lowVoltage = 3.0;
  const pct = voltage >= highVoltage
    ? ((voltage - highVoltage) / (fullVoltage - highVoltage)) * 50 + 50
    : ((voltage - lowVoltage) / (highVoltage - lowVoltage)) * 50;

  return Math.min(100, Math.max(0, Math.round(pct)));
}

export async function queueImmediateRefreshIfOnline(
  fetchImpl: FetchLike,
  mac: string,
  headers: Record<string, string>,
): Promise<{ onlineNow: boolean | null; lastSeen: string | null; refreshQueued: boolean }> {
  try {
    const stateRes = await fetchImpl(`/api/device/${encodeURIComponent(mac)}/state`, {
      cache: "no-store",
      headers,
    });
    if (!stateRes.ok) {
      return { onlineNow: null, lastSeen: null, refreshQueued: false };
    }
    const stateData = await stateRes.json();
    const onlineNow = Boolean(stateData?.is_online);
    const lastSeen = typeof stateData?.last_seen === "string" && stateData.last_seen ? stateData.last_seen : null;
    const runtimeMode = typeof stateData?.runtime_mode === "string" ? stateData.runtime_mode.toLowerCase() : "";

    if (!onlineNow || runtimeMode === "interval") {
      return { onlineNow: false, lastSeen, refreshQueued: false };
    }

    try {
      const refreshRes = await fetchImpl(`/api/device/${encodeURIComponent(mac)}/refresh`, {
        cache: "no-store",
        method: "POST",
        headers,
      });
      return { onlineNow: true, lastSeen, refreshQueued: refreshRes.ok };
    } catch {
      return { onlineNow: true, lastSeen, refreshQueued: false };
    }
  } catch {
    return { onlineNow: null, lastSeen: null, refreshQueued: false };
  }
}
