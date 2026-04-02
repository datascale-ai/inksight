export type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

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

    if (!onlineNow) {
      return { onlineNow: false, lastSeen, refreshQueued: false };
    }

    try {
      await fetchImpl(`/api/device/${encodeURIComponent(mac)}/refresh`, {
        cache: "no-store",
        method: "POST",
        headers,
      });
      return { onlineNow: true, lastSeen, refreshQueued: true };
    } catch {
      return { onlineNow: true, lastSeen, refreshQueued: false };
    }
  } catch {
    return { onlineNow: null, lastSeen: null, refreshQueued: false };
  }
}
