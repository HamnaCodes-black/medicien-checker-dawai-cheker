import { Languages, Moon, Sun } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useApp } from "../context/AppContext";

export function LanguageToggle() {
  const { language, setLanguage } = useApp();
  const { t } = useTranslation();
  const next = language === "en" ? "ur" : "en";
  return (
    <button
      type="button"
      className="lang-btn"
      onClick={() => setLanguage(next)}
      aria-label={
        next === "ur" ? t("language.switchToUrdu") : t("language.switchToEnglish")
      }
      title={t("language.label")}
    >
      <span className="inline-flex items-center gap-1.5">
        <Languages size={15} aria-hidden="true" />
        <span lang={next}>{next === "ur" ? "اردو" : "EN"}</span>
      </span>
    </button>
  );
}

export function ThemeToggle() {
  const { theme, toggleTheme } = useApp();
  const { t } = useTranslation();
  const next = theme === "dark" ? "light" : "dark";
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={toggleTheme}
      aria-label={next === "dark" ? t("theme.toDark") : t("theme.toLight")}
      title={next === "dark" ? t("theme.toDark") : t("theme.toLight")}
    >
      {theme === "dark" ? (
        <Sun size={19} aria-hidden="true" />
      ) : (
        <Moon size={19} aria-hidden="true" />
      )}
    </button>
  );
}
