import { useState } from 'react';
import { Alert, StyleSheet, TextInput, View } from 'react-native';
import { useLocalSearchParams } from 'expo-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { listDeviceMembers, removeDeviceMember, shareDeviceMember } from '@/features/device/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

export default function DeviceMembersScreen() {
  const { t } = useI18n();
  const { mac } = useLocalSearchParams<{ mac: string }>();
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();
  const [username, setUsername] = useState('');

  const membersQuery = useQuery({
    queryKey: ['device-members', mac, token],
    queryFn: () => listDeviceMembers(mac || '', token || ''),
    enabled: Boolean(mac && token),
  });

  const shareMutation = useMutation({
    mutationFn: async () => shareDeviceMember(mac || '', token || '', username.trim()),
    onSuccess: () => {
      setUsername('');
      queryClient.invalidateQueries({ queryKey: ['device-members', mac, token] });
      Alert.alert(t('members.inviteSuccessTitle'), t('members.inviteSuccess'));
    },
    onError: (error) => Alert.alert(t('members.inviteSubmit'), error instanceof Error ? error.message : t('members.inviteSubmit')),
  });

  const removeMutation = useMutation({
    mutationFn: async (userId: number) => removeDeviceMember(mac || '', token || '', userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['device-members', mac, token] });
      Alert.alert(t('members.removeSuccessTitle'), t('members.removeSuccess'));
    },
    onError: (error) => Alert.alert(t('members.remove'), error instanceof Error ? error.message : t('members.remove')),
  });

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{t('members.title')}</InkText>
      <InkText dimmed>{t('members.subtitle')}</InkText>

      <InkCard>
        <InkText style={styles.label}>{t('members.inviteLabel')}</InkText>
        <TextInput value={username} onChangeText={setUsername} placeholder={t('members.invitePlaceholder')} style={styles.input} autoCapitalize="none" />
        <InkButton
          label={shareMutation.isPending ? t('common.loading') : t('members.inviteSubmit')}
          block
          onPress={() => shareMutation.mutate()}
          disabled={!token || !username.trim() || shareMutation.isPending}
        />
      </InkCard>

      {(membersQuery.data?.members || []).map((member) => (
        <InkCard key={member.user_id}>
          <View style={styles.memberRow}>
            <View style={styles.memberText}>
              <InkText style={styles.memberName}>{member.username}</InkText>
              <InkText dimmed>{member.role === 'owner' ? t('members.owner') : t('members.member')}</InkText>
            </View>
            {member.role !== 'owner' ? (
              <InkButton
                label={removeMutation.isPending ? t('common.loading') : t('members.remove')}
                variant="secondary"
                onPress={() => removeMutation.mutate(member.user_id)}
              />
            ) : null}
          </View>
        </InkCard>
      ))}
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  label: {
    marginBottom: 8,
    fontWeight: '600',
  },
  input: {
    height: 50,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    marginBottom: 14,
    color: theme.colors.ink,
  },
  memberRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
  },
  memberText: {
    flex: 1,
  },
  memberName: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 4,
  },
});
