"use client";

import { useCallback, useEffect, useRef, useState } from "react";

type HoverDropdownOptions = {
  closeDelayMs?: number;
};

export function useHoverDropdown(options?: HoverDropdownOptions) {
  const closeDelayMs = options?.closeDelayMs ?? 160;
  const [open, setOpen] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearCloseTimer = useCallback(() => {
    if (!closeTimerRef.current) return;
    clearTimeout(closeTimerRef.current);
    closeTimerRef.current = null;
  }, []);

  const openMenu = useCallback(() => {
    clearCloseTimer();
    setOpen(true);
  }, [clearCloseTimer]);

  const closeMenu = useCallback(() => {
    clearCloseTimer();
    setOpen(false);
  }, [clearCloseTimer]);

  const scheduleClose = useCallback(() => {
    clearCloseTimer();
    closeTimerRef.current = setTimeout(() => {
      setOpen(false);
      closeTimerRef.current = null;
    }, closeDelayMs);
  }, [clearCloseTimer, closeDelayMs]);

  useEffect(() => {
    return () => {
      clearCloseTimer();
    };
  }, [clearCloseTimer]);

  return {
    open,
    openMenu,
    closeMenu,
    scheduleClose,
  };
}
