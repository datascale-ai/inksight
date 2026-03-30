import { useMemo } from 'react';
import { useLocalSearchParams, router } from 'expo-router';
import { useQuery } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { ModeIcon } from '@/components/content/ModeIcon';
import { listModes } from '@/features/modes/api';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';

export default function BrowseDetailScreen() {
  const { t } = useI18n();
  const params = useLocalSearchParams<{
    id: string;
    kind?: string;
    title?: string;
    summary?: string;
    time?: string;
  }>();
  const token = useAuthStore((state) => state.token);
  const modeId = decodeURIComponent(params.id || '');
  const kind = params.kind || 'content';

  const modesQuery = useQuery({
    queryKey: ['browse-detail-modes'],
    queryFn: listModes,
    enabled: kind === 'mode',
  });

  const mode = useMemo(
    () => modesQuery.data?.modes.find((item) => item.mode_id === modeId),
    [modesQuery.data, modeId],
  );

  return (
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>
        {decodeURIComponent(params.title || mode?.display_name || modeId || t('nav.detail'))}
      </InkText>

      <InkCard>
        {kind === 'mode' ? <ModeIcon modeId={modeId} /> : null}
        <InkText style={{ marginTop: kind === 'mode' ? 12 : 0, fontSize: 16, fontWeight: '600' }}>
          {kind === 'mode' ? mode?.display_name || modeId : decodeURIComponent(params.title || t('nav.detail'))}
        </InkText>
        <InkText dimmed style={{ marginTop: 8, lineHeight: 24 }}>
          {decodeURIComponent(params.summary || mode?.description || t('browse.detail.default'))}
        </InkText>
        {params.time ? <InkText dimmed style={{ marginTop: 12 }}>{decodeURIComponent(params.time)}</InkText> : null}
      </InkCard>

      {kind === 'mode' ? (
        <InkButton
          label={token ? t('browse.detail.rewrite') : t('browse.detail.loginToSave')}
          variant="secondary"
          block
          onPress={() => router.push(token ? `/create/generate?template=${encodeURIComponent(modeId)}` : '/login')}
        />
      ) : (
        <InkButton label={t('browse.detail.back')} block onPress={() => router.back()} />
      )}
    </AppScreen>
  );
}
