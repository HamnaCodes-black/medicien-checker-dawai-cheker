import { useEffect, useState } from "react";
import {
  ChevronLeft,
  History as HistoryIcon,
  Home,
  Info,
  ScanLine,
  WifiOff,
} from "lucide-react";
import {
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Brand } from "./Logo";
import { LanguageToggle, ThemeToggle } from "./Controls";

const NAV_ITEMS = [
  { to: "/", labelKey: "nav.home", icon: Home, end: true },
  { to: "/scan", labelKey: "nav.scan", icon: ScanLine, end: false },
  { to: "/history", labelKey: "nav.history", icon: HistoryIcon, end: false },
  { to: "/how-it-works", labelKey: "nav.info", icon: Info, end: false },
];

function useBackDestination() {
  const { pathname } = useLocation();
  if (pathname === "/report") return -1;
  if (pathname === "/admin") return "/how-it-works";
  if (pathname.startsWith("/saved/")) return "/history";
  if (pathname === "/result") return "/";
  return null;
}

export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [online, setOnline] = useState(() => navigator.onLine);
  const backDestination = useBackDestination();
  const hideNav =
    location.pathname === "/onboarding" ||
    location.pathname === "/analyzing" ||
    location.pathname === "/result" ||
    location.pathname.startsWith("/saved/") ||
    location.pathname === "/report" ||
    location.pathname === "/admin";
  const showBack = backDestination !== null;
  const onResultOrReport =
    location.pathname === "/result" ||
    location.pathname.startsWith("/saved/") ||
    location.pathname === "/report";

  useEffect(() => {
    const handleOnline = () => setOnline(true);
    const handleOffline = () => setOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [location.pathname]);

  const handleBack = () => {
    if (backDestination === -1) {
      if (window.history.length > 2) navigate(-1);
      else navigate("/");
    } else if (typeof backDestination === "string") {
      navigate(backDestination);
    }
  };

  return (
    <div className="app-shell">
      <a href="#main-content" className="visually-hidden">
        {t("nav.skip")}
      </a>
      <header className="topbar">
        <div className="topbar-inner">
          <div className="flex min-w-0 items-center gap-1">
            {showBack ? (
              <button
                type="button"
                className="icon-btn"
                onClick={handleBack}
                aria-label={t("actions.back")}
              >
                <ChevronLeft
                  size={22}
                  className="rtl:rotate-180"
                  aria-hidden="true"
                />
              </button>
            ) : null}
            <Brand compact={showBack} />
          </div>
          <nav className="desktop-nav" aria-label={t("nav.home")}>
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) =>
                    `desktop-nav-link${isActive ? " is-active" : ""}`
                  }
                >
                  <Icon size={16} aria-hidden="true" />
                  <span>{t(item.labelKey)}</span>
                </NavLink>
              );
            })}
          </nav>
          <div className="header-actions">
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>
      </header>

      {!online ? (
        <div className="offline-banner" role="status">
          <WifiOff size={16} aria-hidden="true" />
          <span>{t("app.offline")}</span>
        </div>
      ) : null}

      <main
        id="main-content"
        className={`${onResultOrReport ? "page-with-disclaimer" : ""} ${
          hideNav ? "" : "page-with-nav"
        }`}
      >
        <div key={location.pathname} className="page-transition">
          <Outlet />
        </div>
      </main>

      {!hideNav ? (
        <nav className="bottom-nav" aria-label={t("nav.home")}>
          <div className="bottom-nav-inner">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className="nav-item"
                >
                  <span className="nav-icon-wrap">
                    <Icon size={20} strokeWidth={2} aria-hidden="true" />
                  </span>
                  <span>{t(item.labelKey)}</span>
                </NavLink>
              );
            })}
          </div>
        </nav>
      ) : null}
    </div>
  );
}
