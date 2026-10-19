import { useEffect, useState, type ReactNode } from "react";
import {
  Bookmark,
  Camera,
  FileSearch,
  FlaskConical,
  Languages,
  ScanLine,
  ShieldAlert,
  ShieldQuestion,
  Sparkles,
  UserRoundX,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { DemoPicker } from "../components/DemoPicker";
import { SectionHeader } from "../components/PageHeader";
import { HistorySkeleton, VerdictBadge } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { listScans } from "../lib/db";
import { formatDateTime } from "../lib/format";
import type { ScanRecord } from "../types";

const ONBOARDING_KEY = "dawaiicheck_onboarded";

export function HomePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { language } = useApp();
  const [recent, setRecent] = useState<ScanRecord[] | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);

  useEffect(() => {
    let onboarded: boolean;
    try {
      onboarded = window.localStorage.getItem(ONBOARDING_KEY) === "1";
    } catch {
      onboarded = true;
    }
    if (!onboarded) navigate("/onboarding", { replace: true });
  }, [navigate]);

  useEffect(() => {
    let active = true;
    void listScans()
      .then((records) => {
        if (active) setRecent(records);
      })
      .catch(() => {
        if (active) setRecent([]);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page page-wide py-5">
      <section className="hero-card surface-pad reveal">
        <div className="relative z-10">
          <div className="flex flex-wrap items-center gap-2">
            <span className="chip chip-brand">
              <Sparkles size={13} aria-hidden="true" />
              {t("home.eyebrow")}
            </span>
            <span className="chip chip-demo">{t("home.demo.short")}</span>
          </div>
          <h1 className="display-hero font-display mt-4">{t("home.title")}</h1>
          <p className="lead mt-3 max-w-xl">{t("home.subtitle")}</p>

          <div className="hero-actions">
            <Link to="/scan" className="btn btn-primary btn-lg">
              <Camera size={19} aria-hidden="true" />
              {t("home.scanCta")}
            </Link>
            <button
              type="button"
              className="btn btn-secondary btn-lg"
              onClick={() => setDemoOpen(true)}
            >
              <FlaskConical size={19} aria-hidden="true" />
              {t("home.demoCta")}
            </button>
          </div>
          <p className="hint mt-3">{t("home.scanHint")}</p>

          <ul className="mt-5 flex flex-wrap gap-2">
            <TrustItem icon={<UserRoundX size={14} />}>
              {t("home.trust.noAccount")}
            </TrustItem>
            <TrustItem icon={<Bookmark size={14} />}>
              {t("home.trust.consent")}
            </TrustItem>
            <TrustItem icon={<Languages size={14} />}>
              {t("home.trust.bilingual")}
            </TrustItem>
          </ul>
        </div>
      </section>

      <section className="mt-8" aria-labelledby="recent-heading">
        <SectionHeader
          title={<span id="recent-heading">{t("home.recent.title")}</span>}
          action={
            recent && recent.length > 0 ? (
              <Link to="/history" className="link text-sm font-semibold">
                {t("home.recent.viewAll")}
              </Link>
            ) : undefined
          }
        />
        {recent === null ? <HistorySkeleton /> : null}
        {recent && recent.length === 0 ? (
          <div className="surface surface-pad flex items-start gap-3">
            <span className="feature-icon" aria-hidden="true">
              <Camera size={19} />
            </span>
            <div>
              <p className="font-semibold">{t("history.empty.title")}</p>
              <p className="muted mt-1 text-sm leading-relaxed">
                {t("history.empty.body")}
              </p>
            </div>
          </div>
        ) : null}
        {recent && recent.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {recent.slice(0, 3).map((record) => {
              const name =
                record.result.fields.product_name ?? t("history.unnamed");
              const photo = record.photos.front;
              return (
                <Link
                  key={record.id}
                  to={`/saved/${record.id}`}
                  className="history-card"
                >
                  <span className="history-thumb">
                    {photo ? (
                      <img src={photo} alt="" />
                    ) : (
                      <span className="grid h-full place-items-center text-[var(--muted)]">
                        <FileSearch size={22} aria-hidden="true" />
                      </span>
                    )}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex flex-wrap items-start justify-between gap-2">
                      <span className="font-semibold leading-snug">{name}</span>
                      <VerdictBadge verdict={record.result.verdict} />
                    </span>
                    <span className="muted mt-1 block text-xs">
                      {t("history.savedOn", {
                        date: formatDateTime(record.createdAt, language),
                      })}
                    </span>
                    <span className="muted mt-2 block text-xs">
                      {t("history.risk", {
                        score: Math.round(record.result.risk_score),
                      })}
                    </span>
                  </span>
                </Link>
              );
            })}
          </div>
        ) : null}
      </section>

      <section className="mt-8" aria-labelledby="how-heading">
        <SectionHeader
          title={<span id="how-heading">{t("home.how.title")}</span>}
          description={t("home.how.subtitle")}
        />
        <div className="quick-grid quick-grid-3">
          <HowCard
            icon={<ScanLine size={20} />}
            title={t("home.how.step1Title")}
            body={t("home.how.step1Body")}
          />
          <HowCard
            icon={<FileSearch size={20} />}
            title={t("home.how.step2Title")}
            body={t("home.how.step2Body")}
          />
          <HowCard
            icon={<ShieldQuestion size={20} />}
            title={t("home.how.step3Title")}
            body={t("home.how.step3Body")}
          />
        </div>
        <div className="mt-3">
          <Link to="/how-it-works" className="link text-sm font-semibold">
            {t("home.how.link")}
          </Link>
        </div>
      </section>

      <section className="mt-8">
        <div className="callout">
          <div className="flex items-start gap-3">
            <span className="feature-icon feature-icon-warn" aria-hidden="true">
              <ShieldAlert size={20} />
            </span>
            <div>
              <h2 className="display-section font-display">
                {t("home.limits.title")}
              </h2>
              <p className="muted mt-2 text-sm leading-relaxed">
                {t("home.limits.body")}
              </p>
              <Link
                to="/how-it-works"
                className="link mt-3 inline-block text-sm font-semibold"
              >
                {t("home.limits.link")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="mt-4">
        <div className="notice" data-tone="info">
          <FlaskConical size={18} aria-hidden="true" />
          <div>
            <strong>{t("home.demo.title")}</strong>
            <p className="mt-1 text-sm leading-relaxed">
              {t("home.demo.body")}
            </p>
          </div>
        </div>
      </section>

      <footer className="mt-8 py-4 text-center">
        <p className="hint">{t("home.footer")}</p>
        <p className="faint mt-1 text-xs">{t("app.shortDisclaimer")}</p>
      </footer>

      <DemoPicker open={demoOpen} onClose={() => setDemoOpen(false)} />
    </div>
  );
}

function TrustItem({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <li className="chip">
      <span className="inline-flex items-center gap-1.5">
        {icon}
        <span>{children}</span>
      </span>
    </li>
  );
}

function HowCard({
  icon,
  title,
  body,
}: {
  icon: ReactNode;
  title: string;
  body: string;
}) {
  return (
    <article className="surface surface-pad">
      <span className="feature-icon" aria-hidden="true">
        {icon}
      </span>
      <h3 className="mt-3 font-semibold leading-snug">{title}</h3>
      <p className="muted mt-1 text-sm leading-relaxed">{body}</p>
    </article>
  );
}
