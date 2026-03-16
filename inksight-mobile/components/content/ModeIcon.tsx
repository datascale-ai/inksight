import type { LucideIcon } from 'lucide-react-native';
import {
  BookOpen,
  Brain,
  CalendarDays,
  CloudSun,
  Compass,
  Dumbbell,
  Feather,
  Image as ImageIcon,
  Newspaper,
  PenTool,
  Sparkles,
} from 'lucide-react-native';
import { theme } from '@/lib/theme';

const iconMap: Record<string, LucideIcon> = {
  DAILY: Sparkles,
  WEATHER: CloudSun,
  POETRY: Feather,
  ARTWALL: ImageIcon,
  BRIEFING: Newspaper,
  ZEN: Compass,
  STOIC: BookOpen,
  FITNESS: Dumbbell,
  ALMANAC: CalendarDays,
  CREATE: PenTool,
};

export function ModeIcon({ modeId, color = theme.colors.ink, size = 18 }: { modeId: string; color?: string; size?: number }) {
  const Icon = iconMap[modeId.toUpperCase()] || Brain;
  return <Icon color={color} size={size} strokeWidth={theme.strokeWidth} />;
}
