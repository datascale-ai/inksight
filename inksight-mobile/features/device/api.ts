import { apiFetch, apiRequest, buildApiUrl } from '@/lib/api-client';

export type DeviceSummary = {
  mac: string;
  nickname?: string;
  role?: string;
  status?: string;
};

export type DeviceState = {
  mac: string;
  battery_pct?: number;
  battery_voltage?: number;
  last_persona?: string;
  runtime_mode?: string;
  last_seen?: string;
  is_online?: boolean;
  refresh_minutes?: number;
};

export type DeviceContentItem = {
  id: number;
  mode_id: string;
  content: Record<string, unknown>;
  is_favorite?: boolean;
  time: string;
};

export type DeviceConfig = {
  id?: number;
  mac: string;
  nickname?: string;
  modes: string[];
  refreshInterval?: number;
  refreshStrategy?: string;
  language?: string;
  contentTone?: string;
  city?: string;
  llmProvider?: string;
  llmModel?: string;
  modeOverrides?: Record<string, Record<string, unknown>>;
};

export type DeviceMember = {
  user_id: number;
  username: string;
  role: string;
  status: string;
  nickname?: string;
  granted_by?: number;
  created_at?: string;
  updated_at?: string;
};

export type DeviceClaimResult = {
  ok: boolean;
  status: string;
  mac?: string;
  role?: string;
};

export type DeviceAccessRequest = {
  id: number;
  mac: string;
  requester_user_id: number;
  requester_username: string;
  status: string;
  created_at?: string;
  updated_at?: string;
};

export type FirmwareRelease = {
  version: string;
  tag: string;
  published_at?: string;
  download_url?: string;
  size_bytes?: number;
  chip_family?: string;
  asset_name?: string;
  manifest?: Record<string, unknown>;
};

export async function listUserDevices(token: string) {
  return apiRequest<{ devices: DeviceSummary[] }>('/user/devices', { token });
}

export async function getDeviceState(mac: string, token: string) {
  return apiRequest<DeviceState>(`/device/${encodeURIComponent(mac)}/state`, { token });
}

export async function getDeviceConfig(mac: string, token: string) {
  return apiRequest<DeviceConfig>(`/config/${encodeURIComponent(mac)}`, { token });
}

export async function saveDeviceConfig(token: string, body: DeviceConfig) {
  return apiRequest<{ ok: boolean; config_id: number }>('/config', {
    method: 'POST',
    token,
    body,
  });
}

export async function getDeviceHistory(mac: string, token: string) {
  return apiRequest<{ mac: string; history: DeviceContentItem[] }>(`/device/${encodeURIComponent(mac)}/history`, {
    token,
  });
}

export async function getDeviceFavorites(mac: string, token: string) {
  return apiRequest<{ mac: string; favorites: DeviceContentItem[] }>(`/device/${encodeURIComponent(mac)}/favorites`, {
    token,
  });
}

export async function refreshDevice(mac: string, token: string) {
  return apiRequest<{ ok: boolean; message: string }>(`/device/${encodeURIComponent(mac)}/refresh`, {
    method: 'POST',
    token,
  });
}

export async function switchDeviceMode(mac: string, token: string, mode: string) {
  return apiRequest<{ ok: boolean; message: string }>(`/device/${encodeURIComponent(mac)}/switch`, {
    method: 'POST',
    token,
    body: { mode },
  });
}

export async function listDeviceMembers(mac: string, token: string) {
  return apiRequest<{ mac: string; members: DeviceMember[]; owner_user_id?: number }>(
    `/user/devices/${encodeURIComponent(mac)}/members`,
    { token },
  );
}

export async function shareDeviceMember(mac: string, token: string, username: string) {
  return apiRequest<{ ok: boolean; status: string; membership?: DeviceMember }>(
    `/user/devices/${encodeURIComponent(mac)}/share`,
    {
      method: 'POST',
      token,
      body: { username },
    },
  );
}

export async function removeDeviceMember(mac: string, token: string, targetUserId: number) {
  return apiRequest<{ ok: boolean }>(`/user/devices/${encodeURIComponent(mac)}/members/${targetUserId}`, {
    method: 'DELETE',
    token,
  });
}

export async function claimDevice(token: string, body: { token?: string; pair_code?: string }) {
  return apiRequest<DeviceClaimResult>('/claim/consume', {
    method: 'POST',
    token,
    body,
  });
}

export async function getLatestFirmwareRelease() {
  return apiRequest<{ source?: string; repo?: string; cached?: boolean; latest?: FirmwareRelease }>(
    '/firmware/releases/latest',
  );
}

export async function validateFirmwareUrl(url: string) {
  const params = new URLSearchParams({ url });
  return apiRequest<{ reachable: boolean; final_url?: string; status_code?: number }>(`/firmware/validate-url?${params.toString()}`);
}

export async function favoriteDeviceContent(mac: string, token: string, mode?: string) {
  return apiRequest<{ ok: boolean; message: string; mode_id?: string }>(`/device/${encodeURIComponent(mac)}/favorite`, {
    method: 'POST',
    token,
    body: mode ? { mode } : {},
  });
}

export async function pushPreviewToDevice(mac: string, token: string, previewUrl: string, mode?: string) {
  const previewResponse = await apiFetch(buildApiUrl(previewUrl), {
    token,
    contentType: null,
  });
  if (!previewResponse.ok) {
    throw new Error(`Preview fetch failed: ${previewResponse.status}`);
  }
  const previewBytes = await previewResponse.arrayBuffer();
  const query = mode ? `?mode=${encodeURIComponent(mode)}` : '';
  const response = await apiFetch(`/device/${encodeURIComponent(mac)}/apply-preview${query}`, {
    method: 'POST',
    token,
    contentType: 'image/png',
    body: previewBytes,
  });

  if (!response.ok) {
    let message = `Push preview failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.message || payload.error || message;
    } catch {
      // Ignore JSON parse failures.
    }
    throw new Error(message);
  }

  return response.json() as Promise<{ ok: boolean; message: string }>;
}

export async function pushPreviewImageToDevice(mac: string, token: string, previewBytes: ArrayBuffer, mode?: string) {
  const query = mode ? `?mode=${encodeURIComponent(mode)}` : '';
  const response = await apiFetch(`/device/${encodeURIComponent(mac)}/apply-preview${query}`, {
    method: 'POST',
    token,
    contentType: 'image/png',
    body: previewBytes,
  });

  if (!response.ok) {
    let message = `Push preview failed: ${response.status}`;
    try {
      const payload = await response.json();
      message = payload.message || payload.error || message;
    } catch {
    }
    throw new Error(message);
  }

  return response.json() as Promise<{ ok: boolean; message: string }>;
}

export function getDeviceShareImageUrl(mac: string, width = 800, height = 450) {
  const params = new URLSearchParams({
    w: String(width),
    h: String(height),
  });
  return buildApiUrl(`/device/${encodeURIComponent(mac)}/share?${params.toString()}`);
}

export async function listDeviceAccessRequests(token: string) {
  return apiRequest<{ requests: DeviceAccessRequest[] }>('/user/devices/requests', { token });
}

export async function approveDeviceAccessRequest(token: string, requestId: number) {
  return apiRequest<{ ok: boolean; membership?: DeviceMember }>(`/user/devices/requests/${requestId}/approve`, {
    method: 'POST',
    token,
  });
}

export async function rejectDeviceAccessRequest(token: string, requestId: number) {
  return apiRequest<{ ok: boolean }>(`/user/devices/requests/${requestId}/reject`, {
    method: 'POST',
    token,
  });
}
