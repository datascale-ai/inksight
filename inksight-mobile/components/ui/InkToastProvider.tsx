import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { InkToast, type ToastConfig, type ToastVariant } from './InkToast';

type ShowToastFn = (message: string, variant?: ToastVariant) => void;

const ToastContext = createContext<ShowToastFn>(() => undefined);

let _idCounter = 0;

export function InkToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastConfig[]>([]);
  const queueRef = useRef<ToastConfig[]>([]);
  const activeRef = useRef<boolean>(false);
  const gapTimerRef = useRef<ReturnType<typeof setTimeout>>();

  // Cleanup timer on unmount
  useEffect(() => {
    return () => {
      if (gapTimerRef.current) clearTimeout(gapTimerRef.current);
    };
  }, []);

  const next = useCallback(() => {
    if (queueRef.current.length === 0) {
      activeRef.current = false;
      return;
    }
    const [head, ...rest] = queueRef.current;
    queueRef.current = rest;
    activeRef.current = true;
    setToasts([head]);
  }, []);

  const handleDismiss = useCallback(
    (id: string) => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
      gapTimerRef.current = setTimeout(next, 150);
    },
    [next],
  );

  const showToast: ShowToastFn = useCallback(
    (message, variant = 'info') => {
      const toast: ToastConfig = {
        id: String(++_idCounter),
        message,
        variant,
      };
      if (!activeRef.current) {
        activeRef.current = true;
        setToasts([toast]);
      } else {
        queueRef.current = [...queueRef.current, toast];
      }
    },
    [],
  );

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <View style={styles.overlay} pointerEvents="none">
        {toasts.map((toast) => (
          <InkToast key={toast.id} toast={toast} onDismiss={handleDismiss} />
        ))}
      </View>
    </ToastContext.Provider>
  );
}

export function useToast(): ShowToastFn {
  return useContext(ToastContext);
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 9999,
  },
});
