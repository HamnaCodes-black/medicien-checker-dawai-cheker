import { useEffect, useRef, useState } from "react";
import {
  Camera,
  Check,
  LoaderCircle,
  ScanLine,
  ShieldAlert,
  ShieldQuestion,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "../components/PageHeader";
import { useApp } from "../context/AppContext";
import { ApiError, analyzePack } from "../lib/api";
import type { AnalysisResult } from "../types";

const STEPS = [
  { key: "photo", icon: Camera },
  { key: "barcode", icon: ScanLine },
  { key: "text", icon: ScanLine },
  { key: "reference", icon: ShieldQuestion },
  { key: "scoring", icon: ShieldQuestion },
];

type Failure = "network" | "error";

export function AnalyzingPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pendingPhotos, setSession, setPendingPhotos } = useApp();
  const [stage, setStage] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [failure, setFailure] = useState<Failure | null>(null);
  const requestRef = useRef<{
    attempt: number;
    promise: Promise<AnalysisResult>;
  } | null>(null);

  useEffect(() => {
    if (!pendingPhotos) return;
    const timer = window.setInterval(() => {
      setStage((current) => Math.min(current + 1, STEPS.length - 1));
    }, 2400);
    return () => window.clearInterval(timer);
  }, [pendingPhotos, attempt]);

  useEffect(() => {
    if (!pendingPhotos) return;
    if (!requestRef.current || requestRef.current.attempt !== attempt) {
      requestRef.current = {
        attempt,
        promise: analyzePack(pendingPhotos),
      };
    }
    let active = true;
    const request = requestRef.current.promise;
    void request
      .then((result) => {
        if (!active) return;
        setSession({ result, photos: pendingPhotos, saved: false });
        setPendingPhotos(null);
        navigate("/result", { replace: true });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setFailure(
          error instanceof ApiError && error.kind === "network"
            ? "network"
            : "error",
        );
      });
    return () => {
      active = false;
    };
  }, [
    attempt,
    navigate,
    pendingPhotos,
    setPendingPhotos,
    setSession,
  ]);

  const retry = () => {
    setFailure(null);
    setStage(0);
    setAttempt((current) => current + 1);
  };

  if (!pendingPhotos) {
    return (
      <div className="page page-narrow py-10">
        <div className="surface surface-pad text-center">
          <div className="empty-visual mx-auto">
            <Camera size={30} aria-hidden="true" />
          </div>
          <h1 className="display-page font-display mt-4">
            {t("analyzing.errorTitle")}
          </h1>
          <p className="muted mt-2">{t("analyzing.errorMissing")}</p>
          <button
            type="button"
            className="btn btn-primary mt-5"
            onClick={() => navigate("/scan")}
          >
            {t("analyzing.backToScan")}
          </button>
        </div>
      </div>
    );
  }

  if (failure) {
    return (
      <div className="page page-narrow py-10">
        <div className="surface surface-pad text-center">
          <div className="empty-visual mx-auto">
            <TriangleAlert size={30} aria-hidden="true" />
          </div>
          <h1 className="display-page font-display mt-4">
            {failure === "network"
              ? t("analyzing.networkTitle")
              : t("analyzing.errorTitle")}
          </h1>
          <p className="muted mt-2">
            {failure === "network"
              ? t("analyzing.networkBody")
              : t("analyzing.errorBody")}
          </p>
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-center">
            <button
              type="button"
              className="btn btn-primary"
              onClick={retry}
            >
              {t("analyzing.retry")}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => navigate("/scan")}
            >
              {t("analyzing.backToScan")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page page-narrow py-8">
      <PageHeader
        eyebrow={t("app.tagline")}
        title={t("analyzing.title")}
        description={t("analyzing.subtitle")}
      />

      <div className="scan-visual" aria-hidden="true">
        <span className="scan-doc">
          <ScanLine size={44} />
        </span>
        <span className="scan-line" />
        <span className="scan-corner tl" />
        <span className="scan-corner tr" />
        <span className="scan-corner bl" />
        <span className="scan-corner br" />
      </div>

      <section className="surface surface-pad mt-5" aria-live="polite">
        <div className="flex items-center gap-2">
          <LoaderCircle
            className="spin text-[var(--brand)]"
            size={18}
            aria-hidden="true"
          />
          <span className="text-sm font-semibold">
            {t(`analyzing.steps.${STEPS[stage].key}`)}
          </span>
        </div>
        <div className="progress-track mt-3">
          <div
            className="progress-fill"
            style={{ width: `${((stage + 1) / STEPS.length) * 100}%` }}
          />
        </div>
        <ul className="checklist mt-4">
          {STEPS.map((item, index) => {
            const state =
              index < stage ? "done" : index === stage ? "active" : "pending";
            const Icon = item.icon;
            return (
              <li key={item.key} className="checklist-item" data-state={state}>
                <span className="checklist-dot">
                  {state === "done" ? (
                    <Check size={13} aria-hidden="true" />
                  ) : state === "active" ? (
                    <Icon size={13} aria-hidden="true" />
                  ) : (
                    <span className="text-[10px]">{index + 1}</span>
                  )}
                </span>
                <span>{t(`analyzing.steps.${item.key}`)}</span>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="notice mt-4">
        <ShieldAlert size={17} aria-hidden="true" />
        <span>{t("analyzing.warning")}</span>
      </div>

      <button
        type="button"
        className="btn btn-ghost btn-block mt-4"
        onClick={() => navigate("/scan")}
      >
        {t("analyzing.cancel")}
      </button>
    </div>
  );
}
