import { useEffect, useRef, useState } from 'react';
import { Alert, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowLeft, Eye, EyeOff } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { sendResetCode, resetPasswordWithCode } from '@/features/auth/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

type FormErrors = {
  email?: string;
  code?: string;
  password?: string;
  confirm?: string;
};

export function ForgotPasswordForm() {
  const { t } = useI18n();

  const [step, setStep] = useState<'email' | 'verify'>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  function startCooldown() {
    setCooldown(60);
    timerRef.current = setInterval(() => {
      setCooldown((prev) => { if (prev <= 1) { if (timerRef.current) clearInterval(timerRef.current); return 0; } return prev - 1; });
    }, 1000);
  }

  async function handleSendCode() {
    const e = email.trim();
    if (!e || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) {
      setErrors({ email: t('auth.errorEmailFormat') });
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      await sendResetCode(e);
      setStep('verify');
      startCooldown();
    } catch (err) {
      Alert.alert(t('auth.forgotPasswordError'), err instanceof Error ? err.message : t('common.loading'));
    } finally {
      setLoading(false);
    }
  }

  async function handleReset() {
    const errs: FormErrors = {};
    if (!code.trim()) errs.code = t('auth.errorCodeRequired');
    if (newPassword.length < 6) errs.password = t('auth.errorPasswordMin');
    if (newPassword !== confirmPassword) errs.confirm = t('auth.errorPasswordMismatch');
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setErrors({});
    setLoading(true);
    try {
      await resetPasswordWithCode(email.trim(), code.trim(), newPassword);
      Alert.alert(t('auth.forgotPasswordSuccess'), t('auth.forgotPasswordSuccessMessage'), [
        { text: t('common.confirm'), onPress: () => router.replace('/login') },
      ]);
    } catch (err) {
      Alert.alert(t('auth.forgotPasswordError'), err instanceof Error ? err.message : t('common.loading'));
    } finally {
      setLoading(false);
    }
  }

  return (
    <AppScreen>
      <Pressable onPress={() => router.back()} style={styles.backButton}>
        <ArrowLeft size={22} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
      </Pressable>

      <InkText serif style={styles.title}>{t('auth.forgotPassword')}</InkText>
      <InkText dimmed style={styles.subtitle}>{t('auth.forgotPasswordHintEmail')}</InkText>

      <InkCard>
        <TextInput
          value={email}
          onChangeText={(text) => { setEmail(text); if (errors.email) setErrors((prev) => ({ ...prev, email: undefined })); }}
          placeholder={t('auth.emailRequired')}
          style={[styles.input, errors.email ? styles.inputError : null]}
          keyboardType="email-address"
          autoCapitalize="none"
          editable={step === 'email'}
        />
        {errors.email ? <InkText style={styles.errorText}>{errors.email}</InkText> : null}

        {step === 'email' ? (
          <InkButton
            label={loading ? t('auth.processing') : t('auth.sendCode')}
            block
            onPress={handleSendCode}
            disabled={loading || !email.trim()}
          />
        ) : (
          <>
            <View style={styles.codeRow}>
              <TextInput
                value={code}
                onChangeText={(text) => { setCode(text); if (errors.code) setErrors((prev) => ({ ...prev, code: undefined })); }}
                placeholder={t('auth.verificationCode')}
                style={[styles.input, styles.codeInput, errors.code ? styles.inputError : null]}
                keyboardType="number-pad"
                maxLength={6}
              />
              <InkButton
                label={cooldown > 0 ? `${cooldown}s` : t('auth.resendCode')}
                variant="secondary"
                onPress={handleSendCode}
                disabled={cooldown > 0 || loading}
                style={styles.resendButton}
              />
            </View>
            {errors.code ? <InkText style={styles.errorText}>{errors.code}</InkText> : null}

            <View style={styles.passwordWrap}>
              <TextInput
                value={newPassword}
                onChangeText={(text) => { setNewPassword(text); if (errors.password) setErrors((prev) => ({ ...prev, password: undefined })); }}
                placeholder={t('auth.newPassword')}
                secureTextEntry={!showPassword}
                style={[styles.input, styles.passwordInput, errors.password ? styles.inputError : null]}
              />
              <Pressable onPress={() => setShowPassword((prev) => !prev)} style={styles.eyeButton}>
                {showPassword
                  ? <EyeOff size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />
                  : <Eye size={18} color={theme.colors.secondary} strokeWidth={theme.strokeWidth} />}
              </Pressable>
            </View>
            {errors.password ? <InkText style={styles.errorText}>{errors.password}</InkText> : null}

            <View style={styles.passwordWrap}>
              <TextInput
                value={confirmPassword}
                onChangeText={(text) => { setConfirmPassword(text); if (errors.confirm) setErrors((prev) => ({ ...prev, confirm: undefined })); }}
                placeholder={t('auth.confirmNewPassword')}
                secureTextEntry={!showPassword}
                style={[styles.input, styles.passwordInput, errors.confirm ? styles.inputError : null]}
              />
            </View>
            {errors.confirm ? <InkText style={styles.errorText}>{errors.confirm}</InkText> : null}

            <InkButton
              label={loading ? t('auth.processing') : t('auth.forgotPasswordSubmit')}
              block
              onPress={handleReset}
              disabled={loading || !code.trim() || !newPassword || !confirmPassword}
            />
          </>
        )}

        <InkButton
          label={t('auth.backToLogin')}
          block
          variant="ghost"
          onPress={() => router.back()}
          style={styles.backLoginButton}
        />
      </InkCard>
    </AppScreen>
  );
}

const styles = StyleSheet.create({
  backButton: {
    marginBottom: 16,
    width: 40,
    height: 40,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  title: {
    fontSize: 32,
    fontWeight: '600',
  },
  subtitle: {
    marginBottom: 24,
    marginTop: 4,
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
  codeRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'flex-start',
  },
  codeInput: {
    flex: 1,
    letterSpacing: 4,
  },
  resendButton: {
    height: 52,
    minWidth: 80,
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
  backLoginButton: {
    marginTop: 8,
  },
});
