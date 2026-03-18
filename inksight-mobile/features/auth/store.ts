import { create } from 'zustand';
import { clearToken, getToken, setToken } from '@/lib/storage';
import { login, me, register, type AuthUser } from '@/features/auth/api';

type AuthState = {
  token: string | null;
  user: AuthUser | null;
  hydrated: boolean;
  loading: boolean;
  bootstrap: () => Promise<void>;
  signIn: (
    username: string,
    password: string,
    mode?: 'login' | 'register',
    options?: { phone?: string; email?: string },
  ) => Promise<void>;
  signOut: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: null,
  user: null,
  hydrated: false,
  loading: false,
  bootstrap: async () => {
    if (get().hydrated) {
      return;
    }
    const token = await getToken();
    if (!token) {
      set({ hydrated: true });
      return;
    }
    try {
      const user = await me(token);
      set({ token, user, hydrated: true });
    } catch {
      await clearToken();
      set({ token: null, user: null, hydrated: true });
    }
  },
  signIn: async (username, password, mode = 'login', options) => {
    set({ loading: true });
    try {
      const result =
        mode === 'register'
          ? await register({
              username,
              password,
              phone: options?.phone,
              email: options?.email,
            })
          : await login(username, password);
      await setToken(result.token);
      set({
        token: result.token,
        user: { user_id: result.user_id, username: result.username },
        hydrated: true,
        loading: false,
      });
    } catch (error) {
      set({ loading: false });
      throw error;
    }
  },
  signOut: async () => {
    await clearToken();
    set({ token: null, user: null });
  },
}));
