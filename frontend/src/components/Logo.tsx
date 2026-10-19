import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <span
      className="brand-mark"
      style={{ width: size, height: size, borderRadius: size * 0.34 }}
      aria-hidden="true"
    >
      <svg
        viewBox="0 0 32 32"
        width={size * 0.62}
        height={size * 0.62}
        fill="none"
        stroke="currentColor"
        strokeWidth="2.1"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M5 11V7.5A2.5 2.5 0 0 1 7.5 5H11" />
        <path d="M21 5h3.5A2.5 2.5 0 0 1 27 7.5V11" />
        <path d="M27 21v3.5a2.5 2.5 0 0 1-2.5 2.5H21" />
        <path d="M11 27H7.5A2.5 2.5 0 0 1 5 24.5V21" />
        <rect x="11" y="10.5" width="10" height="12" rx="2" />
        <path d="M11 15h10" />
        <path d="M14.4 19h3.2" />
      </svg>
    </span>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  const { t } = useTranslation();
  return (
    <Link to="/" className="brand" aria-label={t("app.name")}>
      <LogoMark />
      <span className="brand-word">
        <span className="brand-name">DawaiCheck</span>
        {!compact ? (
          <span className="brand-tagline">{t("app.tagline")}</span>
        ) : null}
      </span>
    </Link>
  );
}
