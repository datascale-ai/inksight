import { Alert, View } from 'react-native';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkButton } from '@/components/ui/InkButton';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { useAuthStore } from '@/features/auth/store';
import { approveDeviceAccessRequest, listDeviceAccessRequests, rejectDeviceAccessRequest } from '@/features/device/api';
import { useI18n } from '@/lib/i18n';

export default function DeviceRequestsScreen() {
  const { t } = useI18n();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const requestsQuery = useQuery({
    queryKey: ['device-access-requests', token],
    queryFn: () => listDeviceAccessRequests(token || ''),
    enabled: Boolean(token),
  });

  const approveMutation = useMutation({
    mutationFn: async (requestId: number) => approveDeviceAccessRequest(token || '', requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['device-access-requests', token] });
      Alert.alert(t('common.saved'), t('requests.approveSuccess'));
    },
    onError: (error) => Alert.alert(t('requests.approve'), error instanceof Error ? error.message : t('requests.approve')),
  });
  const rejectMutation = useMutation({
    mutationFn: async (requestId: number) => rejectDeviceAccessRequest(token || '', requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['device-access-requests', token] });
      Alert.alert(t('common.saved'), t('requests.rejectSuccess'));
    },
    onError: (error) => Alert.alert(t('requests.reject'), error instanceof Error ? error.message : t('requests.reject')),
  });

  return (
    <AppScreen>
      <InkText serif style={{ fontSize: 32, fontWeight: '600' }}>{t('requests.title')}</InkText>
      <InkText dimmed>{t('requests.subtitle')}</InkText>

      {(requestsQuery.data?.requests || []).length === 0 ? (
        <InkCard>
          <InkText dimmed>{t('requests.empty')}</InkText>
        </InkCard>
      ) : null}

      {(requestsQuery.data?.requests || []).map((request) => (
        <InkCard key={request.id}>
          <InkText style={{ fontSize: 16, fontWeight: '600' }}>{request.requester_username}</InkText>
          <InkText dimmed style={{ marginTop: 8 }}>{request.mac}</InkText>
          <InkText dimmed>{request.created_at}</InkText>
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 16 }}>
            <InkButton label={approveMutation.isPending ? t('common.loading') : t('requests.approve')} onPress={() => approveMutation.mutate(request.id)} />
            <InkButton label={rejectMutation.isPending ? t('common.loading') : t('requests.reject')} variant="secondary" onPress={() => rejectMutation.mutate(request.id)} />
          </View>
        </InkCard>
      ))}
    </AppScreen>
  );
}
