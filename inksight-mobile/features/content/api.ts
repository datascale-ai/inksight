import { apiRequest } from '@/lib/api-client';

export type TodayItem = {
  mode_id: string;
  display_name: string;
  icon: string;
  summary: string;
  content: Record<string, unknown>;
  preview_url: string;
  image_url: string;
};

export type TodayPayload = {
  generated_at: string;
  items: TodayItem[];
  date?: Record<string, unknown>;
  weather?: {
    weather_str?: string;
    city?: string;
    temp?: number;
  };
};

export async function getTodayContent(modes = ['DAILY', 'POETRY', 'WEATHER']) {
  const params = new URLSearchParams({
    modes: modes.join(','),
    limit: String(modes.length),
  });
  return apiRequest<TodayPayload>(`/content/today?${params.toString()}`);
}
