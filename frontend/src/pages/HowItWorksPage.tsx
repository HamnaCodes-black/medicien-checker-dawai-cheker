import { useEffect, useState, type ReactNode } from "react";
import {
  BadgeCheck,
  CalendarDays,
  Camera,
  Database,
  ExternalLink,
  Hash,
  LoaderCircle,
  LockKeyhole,
  Palette,
  Printer,
  ScanBarcode,
  Scale,
  ShieldAlert,
  ShieldQuestion,
  SpellCheck,
  WifiOff,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { PageHeader, SectionHeader } from "../components/PageHeader";
import { Toggle, VerdictBadge } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { getHealth } from "../lib/api";
import type { HealthResponse } from "../types";

export function HowItWorksPage() {
  const { t } = useTranslation();
  const { adminLinkEnabled, setAdminLinkEnabled } = useApp();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState(false);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void getHealth()
      .then((value) => {
        if (active) setHealth(value);
      })
      .catch(() => {
        if (active) setHealthError(true);
      })
      .finally(() => {
        if (active) setHealthLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("app.tagline")}
        title={t("how.title")}
        description={t("how.subtitle")}
        actions={<span className="badge badge-demo">{t("app.demoData")}</span>}
      />

      <section className="surface surface-pad">
        <div className="flex items-start gap-3">
          <span className="feature-icon" aria-hidden="true">
            {healthLoading ? (
              <LoaderCircle className="spin" size={19} />
            ) : healthError ? (
              <WifiOff size={19} />
            ) : (
              <Database size={19} />
            )}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="display-section font-display">
                {t("how.health.title")}
              </h2>
              {health?.demo_data ? (
                <span className="badge badge-demo">{t("how.health.demo")}</span>
              ) : null}
            </div>
            <p className="muted mt-1 text-sm leading-relaxed">
              {healthLoading
                ? t("how.health.loading")
                : healthError || !health
                  ? t("how.health.offline")
                  : t("how.health.online", {
                      engine: health.ocr_engine,
                      count: health.reference_count,
                    })}
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader title={t("how.whatTitle")} />
        <div className="grid gap-2">
          <CheckLine icon={<ScanBarcode size={18} />}>
            {t("how.what.barcode")}
          </CheckLine>
          <CheckLine icon={<CalendarDays size={18} />}>
            {t("how.what.dates")}
          </CheckLine>
          <CheckLine icon={<Hash size={18} />}>
            {t("how.what.batch")}
          </CheckLine>
          <CheckLine icon={<BadgeCheck size={18} />}>
            {t("how.what.registration")}
          </CheckLine>
          <CheckLine icon={<SpellCheck size={18} />}>
            {t("how.what.spelling")}
          </CheckLine>
          <CheckLine icon={<Palette size={18} />}>
            {t("how.what.visual")}
          </CheckLine>
          <CheckLine icon={<Printer size={18} />}>
            {t("how.what.print")}
          </CheckLine>
          <CheckLine icon={<Camera size={18} />}>
            {t("how.what.quality")}
          </CheckLine>
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader title={t("how.limitsTitle")} />
        <div className="callout callout-warn">
          <div className="flex items-start gap-3">
            <ShieldAlert size={20} className="mt-0.5 flex-none" aria-hidden="true" />
            <ul className="space-y-2">
              <li>{t("how.limits.inside")}</li>
              <li>{t("how.limits.genuine")}</li>
              <li>{t("how.limits.safe")}</li>
              <li>{t("how.limits.registry")}</li>
              <li>{t("how.limits.visual")}</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader title={t("how.verdictsTitle")} />
        <div className="grid gap-3">
          <div className="surface surface-pad">
            <VerdictBadge verdict="consistent" />
            <p className="muted mt-2 text-sm leading-relaxed">
              {t("how.verdicts.consistent")}
            </p>
          </div>
          <div className="surface surface-pad">
            <VerdictBadge verdict="suspicious" />
            <p className="muted mt-2 text-sm leading-relaxed">
              {t("how.verdicts.suspicious")}
            </p>
          </div>
          <div className="surface surface-pad">
            <VerdictBadge verdict="undetermined" />
            <p className="muted mt-2 text-sm leading-relaxed">
              {t("how.verdicts.undetermined")}
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader title={t("how.photosTitle")} />
        <div className="surface surface-pad">
          <ul className="space-y-2 text-sm leading-relaxed">
            <li>{t("how.photos.light")}</li>
            <li>{t("how.photos.fill")}</li>
            <li>{t("how.photos.panel")}</li>
          </ul>
        </div>
      </section>

      <section className="mt-6 grid gap-3 sm:grid-cols-2">
        <InfoCard
          icon={<LockKeyhole size={19} />}
          title={t("how.privacyTitle")}
          body={t("how.privacyBody")}
        />
        <InfoCard
          icon={<ShieldQuestion size={19} />}
          title={t("how.drapTitle")}
          body={t("how.drapBody")}
        />
        <InfoCard
          icon={<BadgeCheck size={19} />}
          title={t("how.demoTitle")}
          body={t("how.demoBody")}
        />
        <InfoCard
          icon={<Scale size={19} />}
          title={t("how.scoringTitle")}
          body={t("how.scoringBody")}
        />
      </section>

      <section className="mt-6">
        <SectionHeader title={t("how.admin.title")} />
        <div className="surface surface-pad">
          <Toggle
            id="reference-lab-toggle"
            checked={adminLinkEnabled}
            onChange={setAdminLinkEnabled}
            label={t("how.admin.toggle")}
            description={t("how.admin.body")}
          />
          {adminLinkEnabled ? (
            <Link to="/admin" className="btn btn-secondary mt-4">
              <ExternalLink size={17} aria-hidden="true" />
              {t("how.admin.open")}
            </Link>
          ) : null}
        </div>
      </section>

      <Link to="/" className="btn btn-ghost btn-block mt-6">
        {t("how.backHome")}
      </Link>
    </div>
  );
}

function CheckLine({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <div className="surface flex items-center gap-3 p-3">
      <span className="feature-icon" aria-hidden="true">
        {icon}
      </span>
      <span className="text-sm leading-relaxed">{children}</span>
    </div>
  );
}

function InfoCard({
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
      <h2 className="mt-3 font-semibold">{title}</h2>
      <p className="muted mt-1 text-sm leading-relaxed">{body}</p>
    </article>
  );
}
