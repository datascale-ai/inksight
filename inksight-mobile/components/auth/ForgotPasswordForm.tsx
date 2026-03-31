import { useState } from 'react';
import { Alert, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { router } from 'expo-router';
import { ArrowLeft, Eye, EyeOff } from 'lucide-react-native';
import { AppScreen } from '@/components/layout/AppScreen';
import { InkCard } from '@/components/ui/InkCard';
import { InkText } from '@/components/ui/InkText';
import { InkButton } from '@/components/ui/InkButton';
import { resetPassword } from '@/features/auth/api';
import { useI18n } from '@/lib/i18n';
import { theme } from '@/lib/theme';

type FormErrors = {
  username?: string;
  contact?: string;
  password?: string;
  confirm?: string;
};

export function ForgotPasswordForm() {
  const { t } = useI18n();

  const [username, setUsername] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FormErrors>({});
  const [loading, setLoading] = useState(false);

  function validate(): FormErrors | null {
    const errs: FormErrors = {};
    const trimmed = username.trim();
    if (trimmed.length < 2 || trimmed.length > 30) {
      errs.username = t('auth.errorUsernameMin');
    } else if (!/^[a-zA-Z0-9_]+$/.test(trimmed)) {
      errs.username = t('auth.errorUsernameFormat');
    }

    const p = phone.trim();
    const e = email.trim();
    if (!p && !e) {
      errs.contact = t('auth.errorContactRequired');
    }
    if (p && !/^\+?[0-9][0-9\s\-]{6,20}$/.test(p)) {
      errs.contact = t('auth.errorPhoneFormat');
    }
    if (e && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) {
      errs.contact = t('auth.errorEmailFormat');
    }

    if (newPassword.length < 6) {
      errs.password = t('auth.errorPasswordMin');
    }
    if (newPassword !== confirmPassword) {
      errs.confirm = t('auth.errorPasswordMismatch');
    }

    return Object.keys(errs).length > 0 ? errs : null;
  }

  async function handleReset() {
    const errs = validate();
    if (errs) {
      setErrors(errs);
      return;
    }
    setErrors({});
    setLoading(true);
    try {
      await resetPassword({
        username: username.trim(),
        password: newPassword,
        phone: phone.trim() || undefined,
        email: email.trim() || undefined,
      });
      Alert.alert(t('auth.forgotPasswordSuccess'), t('auth.forgotPasswordSuccessMessage'), [
        { text: t('common.confirm'), onPress: () => router.replace('/login') },
      ]);
    } catch (err) {
      Alert.alert(
        t('auth.forgotPasswordError'),
        err instanceof Error ? err.message : t('common.loading'),
      );
    } finally {
      setLoading(false);
    }
  }

  function handleBack() {
    router.back();
  }

  return (
    <AppScreen>
      <Pressable onPress={handleBack} style={styles.backButton}>
        <ArrowLeft
          size={22}
          color={theme.colors.secondary}
          strokeWidth={theme.strokeWidth}
        />
      </Pressable>

      <InkText serif style={styles.title}>{t('auth.forgotPassword')}</InkText>
      <InkText dimmed style={styles.subtitle}>{t('auth.forgotPasswordHint')}</InkText>

      <InkCard>
        <TextInput
          value={username}
          onChangeText={(text) => {
            setUsername(text);
            if (errors.username) setErrors((prev) => ({ ...prev, username: undefined }));
          }}
          placeholder={t('auth.username')}
          style={[styles.input, errors.username ? styles.inputError : null]}
          autoCapitalize="none"
        />
        {errors.username ? (
          <InkText style={styles.errorText}>{errors.username}</InkText>
        ) : null}

        <TextInput
          value={phone}
          onChangeText={(text) => {
            setPhone(text);
            if (errors.contact) setErrors((prev) => ({ ...prev, contact: undefined }));
          }}
          placeholder={t('auth.phoneOptional')}
          style={[styles.input, errors.contact ? styles.inputError : null]}
          keyboardType="phone-pad"
          autoCapitalize="none"
        />

        <TextInput
          value={email}
          onChangeText={(text) => {
            setEmail(text);
            if (errors.contact) setErrors((prev) => ({ ...prev, contact: undefined }));
          }}
          placeholder={t('auth.emailOptional')}
          style={[styles.input, errors.contact ? styles.inputError : null]}
          keyboardType="email-address"
          autoCapitalize="none"
        />
        {errors.contact ? (
          <InkText style={styles.errorText}>{errors.contact}</InkText>
        ) : null}

        <View style={styles.passwordWrap}>
          <TextInput
            value={newPassword}
            onChangeText={(text) => {
              setNewPassword(text);
              if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
            }}
            placeholder={t('auth.newPassword')}
            secureTextEntry={!showPassword}
            style={[styles.input, styles.passwordInput, errors.password ? styles.inputError : null]}
          />
          <Pressable
            onPress={() => setShowPassword((prev) => !prev)}
            style={styles.eyeButton}
          >
            {showPassword ? (
              <EyeOff
                size={18}
                color={theme.colors.secondary}
                strokeWidth={theme.strokeWidth}
              />
            ) : (
              <Eye
                size={18}
                color={theme.colors.secondary}
                strokeWidth={theme.strokeWidth}
              />
            )}
          </Pressable>
        </View>
        {errors.password ? (
          <InkText style={styles.errorText}>{errors.password}</InkText>
        ) : null}

        <View style={styles.passwordWrap}>
          <TextInput
            value={confirmPassword}
            onChangeText={(text) => {
              setConfirmPassword(text);
              if (errors.confirm) setErrors((prev) => ({ ...prev, confirm: undefined }));
            }}
            placeholder={t('auth.confirmNewPassword')}
            secureTextEntry={!showPassword}
            style={[styles.input, styles.passwordInput, errors.confirm ? styles.inputError : null]}
          />
        </View>
        {errors.confirm ? (
          <InkText style={styles.errorText}>{errors.confirm}</InkText>
        ) : null}

        <InkButton
          label={loading ? t('auth.processing') : t('auth.forgotPasswordSubmit')}
          block
          onPress={handleReset}
          disabled={loading || !username.trim() || !newPassword || !confirmPassword}
        />

        <InkButton
          label={t('auth.backToLogin')}
          block
          variant="ghost"
          onPress={handleBack}
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
