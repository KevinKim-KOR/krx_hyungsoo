"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

type ToastVariant = "success" | "error" | "warning";

type ToastItem = {
  id: number;
  message: string;
  variant: ToastVariant;
};

type ToastContextValue = {
  success: (message: string) => void;
  error: (message: string) => void;
  warning: (message: string) => void;
};

const ToastContext = createContext<ToastContextValue | null>(null);

type ToastProviderProps = {
  children: ReactNode;
};

function getToastClassName(variant: ToastVariant): string {
  switch (variant) {
    case "success":
      return "bg-success-lt text-success-emphasis border-success-subtle";
    case "error":
      return "bg-danger-lt text-danger-emphasis border-danger-subtle";
    case "warning":
      return "bg-warning-lt text-warning-emphasis border-warning-subtle";
    default:
      return "";
  }
}

export function ToastProvider({ children }: ToastProviderProps) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(1);

  const removeToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const pushToast = useCallback(
    (variant: ToastVariant, message: string) => {
      const id = nextIdRef.current;
      nextIdRef.current += 1;

      setToasts((current) => [...current, { id, message, variant }]);
      if (variant !== "error") {
        window.setTimeout(() => {
          setToasts((current) => current.filter((toast) => toast.id !== id));
        }, 3_000);
      }
    },
    [],
  );

  const value = useMemo<ToastContextValue>(
    () => ({
      success: (message) => pushToast("success", message),
      error: (message) => pushToast("error", message),
      warning: (message) => pushToast("warning", message),
    }),
    [pushToast],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="appToastViewport" aria-live="polite" aria-atomic="true">
        {toasts.map((toast) => (
          <div key={toast.id} className={`toast show appToast ${getToastClassName(toast.variant)}`} role="status">
            <div className="toast-body appToastBody">
              <span>{toast.message}</span>
              <button
                type="button"
                className="btn-close appToastClose"
                aria-label="닫기"
                onClick={() => removeToast(toast.id)}
              />
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("ToastProvider가 필요합니다.");
  }
  return context;
}
