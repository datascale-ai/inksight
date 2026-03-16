import { useMemo, useState } from 'react';
import { Alert, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { Eye, EyeOff } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { useAuthStore } from '@/features/auth/store';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

type Props = {
  initialMode?: 'login' | 'register';
};

type FormErrors = {
  username?: string;
  password?: string;
  confirm?: string;
};

export function AuthFormScreen({ initialMode = 'login' }: Props) {
  const { t } = useI18n();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [mode, setMode] = useState<'login' | 'register'>(initialMode);
  const signIn = useAuthStore((state) => state.signIn);
  const loading = useAuthStore((state) => state.loading);

  const title = useMemo(() => (mode === 'login' ? t('auth.loginTitle') : t('auth.registerTitle')), [mode, t]);

  function validate(): FormErrors | null {
    const errs: FormErrors = {};
    const trimmed = username.trim();
    if (trimmed.length < 3) {
      errs.username = t('auth.errorUsernameMin');
    } else if (!/^[a-zA-Z0-9_]+$/.test(trimmed)) {
      errs.username = t('auth.errorUsernameFormat');
    }
    if (password.length < 6) {
      errs.password = t('auth.errorPasswordMin');
    }
    if (mode === 'register' && password !== confirmPassword) {
      errs.confirm = t('auth.errorPasswordMatch');
    }
    return Object.keys(errs).length > 0 ? errs : null;
  }

  async function handleSubmit() {
    const validationErrors = validate();
    if (validationErrors) {
      setErrors(validationErrors);
      return;
    }
    setErrors({});
    try {
      await signIn(username.trim(), password, mode);
      router.replace('/(tabs)/me');
    } catch (error) {
      Alert.alert(mode === 'login' ? t('auth.loginError') : t('auth.registerError'), error instanceof Error ? error.message : t('common.loading'));
    }
  }

  function handleModeSwitch() {
    setMode((current) => (current === 'login' ? 'register' : 'login'));
    setErrors({});
    setConfirmPassword('');
  }

  return (
    <AppScreen>
      <InkText serif style={styles.title}>{title}</InkText>
      <InkText dimmed>{t('auth.subtitle')}</InkText>

      <InkCard>
        <View style={styles.segment}>
          <InkButton label={t('auth.login')} variant={mode === 'login' ? 'primary' : 'secondary'} onPress={() => { setMode('login'); setErrors({}); setConfirmPassword(''); }} />
          <InkButton label={t('auth.register')} variant={mode === 'register' ? 'primary' : 'secondary'} onPress={() => { setMode('register'); setErrors({}); }} />
        </View>

        <TextInput
          value={username}
          onChangeText={(text) => { setUsername(text); if (errors.username) setErrors((prev) => ({ ...prev, username: undefined })); }}
          placeholder={t('auth.username')}
          style={[styles.input, errors.username ? styles.inputError : null]}
          autoCapitalize="none"
        />
        {errors.username ? <InkText style={styles.errorText}>{errors.username}</InkText> : null}

        <View style={styles.passwordWrap}>
          <TextInput
            value={password}
            onChangeText={(text) => { setPassword(text); if (errors.password) setErrors((prev) => ({ ...prev, password: undefined })); }}
            placeholder={t('auth.password')}
            secureTextEntry={!showPassword}
            style={[styles.input, styles.passwordInput, errors.password ? styles.inputError : null]}
          />
          <Pressable onPress={() => setShowPassword((prev) => !prev)} style={styles.eyeButton}>
            {showPassword
              ? <EyeOff size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
              : <Eye size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
            }
          </Pressable>
        </View>
        {errors.password ? <InkText style={styles.errorText}>{errors.password}</InkText> : null}

        {mode === 'register' ? (
          <>
            <View style={styles.passwordWrap}>
              <TextInput
                value={confirmPassword}
                onChangeText={(text) => { setConfirmPassword(text); if (errors.confirm) setErrors((prev) => ({ ...prev, confirm: undefined })); }}
                placeholder={t('auth.confirmPassword')}
                secureTextEntry={!showPassword}
                style={[styles.input, styles.passwordInput, errors.confirm ? styles.inputError : null]}
              />
            </View>
            {errors.confirm ? <InkText style={styles.errorText}>{errors.confirm}</InkText> : null}
          </>
        ) : null}

        <InkButton
          label={loading ? t('auth.processing') : mode === 'login' ? t('auth.login') : t('auth.createAccount')}
          block
          onPress={handleSubmit}
          disabled={loading || !username.trim() || !password}
        />
        <InkButton
          label={mode === 'login' ? t('auth.switchToRegister') : t('auth.switchToLogin')}
          block
          variant="ghost"
          onPress={handleModeSwitch}
          style={styles.switchButton}
        />
      </InkCard>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  segment: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 16,
  },
  input: {
    height: 52,
    borderRadius: theme.radius.md,
    backgroundColor: theme.colors.surface,
    paddingHorizontal: 16,
    marginBottom: 12,
    color: theme.colors.ink,
  },
  inputError: {
    borderWidth: 1,
    borderColor: theme.colors.danger,
    marginBottom: 4,
  },
  errorText: {
    color: theme.colors.danger,
    fontSize: 12,
    marginBottom: 12,
    marginLeft: 4,
  },
  passwordWrap: {
    position: 'relative',
  },
  passwordInput: {
    paddingRight: 48,
  },
  eyeButton: {
    position: 'absolute',
    right: 12,
    top: 0,
    height: 52,
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  switchButton: {
    marginTop: 8,
  },
});
