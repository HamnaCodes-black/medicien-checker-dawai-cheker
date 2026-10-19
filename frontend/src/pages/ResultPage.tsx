import { useState } from "react";
import {
  Camera,
  Check,
  CircleHelp,
  FileText,
  Info,
  LoaderCircle,
  PenLine,
  Pill,
  Save,
  Share2,
  ShieldAlert,
  Stethoscope,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { CheckCard } from "../components/CheckCard";
import { ComparisonSlider } from "../components/ComparisonSlider";
import { Dialog } from "../components/Dialog";
import { DisclaimerBar } from "../components/DisclaimerBar";
import { PageHeader, SectionHeader } from "../components/PageHeader";
import { ConfidenceMeter, StatusIcon, VerdictBadge } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { useToast } from "../context/ToastContext";
import { analyzePack } from "../lib/api";
import { saveScan } from "../lib/db";
import { formatDateTime, formatFieldDate, formatScore } from "../lib/format";
import { compressForStorage } from "../lib/images";
import { buildReportText } from "../lib/report";
import { shareOrCopy } from "../lib/share";
import type {
  CheckStatus,
  ExtractedFields,
  FieldName,
  PhotoMap,
  QualityStatus,
  ScanRecord,
  ViewName,
} from "../types";

const FIELD_KEYS: FieldName[] = [
  "product_name",
  "strength",
  "manufacturer",
  "registration_number",
  "batch_number",
  "manufacturing_date",
  "expiry_date",
  "barcode",
];

const COMPARISON_VIEWS: ViewName[] = ["front", "back", "batch", "blister"];

const STATUS_ORDER: Record<CheckStatus, number> = {
  fail: 0,
  warn: 1,
  unknown: 2,
  pass: 3,
};

function riskBand(score: number): "low" | "medium" | "high" {
  if (score < 15) return "low";
  if (score < 35) return "medium";
  return "high";
}

function qualityStatus(status: QualityStatus): CheckStatus {
  return status === "ok" ? "pass" : status;
}

export function ResultPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { language, session, setSession, setPendingPhotos } = useApp();
  const { showToast } = useToast();

  const [saveOpen, setSaveOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pharmacistOpen, setPharmacistOpen] = useState(false);
  const [scoringOpen, setScoringOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ExtractedFields | null>(null);
  const [rechecking, setRechecking] = useState(false);
  const [recheckError, setRecheckError] = useState(false);
  const [showAllChecks, setShowAllChecks] = useState(false);
  const [comparisonView, setComparisonView] = useState<ViewName>("front");

  const result = session?.result ?? null;

  if (!session || !result) {
    return (
      <div className="page page-narrow py-10 text-center">
        <div className="empty-visual mx-auto">
          <CircleHelp size={30} aria-hidden="true" />
        </div>
        <h1 className="display-page font-display mt-4">
          {t("result.notFound.title")}
        </h1>
        <p className="muted mx-auto mt-2 max-w-md">
          {t("result.notFound.body")}
        </p>
        <button
          type="button"
          className="btn btn-primary mt-5"
          onClick={() => navigate("/scan")}
        >
          {t("result.notFound.cta")}
        </button>
      </div>
    );
  }

  const verdict = result.verdict;
  const band = riskBand(result.risk_score);
  const availableComparisons = COMPARISON_VIEWS.filter(
    (view) => result.comparisons[view],
  );
  const activeComparison =
    availableComparisons.find((view) => view === comparisonView) ??
    availableComparisons[0];
  const orderedChecks = [...result.checks].sort(
    (left, right) =>
      STATUS_ORDER[left.status] - STATUS_ORDER[right.status],
  );
  const visibleChecks = showAllChecks
    ? orderedChecks
    : orderedChecks.slice(0, 6);
  const qualityEntries = Object.entries(result.quality);

  const beginEdit = () => {
    setDraft({ ...result.fields });
    setRecheckError(false);
    setEditing(true);
  };

  const updateDraft = (key: FieldName, value: string) => {
    setDraft((current) =>
      current ? { ...current, [key]: value } : current,
    );
  };

  const recheck = async () => {
    if (!draft) return;
    const overrides: Partial<ExtractedFields> = {};
    for (const key of FIELD_KEYS) {
      if ((draft[key] ?? "") !== (result.fields[key] ?? "")) {
        overrides[key] = (draft[key] ?? "").trim() || null;
      }
    }
    if (!Object.keys(overrides).length) {
      setEditing(false);
      return;
    }
    setRechecking(true);
    setRecheckError(false);
    try {
      const updated = await analyzePack(session.photos, { overrides });
      setSession({ result: updated, photos: session.photos, saved: false });
      setEditing(false);
      setDraft(null);
      setShowAllChecks(false);
    } catch {
      setRecheckError(true);
    } finally {
      setRechecking(false);
    }
  };

  const saveResult = async () => {
    setSaving(true);
    try {
      const stored: PhotoMap = {};
      await Promise.all(
        Object.entries(session.photos).map(async ([view, value]) => {
          if (value) {
            stored[view as ViewName] = await compressForStorage(value);
          }
        }),
      );
      const record: ScanRecord = {
        id: result.analysis_id,
        createdAt: new Date().toISOString(),
        result,
        photos: stored,
        language,
      };
      await saveScan(record);
      setSession({ ...session, saved: true });
      setSaveOpen(false);
      showToast(t("result.saveDialog.success"));
    } catch {
      showToast(t("result.saveDialog.error"), "error");
    } finally {
      setSaving(false);
    }
  };

  const shareResult = async () => {
    const text = buildReportText(result, t, language);
    const outcome = await shareOrCopy(t("result.share.title"), text);
    if (outcome === "shared") showToast(t("result.share.success"));
    else if (outcome === "copied") showToast(t("result.share.copied"));
    else if (outcome === "failed") showToast(t("result.share.error"), "error");
  };

  const askSave = () => {
    if (session.saved) {
      showToast(t("result.saveDialog.alreadySaved"));
      return;
    }
    setSaveOpen(true);
  };

  const retake = () => {
    setPendingPhotos(session.photos);
    navigate("/scan");
  };

  const verdictNoteTone = verdict === "suspicious" ? "danger" : "warn";

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("result.checkedOn", {
          date: formatDateTime(result.created_at, language),
        })}
        title={t("result.title")}
        actions={
          <>
            {session.saved ? (
              <span className="badge badge-pass">
                <Check size={12} aria-hidden="true" />
                {t("result.savedChip")}
              </span>
            ) : null}
            {result.reference?.demo ? (
              <span className="badge badge-demo">{t("app.demoData")}</span>
            ) : null}
          </>
        }
      />

      <section className="verdict-card" data-verdict={verdict}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <VerdictBadge verdict={verdict} />
          <span className="chip">
            {t(`result.confidence.title`)}:{" "}
            {t(`confidence.${result.confidence}.label`)}
          </span>
        </div>
        <h2 className="display-hero font-display mt-4">
          {t(`result.verdict.${verdict}.title`)}
        </h2>
        <p className="lead mt-2">{t(`result.verdict.${verdict}.subtitle`)}</p>
        <div className="notice mt-4" data-tone={verdictNoteTone}>
          <ShieldAlert size={18} aria-hidden="true" />
          <span>{t(`result.verdict.${verdict}.note`)}</span>
        </div>
        {result.reference?.demo ? (
          <p className="hint mt-3">{t("result.demoNotice")}</p>
        ) : null}
      </section>

      <section className="surface surface-pad mt-4">
        <div className="grid gap-5 sm:grid-cols-2">
          <div className="metric-block">
            <span className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              {t("result.risk.title")}
            </span>
            <span className="metric-value">
              {formatScore(result.risk_score)}
              <span className="muted text-sm font-normal">
                {" "}
                {t("result.risk.outOf")}
              </span>
            </span>
            <span className="text-sm font-semibold">
              {t(`result.risk.band.${band}`)}
            </span>
            <span className="hint mt-1">{t("result.risk.hint")}</span>
          </div>
          <div>
            <span className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
              {t("result.confidence.title")}
            </span>
            <div className="mt-2">
              <ConfidenceMeter level={result.confidence} />
            </div>
            <p className="muted mt-3 text-sm leading-relaxed">
              {t(result.confidence_reason_key, {
                defaultValue: result.confidence_reason_en,
              })}
            </p>
            <button
              type="button"
              className="link mt-2 text-sm font-semibold"
              onClick={() => setScoringOpen(true)}
            >
              <Info size={14} aria-hidden="true" />
              {t("result.scoring.button")}
            </button>
          </div>
        </div>
      </section>

      {result.notices.length ? (
        <section className="mt-6">
          <SectionHeader title={t("result.notices.title")} />
          <div className="grid gap-2">
            {result.notices.map((notice, index) => (
              <div
                key={`${notice.key}-${index}`}
                className="notice"
                data-tone={notice.tone === "info" ? undefined : notice.tone}
              >
                {notice.tone === "danger" ? (
                  <ShieldAlert size={17} aria-hidden="true" />
                ) : notice.tone === "warn" ? (
                  <TriangleAlert size={17} aria-hidden="true" />
                ) : (
                  <Info size={17} aria-hidden="true" />
                )}
                <span>
                  {t(notice.key, {
                    ...notice.params,
                    defaultValue: notice.text_en,
                  })}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="mt-6">
        <SectionHeader
          title={t("result.reference.title")}
          action={
            result.reference_match &&
            result.reference_match.matched_by !== "none" ? (
              <span className="chip chip-brand">
                {t(result.reference_match.label_key, {
                  defaultValue: result.reference_match.matched_by,
                })}
              </span>
            ) : undefined
          }
        />
        <div className="surface surface-pad">
          {result.reference ? (
            <dl className="field-grid">
              <div className="field-row">
                <dt>{t("result.reference.name")}</dt>
                <dd>{result.reference.name}</dd>
              </div>
              {result.reference.strength ? (
                <div className="field-row">
                  <dt>{t("result.reference.strength")}</dt>
                  <dd>{result.reference.strength}</dd>
                </div>
              ) : null}
              {result.reference.manufacturer ? (
                <div className="field-row">
                  <dt>{t("result.reference.manufacturer")}</dt>
                  <dd>{result.reference.manufacturer}</dd>
                </div>
              ) : null}
              {result.reference.registration_number ? (
                <div className="field-row">
                  <dt>{t("result.reference.registration")}</dt>
                  <dd>{result.reference.registration_number}</dd>
                </div>
              ) : null}
              {result.reference.barcode ? (
                <div className="field-row">
                  <dt>{t("result.reference.barcode")}</dt>
                  <dd className="tabular">{result.reference.barcode}</dd>
                </div>
              ) : null}
              {result.reference.demo ? (
                <div className="field-row">
                  <dt>{t("result.reference.demo")}</dt>
                  <dd>
                    <span className="badge badge-demo">
                      {t("app.demoData")}
                    </span>
                  </dd>
                </div>
              ) : null}
            </dl>
          ) : (
            <div>
              <p className="font-semibold">{t("result.reference.none")}</p>
              <p className="muted mt-1 text-sm leading-relaxed">
                {t("result.reference.noneBody")}
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader
          title={t("result.fields.title")}
          description={t("result.fields.hint")}
          action={
            !editing ? (
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={beginEdit}
              >
                <PenLine size={15} aria-hidden="true" />
                {t("result.fields.edit")}
              </button>
            ) : (
              <button
                type="button"
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setEditing(false);
                  setDraft(null);
                  setRecheckError(false);
                }}
                disabled={rechecking}
              >
                {t("result.fields.cancel")}
              </button>
            )
          }
        />
        <div className="surface surface-pad">
          {editing && draft ? (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {FIELD_KEYS.map((key) => (
                  <label key={key} className="block">
                    <span className="label">{t(`fields.${key}`)}</span>
                    <input
                      className="field"
                      value={draft[key] ?? ""}
                      onChange={(event) =>
                        updateDraft(key, event.target.value)
                      }
                      dir={key === "barcode" ? "ltr" : undefined}
                      autoComplete="off"
                    />
                  </label>
                ))}
              </div>
              <p className="callout mt-3">{t("result.fields.rerunInfo")}</p>
              {recheckError ? (
                <p className="callout callout-danger mt-3" role="alert">
                  {t("result.fields.rerunError")}
                </p>
              ) : null}
              <button
                type="button"
                className="btn btn-primary mt-3"
                onClick={() => void recheck()}
                disabled={rechecking}
              >
                {rechecking ? (
                  <LoaderCircle className="spin" size={17} aria-hidden="true" />
                ) : (
                  <Check size={17} aria-hidden="true" />
                )}
                {rechecking
                  ? t("result.fields.rechecking")
                  : t("result.fields.recheck")}
              </button>
            </>
          ) : (
            <dl className="field-grid">
              {FIELD_KEYS.map((key) => {
                const raw = result.fields[key];
                const value =
                  key === "expiry_date" || key === "manufacturing_date"
                    ? formatFieldDate(raw, language)
                    : raw;
                return (
                  <div key={key} className="field-row">
                    <dt>{t(`fields.${key}`)}</dt>
                    <dd>
                      {value ?? (
                        <span className="faint">
                          {t("result.fields.empty")}
                        </span>
                      )}
                    </dd>
                  </div>
                );
              })}
            </dl>
          )}
        </div>
      </section>

      <section className="mt-6">
        <SectionHeader
          title={t("result.checks.title")}
          description={t("result.checks.hint")}
        />
        <div className="grid gap-2">
          {visibleChecks.map((check) => (
            <CheckCard key={check.id} check={check} />
          ))}
        </div>
        {orderedChecks.length > 6 ? (
          <button
            type="button"
            className="btn btn-secondary btn-block mt-3"
            onClick={() => setShowAllChecks((value) => !value)}
          >
            {showAllChecks
              ? t("result.checks.showLess")
              : t("result.checks.showAll", { count: orderedChecks.length })}
          </button>
        ) : null}
      </section>

      <section className="mt-6">
        <SectionHeader
          title={t("result.comparison.title")}
          description={t("result.comparison.hint")}
        />
        {availableComparisons.length && activeComparison ? (
          <div className="surface surface-pad">
            {availableComparisons.length > 1 ? (
              <div className="tab-strip mb-4" role="tablist">
                {availableComparisons.map((view) => (
                  <button
                    key={view}
                    type="button"
                    role="tab"
                    aria-selected={activeComparison === view}
                    className="tab"
                    onClick={() => setComparisonView(view)}
                  >
                    {t(`quality.view.${view}`)}
                  </button>
                ))}
              </div>
            ) : null}
            <ComparisonSlider comparison={result.comparisons[activeComparison]} />
          </div>
        ) : (
          <p className="callout">{t("result.comparison.none")}</p>
        )}
      </section>

      {qualityEntries.length ? (
        <section className="mt-6">
          <SectionHeader
            title={t("result.quality.title")}
            description={t("result.quality.hint")}
          />
          <div className="grid gap-2 sm:grid-cols-2">
            {qualityEntries.map(([view, quality]) => (
              <div
                key={view}
                className="quality-card"
                data-status={quality.status}
              >
                <StatusIcon status={qualityStatus(quality.status)} />
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <strong>
                      {t(`quality.view.${view}`, { defaultValue: view })}
                    </strong>
                    <span className="text-xs font-semibold">
                      {t(`quality.status.${quality.status}`)}
                    </span>
                  </div>
                  <p className="mt-1 text-xs">
                    {quality.width} x {quality.height} ·{" "}
                    {Math.round(quality.brightness)} / 255
                  </p>
                  {quality.issues.length ? (
                    <ul className="mt-2 space-y-1">
                      {quality.issues.map((issue, index) => (
                        <li
                          key={`${issue.code}-${index}`}
                          className="quality-issue"
                        >
                          <span>{t(issue.message_key, {
                            ...issue.params,
                            defaultValue: issue.code,
                          })}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="mt-6">
        <SectionHeader title={t("result.actions.title")} />
        <div className="grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            className="btn btn-primary"
            onClick={askSave}
            disabled={session.saved}
          >
            {session.saved ? (
              <Check size={17} aria-hidden="true" />
            ) : (
              <Save size={17} aria-hidden="true" />
            )}
            {session.saved ? t("result.actions.saved") : t("result.actions.save")}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate("/report")}
          >
            <FileText size={17} aria-hidden="true" />
            {t("result.actions.report")}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => void shareResult()}
          >
            <Share2 size={17} aria-hidden="true" />
            {t("result.actions.share")}
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => setPharmacistOpen(true)}
          >
            <Stethoscope size={17} aria-hidden="true" />
            {t("result.actions.pharmacist")}
          </button>
          <button
            type="button"
            className="btn btn-soft"
            onClick={retake}
          >
            <Camera size={17} aria-hidden="true" />
            {t("result.actions.retake")}
          </button>
          <button
            type="button"
            className="btn btn-soft"
            onClick={() => navigate("/scan")}
          >
            <Pill size={17} aria-hidden="true" />
            {t("result.actions.newScan")}
          </button>
        </div>
        <button
          type="button"
          className="link mt-3 text-sm font-semibold"
          onClick={() => setScoringOpen(true)}
        >
          <Info size={14} aria-hidden="true" />
          {t("result.scoring.button")}
        </button>
      </section>

      <footer className="mt-8 py-4 text-center">
        <p className="hint">{t("app.shortDisclaimer")}</p>
      </footer>

      <DisclaimerBar />

      <Dialog
        open={saveOpen}
        onClose={() => {
          if (!saving) setSaveOpen(false);
        }}
        title={t("result.saveDialog.title")}
        dismissible={!saving}
        footer={
          <div className="flex flex-col gap-2 sm:flex-row-reverse">
            <button
              type="button"
              className="btn btn-primary flex-1"
              onClick={() => void saveResult()}
              disabled={saving}
            >
              {saving ? (
                <LoaderCircle className="spin" size={17} aria-hidden="true" />
              ) : (
                <Save size={17} aria-hidden="true" />
              )}
              {t("result.saveDialog.accept")}
            </button>
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setSaveOpen(false)}
              disabled={saving}
            >
              {t("result.saveDialog.decline")}
            </button>
          </div>
        }
      >
        <p>{t("result.saveDialog.body")}</p>
      </Dialog>

      <Dialog
        open={pharmacistOpen}
        onClose={() => setPharmacistOpen(false)}
        title={t("result.pharmacist.title")}
        footer={
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => setPharmacistOpen(false)}
          >
            {t("result.pharmacist.close")}
          </button>
        }
      >
        <div className="space-y-3">
          <div className="flex items-start gap-2">
            <Stethoscope
              size={18}
              className="mt-0.5 flex-none text-[var(--brand)]"
              aria-hidden="true"
            />
            <p>{t("result.pharmacist.body")}</p>
          </div>
          <div className="notice" data-tone="warn">
            <ShieldAlert size={18} aria-hidden="true" />
            <span>{t("result.pharmacist.drap")}</span>
          </div>
          <div className="callout callout-danger">
            <p>{t("result.pharmacist.urgent")}</p>
          </div>
        </div>
      </Dialog>

      <Dialog
        open={scoringOpen}
        onClose={() => setScoringOpen(false)}
        title={t("result.scoring.title")}
        footer={
          <button
            type="button"
            className="btn btn-primary btn-block"
            onClick={() => setScoringOpen(false)}
          >
            {t("actions.gotIt")}
          </button>
        }
      >
        <p>{t("result.scoring.body")}</p>
        <p className="mt-2">{t("result.scoring.threshold")}</p>
        <p className="mt-3 text-xs">
          {t("result.scoring.version", {
            version: result.scoring_version,
          })}
        </p>
      </Dialog>
    </div>
  );
}
