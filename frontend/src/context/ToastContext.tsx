import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";
import { CheckCircle2, AlertCircle } from "lucide-react";

type Tone = "info" | "error";

interface ToastState {
  message: string;
  tone: Tone;
}

interface ToastContextValue {
  showToast: (message: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timeoutRef = useRef<number | null>(null);
  const location = useLocation();
  const aboveDisclaimer =
    location.pathname === "/result" ||
    location.pathname.startsWith("/saved/") ||
    location.pathname === "/report";

  const showToast = useCallback((message: string, tone: Tone = "info") => {
    setToast({ message, tone });
    if (timeoutRef.current !== null) {
      window.clearTimeout(timeoutRef.current);
    }
    timeoutRef.current = window.setTimeout(() => setToast(null), 3400);
  }, []);

  useEffect(() => {
    return () => {
      if (timeoutRef.current !== null) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div aria-live="polite" aria-atomic="true">
        {toast ? (
          <div
            className={`toast${aboveDisclaimer ? " toast-above-disclaimer" : ""}`}
            data-tone={toast.tone}
            role="status"
          >
            {toast.tone === "error" ? (
              <AlertCircle size={17} aria-hidden="true" />
            ) : (
              <CheckCircle2 size={17} aria-hidden="true" />
            )}
            <span>{toast.message}</span>
          </div>
        ) : null}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error("useToast must be used inside ToastProvider");
  }
  return context;
}
