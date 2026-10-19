import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./en.json";
import ur from "./ur.json";

export type Language = "en" | "ur";
export const LANGUAGE_STORAGE_KEY = "dawaiicheck_lang";

export function readStoredLanguage(): Language | null {
  try {
    const value = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return value === "ur" || value === "en" ? value : null;
  } catch {
    return null;
  }
}

function detectLanguage(): Language {
  const stored = readStoredLanguage();
  if (stored) return stored;
  return navigator.language.toLowerCase().startsWith("ur") ? "ur" : "en";
}

export function applyDocumentLanguage(language: Language) {
  document.documentElement.lang = language;
  document.documentElement.dir = language === "ur" ? "rtl" : "ltr";
  try {
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch {
    // Preferences are a convenience; storage may be unavailable.
  }
}

const initialLanguage = detectLanguage();
applyDocumentLanguage(initialLanguage);

void i18n.use(initReactI18next).init({
  resources: {
    en: { translation: en },
    ur: { translation: ur },
  },
  lng: initialLanguage,
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

export default i18n;
