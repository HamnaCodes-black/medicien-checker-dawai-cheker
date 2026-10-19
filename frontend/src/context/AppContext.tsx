import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import i18n, {
  applyDocumentLanguage,
  type Language,
} from "../i18n";
import {
  initialTheme,
  applyTheme,
  type Theme,
} from "../lib/theme";
import type { AnalysisResult, PhotoMap } from "../types";

export interface AnalysisSession {
  result: AnalysisResult;
  photos: PhotoMap;
  saved: boolean;
}

interface AppContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  theme: Theme;
  toggleTheme: () => void;
  session: AnalysisSession | null;
  setSession: (session: AnalysisSession | null) => void;
  clearSession: () => void;
  pendingPhotos: PhotoMap | null;
  setPendingPhotos: (photos: PhotoMap | null) => void;
  adminLinkEnabled: boolean;
  setAdminLinkEnabled: (enabled: boolean) => void;
}

const AppContext = createContext<AppContextValue | null>(null);

const ADMIN_KEY = "dawaiicheck_admin_link";

function readAdminLink(): boolean {
  try {
    return window.localStorage.getItem(ADMIN_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [language, setLanguageState] = useState<Language>(() =>
    i18n.language === "ur" ? "ur" : "en",
  );
  const [theme, setTheme] = useState<Theme>(() => initialTheme());
  const [session, setSession] = useState<AnalysisSession | null>(null);
  const [pendingPhotos, setPendingPhotos] = useState<PhotoMap | null>(null);
  const [adminLinkEnabled, setAdminLinkState] = useState<boolean>(() =>
    readAdminLink(),
  );

  const setLanguage = useCallback((next: Language) => {
    applyDocumentLanguage(next);
    void i18n.changeLanguage(next);
    setLanguageState(next);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next: Theme = current === "dark" ? "light" : "dark";
      applyTheme(next);
      return next;
    });
  }, []);

  const clearSession = useCallback(() => setSession(null), []);

  const setAdminLinkEnabled = useCallback((enabled: boolean) => {
    setAdminLinkState(enabled);
    try {
      window.localStorage.setItem(ADMIN_KEY, enabled ? "1" : "0");
    } catch {
      // Preference only.
    }
  }, []);

  const value = useMemo<AppContextValue>(
    () => ({
      language,
      setLanguage,
      theme,
      toggleTheme,
      session,
      setSession,
      clearSession,
      pendingPhotos,
      setPendingPhotos,
      adminLinkEnabled,
      setAdminLinkEnabled,
    }),
    [
      language,
      setLanguage,
      theme,
      toggleTheme,
      session,
      clearSession,
      pendingPhotos,
      adminLinkEnabled,
      setAdminLinkEnabled,
    ],
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error("useApp must be used inside AppProvider");
  }
  return context;
}
