import { useEffect, useState } from "react";
import {
  FileSearch,
  History as HistoryIcon,
  LoaderCircle,
  ScanLine,
  ShieldAlert,
  Trash2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { PageHeader } from "../components/PageHeader";
import {
  EmptyState,
  HistorySkeleton,
  VerdictBadge,
} from "../components/Ui";
import { useApp } from "../context/AppContext";
import { useToast } from "../context/ToastContext";
import { clearScans, deleteScan, listScans } from "../lib/db";
import { formatDateTime } from "../lib/format";
import type { ScanRecord } from "../types";

export function HistoryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { language, session, clearSession } = useApp();
  const { showToast } = useToast();
  const [records, setRecords] = useState<ScanRecord[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ScanRecord | null>(null);
  const [deleteAllOpen, setDeleteAllOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listScans()
      .then((items) => {
        if (cancelled) return;
        setRecords(items);
        setLoadError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(true);
        setRecords([]);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const retry = () => {
    setRecords(null);
    setLoadError(false);
    setReloadKey((value) => value + 1);
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setBusy(true);
    try {
      await deleteScan(deleteTarget.id);
      setRecords((current) =>
        current ? current.filter((item) => item.id !== deleteTarget.id) : current,
      );
      if (session?.result.analysis_id === deleteTarget.id) clearSession();
      setDeleteTarget(null);
      showToast(t("history.deleteDialog.success"));
    } catch {
      showToast(t("errors.genericBody"), "error");
    } finally {
      setBusy(false);
    }
  };

  const confirmDeleteAll = async () => {
    setBusy(true);
    try {
      await clearScans();
      setRecords([]);
      clearSession();
      setDeleteAllOpen(false);
      showToast(t("history.deleteAllDialog.success"));
    } catch {
      showToast(t("errors.genericBody"), "error");
    } finally {
      setBusy(false);
    }
  };

  const count = records?.length ?? 0;

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("history.count", { count })}
        title={t("history.title")}
        description={t("history.subtitle")}
        actions={
          count > 0 ? (
            <button
              type="button"
              className="btn btn-danger btn-sm"
              onClick={() => setDeleteAllOpen(true)}
            >
              <Trash2 size={15} aria-hidden="true" />
              {t("history.deleteAll")}
            </button>
          ) : undefined
        }
      />

      <div className="notice mb-4">
        <ShieldAlert size={17} aria-hidden="true" />
        <span>{t("history.localOnly")}</span>
      </div>

      {loadError ? (
        <div className="callout callout-warn mb-4" role="alert">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span>{t("history.loadError")}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={retry}
            >
              {t("history.retry")}
            </button>
          </div>
        </div>
      ) : null}

      {records === null ? <HistorySkeleton /> : null}

      {records && records.length === 0 && !loadError ? (
        <EmptyState
          icon={<HistoryIcon size={30} aria-hidden="true" />}
          title={t("history.empty.title")}
          body={t("history.empty.body")}
          action={
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => navigate("/scan")}
            >
              <ScanLine size={17} aria-hidden="true" />
              {t("history.empty.cta")}
            </button>
          }
        />
      ) : null}

      {records && records.length > 0 ? (
        <div className="grid gap-3">
          {records.map((record) => {
            const name =
              record.result.fields.product_name ?? t("history.unnamed");
            const photo = record.photos.front;
            return (
              <div key={record.id} className="history-card">
                <Link
                  to={`/saved/${record.id}`}
                  className="flex min-w-0 flex-1 gap-3"
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
                <button
                  type="button"
                  className="icon-btn flex-none"
                  onClick={() => setDeleteTarget(record)}
                  aria-label={t("history.delete")}
                  title={t("history.delete")}
                >
                  <Trash2 size={17} aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      ) : null}

      <Dialog
        open={deleteTarget !== null}
        onClose={() => {
          if (!busy) setDeleteTarget(null);
        }}
        title={t("history.deleteDialog.title")}
        dismissible={!busy}
        footer={
          <div className="flex flex-col gap-2 sm:flex-row-reverse">
            <button
              type="button"
              className="btn btn-danger flex-1"
              onClick={() => void confirmDelete()}
              disabled={busy}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} aria-hidden="true" />
              ) : (
                <Trash2 size={17} aria-hidden="true" />
              )}
              {t("history.deleteDialog.confirm")}
            </button>
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setDeleteTarget(null)}
              disabled={busy}
            >
              {t("actions.cancel")}
            </button>
          </div>
        }
      >
        <p>{t("history.deleteDialog.body")}</p>
      </Dialog>

      <Dialog
        open={deleteAllOpen}
        onClose={() => {
          if (!busy) setDeleteAllOpen(false);
        }}
        title={t("history.deleteAllDialog.title")}
        dismissible={!busy}
        footer={
          <div className="flex flex-col gap-2 sm:flex-row-reverse">
            <button
              type="button"
              className="btn btn-danger flex-1"
              onClick={() => void confirmDeleteAll()}
              disabled={busy}
            >
              {busy ? (
                <LoaderCircle className="spin" size={17} aria-hidden="true" />
              ) : (
                <Trash2 size={17} aria-hidden="true" />
              )}
              {t("history.deleteAllDialog.confirm")}
            </button>
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setDeleteAllOpen(false)}
              disabled={busy}
            >
              {t("actions.cancel")}
            </button>
          </div>
        }
      >
        <p>{t("history.deleteAllDialog.body")}</p>
      </Dialog>
    </div>
  );
}
