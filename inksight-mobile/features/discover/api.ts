import { apiRequest } from '@/lib/api-client';

export type DiscoverFeedMode = {
  mode_id: string;
  display_name: string;
  description: string;
  icon: string;
  source: string;
  badge?: string;
};

export type DiscoverSection = {
  id: string;
  title: string;
  subtitle: string;
  items: DiscoverFeedMode[];
};

export type DiscoverChip = {
  id: string;
  label: string;
};

export type DiscoverCtaLink = {
  id: string;
  title: string;
  description: string;
  route: string;
};

export type DiscoverFeed = {
  generated_at: string;
  scene_chips: DiscoverChip[];
  editorial_sections: DiscoverSection[];
  featured_modes: DiscoverFeedMode[];
  cta_links: DiscoverCtaLink[];
};

export async function getDiscoverFeed() {
  return apiRequest<DiscoverFeed>('/discover/feed');
}
