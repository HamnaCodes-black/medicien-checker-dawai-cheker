import { useState } from "react";
import { FlaskConical, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { DEMO_CASES, type DemoCaseId } from "../lib/demo";
import { loadDemoPhotos } from "../lib/images";
import { Dialog } from "./Dialog";

export function DemoPicker({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { setPendingPhotos } = useApp();
  const [loading, setLoading] = useState<DemoCaseId | null>(null);
  const [error, setError] = useState(false);

  const choose = async (id: DemoCaseId) => {
    setLoading(id);
    setError(false);
    try {
      const photos = await loadDemoPhotos(id);
      setPendingPhotos(photos);
      onClose();
      navigate("/analyzing");
    } catch {
      setError(true);
    } finally {
      setLoading(null);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t("demo.pickerTitle")}
      dismissible={loading === null}
    >
      <p>{t("demo.pickerBody")}</p>
      <div className="mt-4 grid gap-2">
        {DEMO_CASES.map((item) => {
          const isLoading = loading === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className="surface flex w-full items-start gap-3 p-3 text-start transition hover:border-[var(--brand)] disabled:opacity-60"
              onClick={() => void choose(item.id)}
              disabled={loading !== null}
            >
              <span
                className="feature-icon"
                data-tone={item.tone}
                aria-hidden="true"
              >
                {isLoading ? (
                  <LoaderCircle className="spin" size={20} />
                ) : (
                  <FlaskConical size={20} />
                )}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-semibold">{t(item.labelKey)}</span>
                <span className="muted mt-0.5 block text-sm leading-snug">
                  {t(item.descriptionKey)}
                </span>
              </span>
              <span className="badge badge-demo mt-1">{t("demo.badge")}</span>
            </button>
          );
        })}
      </div>
      {loading ? (
        <p className="hint mt-3">{t("demo.loading")}</p>
      ) : null}
      {error ? (
        <p className="callout callout-danger mt-3" role="alert">
          {t("demo.loadError")}
        </p>
      ) : null}
    </Dialog>
  );
}
