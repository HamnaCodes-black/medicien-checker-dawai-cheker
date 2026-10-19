import { useEffect, useState } from "react";
import { CircleHelp, TriangleAlert } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { Spinner } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { getScan } from "../lib/db";
import { ResultPage } from "./ResultPage";

type LoadState = "loading" | "ready" | "error" | "missing";

export function SavedResultPage() {
  const { id } = useParams();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setSession, clearSession } = useApp();
  const [state, setState] = useState<LoadState>("loading");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    getScan(id)
      .then((record) => {
        if (cancelled) return;
        if (!record) {
          clearSession();
          setState("missing");
          return;
        }
        setSession({
          result: record.result,
          photos: record.photos,
          saved: true,
        });
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [clearSession, id, reloadKey, setSession]);

  const retry = () => {
    setState("loading");
    setReloadKey((value) => value + 1);
  };

  const view: LoadState = id ? state : "missing";

  if (view === "ready") return <ResultPage />;

  if (view === "loading") {
    return (
      <div className="page page-narrow py-10" aria-busy="true">
        <div className="surface surface-pad flex items-center justify-center gap-3 py-12">
          <Spinner size={22} />
          <span className="font-semibold">{t("result.title")}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="page page-narrow py-10">
      <div className="surface surface-pad text-center">
        <div className="empty-visual mx-auto">
          {view === "missing" ? (
            <CircleHelp size={30} aria-hidden="true" />
          ) : (
            <TriangleAlert size={30} aria-hidden="true" />
          )}
        </div>
        <h1 className="display-page font-display mt-4">
          {view === "missing"
            ? t("result.notFound.title")
            : t("errors.loadFailed")}
        </h1>
        <p className="muted mt-2">
          {view === "missing"
            ? t("result.notFound.body")
            : t("errors.genericBody")}
        </p>
        <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
          {view === "error" ? (
            <button
              type="button"
              className="btn btn-primary"
              onClick={retry}
            >
              {t("history.retry")}
            </button>
          ) : (
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate("/scan")}
            >
              {t("result.notFound.cta")}
            </button>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => navigate("/history")}
          >
            {t("history.title")}
          </button>
        </div>
      </div>
    </div>
  );
}
