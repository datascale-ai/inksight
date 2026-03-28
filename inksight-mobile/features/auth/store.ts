import { create } from 'zustand';
import { clearToken, getToken, setToken } from '@/lib/storage';
import { login, me, register, type AuthUser } from '@/features/auth/api';

/** 真机上 API 若指向本机 localhost，/auth/me 可能长时间挂起，必须超时否则 hydrated 永不成立 */
const ME_REQUEST_TIMEOUT_MS = 12_000;

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise((resolve, reject) => {
    const id = setTimeout(() => reject(new Error('timeout')), ms);
    promise
      .then((v) => {
        clearTimeout(id);
        resolve(v);
      })
      .catch((e) => {
        clearTimeout(id);
        reject(e);
      });
  });
}

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
    extra?: { phone?: string; email?: string },
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
    try {
      const token = await getToken();
      if (!token) {
        set({ hydrated: true });
        return;
      }
      try {
        const user = await withTimeout(me(token), ME_REQUEST_TIMEOUT_MS);
        set({ token, user, hydrated: true });
      } catch {
        await clearToken();
        set({ token: null, user: null, hydrated: true });
      }
    } catch {
      set({ hydrated: true });
    }
  },
  signIn: async (username, password, mode = 'login', extra) => {
    set({ loading: true });
    try {
      const result = mode === 'register' ? await register(username, password, extra) : await login(username, password);
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
