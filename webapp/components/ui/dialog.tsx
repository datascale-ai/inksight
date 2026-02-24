"use client";

import { ReactNode, useEffect, useRef } from "react";
import { X } from "lucide-react";

interface DialogProps {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}

export function Dialog({ open, onClose, children }: DialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    if (open) {
      document.addEventListener("keydown", handleEsc);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === overlayRef.current) onClose();
      }}
    >
      <div className="fixed inset-0 bg-black/40 backdrop-blur-sm" />
      <div className="relative z-10 w-full max-w-lg mx-4 animate-fade-in">
        {children}
      </div>
    </div>
  );
}

export function DialogContent({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-sm border border-ink/10 bg-white p-6 shadow-lg ${className}`}
    >
      {children}
    </div>
  );
}

export function DialogHeader({
  children,
  onClose,
}: {
  children: ReactNode;
  onClose?: () => void;
}) {
  return (
    <div className="flex items-start justify-between mb-4">
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          onClick={onClose}
          className="ml-4 p-1 text-ink-light hover:text-ink transition-colors"
        >
          <X size={18} />
        </button>
      )}
    </div>
  );
}

export function DialogTitle({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-lg font-semibold text-ink">{children}</h2>
  );
}

export function DialogDescription({ children }: { children: ReactNode }) {
  return (
    <p className="text-sm text-ink-light mt-1">{children}</p>
  );
}
