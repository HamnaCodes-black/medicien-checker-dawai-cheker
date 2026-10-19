import { useState } from "react";
import {
  Copy,
  Download,
  FileText,
  LoaderCircle,
  ScanLine,
  Share2,
  ShieldAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { DisclaimerBar } from "../components/DisclaimerBar";
import { PageHeader, SectionHeader } from "../components/PageHeader";
import { StatusBadge, VerdictBadge } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { useToast } from "../context/ToastContext";
import { formatDateTime, formatFieldDate, formatScore } from "../lib/format";
import { buildReportText, generateReportPdf } from "../lib/report";
import { copyText, shareOrCopy } from "../lib/share";
import type { ViewName } from "../types";

const PHOTO_VIEWS: { view: ViewName; labelKey: string }[] = [
  { view: "front", labelKey: "report.photoFront" },
  { view: "back", labelKey: "report.photoBack" },
  { view: "batch", labelKey: "report.photoBatch" },
  { view: "blister", labelKey: "report.photoBlister" },
];

export function ReportPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { session, language } = useApp();
  const { showToast } = useToast();
  const [pdfBusy, setPdfBusy] = useState(false);

  if (!session) {
    return (
      <div className="page page-narrow py-10">
        <div className="surface surface-pad text-center">
          <div className="empty-visual mx-auto">
            <FileText size={30} aria-hidden="true" />
          </div>
          <h1 className="display-page font-display mt-4">
            {t("report.empty.title")}
          </h1>
          <p className="muted mt-2">{t("report.empty.body")}</p>
          <button
            type="button"
            className="btn btn-primary mt-5"
            onClick={() => navigate("/scan")}
          >
            <ScanLine size={17} aria-hidden="true" />
            {t("report.empty.cta")}
          </button>
        </div>
      </div>
    );
  }

  const { result, photos } = session;
  const languageSafe = language === "ur" ? "ur" : "en";
  const text = buildReportText(result, t, languageSafe);
  const product = result.fields.product_name ?? t("history.unnamed");

  const copySummary = async () => {
    const copied = await copyText(text);
    showToast(
      copied ? t("report.copySuccess") : t("report.error"),
      copied ? "info" : "error",
    );
  };

  const shareSummary = async () => {
    const outcome = await shareOrCopy(t("result.share.title"), text);
    if (outcome === "shared") showToast(t("report.shareSuccess"));
    else if (outcome === "copied") showToast(t("report.copySuccess"));
    else if (outcome === "failed") showToast(t("report.error"), "error");
  };

  const downloadPdf = async () => {
    setPdfBusy(true);
    try {
      await generateReportPdf(result, photos);
    } catch {
      showToast(t("report.error"), "error");
    } finally {
      setPdfBusy(false);
    }
  };

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("report.notOfficial")}
        title={t("report.title")}
        description={t("report.subtitle")}
        actions={
          result.reference?.demo ? (
            <span className="badge badge-demo">{t("app.demoData")}</span>
          ) : undefined
        }
      />

      <section className="surface surface-pad">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              {t("report.fieldLabels.product")}
            </p>
            <h2 className="display-section font-display mt-1">{product}</h2>
          </div>
          <VerdictBadge verdict={result.verdict} />
        </div>

        <dl className="field-grid mt-4">
          <div className="field-row">
            <dt>{t("report.batch")}</dt>
            <dd>{result.fields.batch_number ?? "-"}</dd>
          </div>
          <div className="field-row">
            <dt>{t("report.expiry")}</dt>
            <dd>
              {formatFieldDate(result.fields.expiry_date, languageSafe) ?? "-"}
            </dd>
          </div>
          <div className="field-row">
            <dt>{t("report.registration")}</dt>
            <dd>{result.fields.registration_number ?? "-"}</dd>
          </div>
          <div className="field-row">
            <dt>{t("report.reference")}</dt>
            <dd>
              {result.reference?.name ?? t("result.reference.none")}
            </dd>
          </div>
          <div className="field-row">
            <dt>{t("report.score")}</dt>
            <dd>
              {formatScore(result.risk_score)} / 100
            </dd>
          </div>
          <div className="field-row">
            <dt>{t("report.screened")}</dt>
            <dd>{formatDateTime(result.created_at, language)}</dd>
          </div>
        </dl>

        {result.reference?.demo ? (
          <p className="hint mt-3">{t("report.demo")}</p>
        ) : null}
      </section>

      <div className="mt-4 grid gap-2">
        <div className="notice">
          <ShieldAlert size={17} aria-hidden="true" />
          <span>{t("report.notOfficial")}</span>
        </div>
        <div className="notice">
          <ShieldAlert size={17} aria-hidden="true" />
          <span>{t("report.noUpload")}</span>
        </div>
      </div>

      <section className="mt-6">
        <SectionHeader title={t("report.checksTitle")} />
        <div className="surface overflow-hidden">
          <ul>
            {result.checks.map((check) => (
              <li
                key={check.id}
                className="flex items-start justify-between gap-3 border-b border-[var(--line)] p-3 last:border-b-0"
              >
                <span className="min-w-0 flex-1 text-sm font-semibold leading-snug">
                  {t(check.title_key, { defaultValue: check.id })}
                </span>
                <span className="flex flex-none flex-col items-end gap-1">
                  <StatusBadge status={check.status} />
                  <span className="muted text-xs">
                    {formatScore(check.risk_points)} /{" "}
                    {formatScore(check.weight)}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader title={t("report.photos")} />
        <div className="grid grid-cols-2 gap-3">
          {PHOTO_VIEWS.filter(({ view }) => photos[view]).map(
            ({ view, labelKey }) => (
              <figure key={view} className="photo-slot">
                <img src={photos[view]} alt={t(labelKey)} />
                <figcaption className="comparison-label end">
                  {t(labelKey)}
                </figcaption>
              </figure>
            ),
          )}
        </div>
      </section>

      <div className="mt-6 grid gap-2 sm:grid-cols-3">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void copySummary()}
        >
          <Copy size={17} aria-hidden="true" />
          {t("report.copySummary")}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void shareSummary()}
        >
          <Share2 size={17} aria-hidden="true" />
          {t("report.shareSummary")}
        </button>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => void downloadPdf()}
          disabled={pdfBusy}
        >
          {pdfBusy ? (
            <LoaderCircle className="spin" size={17} aria-hidden="true" />
          ) : (
            <Download size={17} aria-hidden="true" />
          )}
          {t("report.downloadPdf")}
        </button>
      </div>
      <p className="hint mt-2 text-center">{t("report.pdfEnglishNote")}</p>

      <button
        type="button"
        className="btn btn-ghost btn-block mt-4"
        onClick={() => navigate("/result")}
      >
        {t("report.back")}
      </button>

      <footer className="mt-6 py-4 text-center">
        <p className="hint">{t("app.shortDisclaimer")}</p>
      </footer>

      <DisclaimerBar />
    </div>
  );
}
