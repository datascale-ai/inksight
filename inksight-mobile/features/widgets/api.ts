import { apiRequest } from '@/lib/api-client';

export type WidgetPayload = {
  mac: string;
  mode_id: string;
  display_name: string;
  icon: string;
  updated_at: string;
  preview_url: string;
  content: Record<string, unknown>;
};

export async function getWidgetData(mac: string, token: string, mode?: string) {
  const params = new URLSearchParams();
  if (mode) {
    params.set('mode', mode);
  }
  const query = params.toString();
  return apiRequest<WidgetPayload>(`/widget/${encodeURIComponent(mac)}/data${query ? `?${query}` : ''}`, {
    token,
  });
}
