import { useEffect, useState, type FormEvent } from "react";
import {
  FileImage,
  ImagePlus,
  LoaderCircle,
  LockKeyhole,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
  X,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { PageHeader, SectionHeader } from "../components/PageHeader";
import { ReferenceSkeleton, Toggle } from "../components/Ui";
import { useApp } from "../context/AppContext";
import { useToast } from "../context/ToastContext";
import {
  addReference,
  apiAssetUrl,
  deleteReference,
  listReferences,
} from "../lib/api";
import { blobToDataUrl } from "../lib/images";
import type { ReferencePublic } from "../types";

type ImageSlot = "front" | "back" | "batch";

interface SelectedImage {
  file: File;
  preview: string;
}

const EMPTY_FORM = {
  name: "",
  strength: "",
  manufacturer: "",
  regNo: "",
  barcode: "",
  barcodePrefix: "",
  batchRegex: "",
  regRegex: "",
  colorHex: "",
};

const MAX_IMAGE_SIZE = 15 * 1024 * 1024;

export function AdminPage() {
  const { t } = useTranslation();
  const { adminLinkEnabled, setAdminLinkEnabled } = useApp();
  const { showToast } = useToast();
  const [references, setReferences] = useState<ReferencePublic[] | null>(null);
  const [listError, setListError] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [images, setImages] = useState<Record<ImageSlot, SelectedImage | null>>({
    front: null,
    back: null,
    batch: null,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<ReferencePublic | null>(
    null,
  );
  const [deleting, setDeleting] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!adminLinkEnabled) return;
    let cancelled = false;
    listReferences()
      .then((items) => {
        if (cancelled) return;
        setReferences(items);
        setListError(false);
      })
      .catch(() => {
        if (cancelled) return;
        setListError(true);
        setReferences([]);
      });
    return () => {
      cancelled = true;
    };
  }, [adminLinkEnabled, reloadKey]);

  const refreshReferences = () => {
    setReferences(null);
    setListError(false);
    setReloadKey((value) => value + 1);
  };

  const setField = (key: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const chooseImage = async (slot: ImageSlot, file: File | undefined) => {
    if (!file) return;
    if (
      file.size > MAX_IMAGE_SIZE ||
      (file.type && !file.type.startsWith("image/"))
    ) {
      setFormError(t("admin.add.imageError"));
      return;
    }
    try {
      const preview = await blobToDataUrl(file);
      setImages((current) => ({ ...current, [slot]: { file, preview } }));
      setFormError(null);
    } catch {
      setFormError(t("admin.add.imageError"));
    }
  };

  const removeImage = (slot: ImageSlot) => {
    setImages((current) => ({ ...current, [slot]: null }));
  };

  const resetForm = () => {
    setForm({ ...EMPTY_FORM });
    setImages({ front: null, back: null, batch: null });
    setFormError(null);
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (
      !form.name.trim() ||
      !form.manufacturer.trim() ||
      !form.regNo.trim() ||
      !images.front
    ) {
      setFormError(t("admin.add.required"));
      return;
    }
    for (const pattern of [form.batchRegex, form.regRegex]) {
      if (!pattern.trim()) continue;
      try {
        new RegExp(pattern);
      } catch {
        setFormError(t("admin.add.invalidRegex"));
        return;
      }
    }
    setSubmitting(true);
    setFormError(null);
    try {
      await addReference({
        name: form.name.trim(),
        manufacturer: form.manufacturer.trim(),
        regNo: form.regNo.trim(),
        strength: form.strength.trim() || undefined,
        barcode: form.barcode.trim() || undefined,
        barcodePrefix: form.barcodePrefix.trim() || undefined,
        batchRegex: form.batchRegex.trim() || undefined,
        regRegex: form.regRegex.trim() || undefined,
        colorHex: form.colorHex.trim() || undefined,
        front: images.front.file,
        back: images.back?.file ?? null,
        batch: images.batch?.file ?? null,
      });
      showToast(t("admin.add.success"));
      resetForm();
      setReloadKey((value) => value + 1);
    } catch {
      setFormError(t("admin.add.error"));
    } finally {
      setSubmitting(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await deleteReference(deleteTarget.id);
      setReferences((current) =>
        current
          ? current.filter((item) => item.id !== deleteTarget.id)
          : current,
      );
      setDeleteTarget(null);
      showToast(t("admin.delete.success"));
    } catch {
      showToast(t("admin.delete.error"), "error");
    } finally {
      setDeleting(false);
    }
  };

  if (!adminLinkEnabled) {
    return (
      <div className="page page-narrow py-8">
        <PageHeader
          eyebrow={t("app.demoData")}
          title={t("admin.gate.title")}
          description={t("admin.gate.body")}
        />
        <div className="surface surface-pad">
          <Toggle
            id="reference-tools-toggle"
            checked={false}
            onChange={setAdminLinkEnabled}
            label={t("admin.gate.toggle")}
            description={t("admin.gate.hint")}
          />
        </div>
        <Link to="/how-it-works" className="btn btn-ghost btn-block mt-4">
          {t("how.backHome")}
        </Link>
      </div>
    );
  }

  const count = references?.length ?? 0;

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("app.demoData")}
        title={t("admin.title")}
        description={t("admin.subtitle")}
        actions={
          <button
            type="button"
            className="btn btn-secondary btn-sm"
                onClick={refreshReferences}
          >
            <RefreshCw size={15} aria-hidden="true" />
            {t("admin.list.refresh")}
          </button>
        }
      />

      <div className="notice notice-demo mb-4">
        <ShieldAlert size={17} aria-hidden="true" />
        <span>{t("admin.demoNotice")}</span>
      </div>

      <section>
        <SectionHeader
          title={t("admin.list.title")}
          action={
            <span className="badge badge-demo">
              {t("admin.list.count", { count })}
            </span>
          }
        />
        {listError ? (
          <div className="callout callout-warn mb-3" role="alert">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <span>{t("admin.list.error")}</span>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
            onClick={refreshReferences}
              >
                {t("admin.list.retry")}
              </button>
            </div>
          </div>
        ) : null}
        {references === null ? (
          <>
            <p className="hint mb-2" role="status">
              {t("admin.list.loading")}
            </p>
            <ReferenceSkeleton />
          </>
        ) : null}
        {references && references.length === 0 && !listError ? (
          <p className="callout">{t("admin.list.empty")}</p>
        ) : null}
        {references && references.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-2">
            {references.map((reference) => (
              <article key={reference.id} className="surface surface-pad">
                <div className="flex items-start gap-3">
                  <span className="history-thumb">
                    {reference.images.front ? (
                      <img
                        src={apiAssetUrl(reference.images.front)}
                        alt={reference.name}
                      />
                    ) : (
                      <span className="grid h-full place-items-center text-[var(--muted)]">
                        <FileImage size={20} aria-hidden="true" />
                      </span>
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="font-semibold leading-snug">
                        {reference.name}
                      </h3>
                      <span className="badge badge-demo">
                        {reference.demo
                          ? t("admin.badges.demo")
                          : t("admin.badges.local")}
                      </span>
                    </div>
                    <p className="muted mt-1 text-xs">
                      {[reference.strength, reference.manufacturer]
                        .filter(Boolean)
                        .join(" · ") || "-"}
                    </p>
                    <p className="muted mt-1 text-xs">
                      {reference.registration_number ?? "-"}
                    </p>
                    {reference.barcode ? (
                      <p className="muted mt-1 text-xs tabular">
                        {reference.barcode}
                      </p>
                    ) : null}
                    {reference.color_hex ? (
                      <span className="mt-2 inline-flex items-center gap-1.5 text-xs">
                        <span
                          className="inline-block h-3.5 w-3.5 rounded-full border border-[var(--line)]"
                          style={{ background: reference.color_hex }}
                          aria-hidden="true"
                        />
                        {reference.color_hex}
                      </span>
                    ) : null}
                  </div>
                  <button
                    type="button"
                    className="icon-btn flex-none"
                    onClick={() => setDeleteTarget(reference)}
                    disabled={reference.demo}
                    aria-label={
                      reference.demo
                        ? t("admin.delete.demoLocked")
                        : t("admin.delete.button")
                    }
                    title={
                      reference.demo
                        ? t("admin.delete.demoLocked")
                        : t("admin.delete.button")
                    }
                  >
                    {reference.demo ? (
                      <LockKeyhole size={16} aria-hidden="true" />
                    ) : (
                      <Trash2 size={16} aria-hidden="true" />
                    )}
                  </button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
      </section>

      <section className="mt-8">
        <SectionHeader
          title={t("admin.add.title")}
          description={t("admin.add.subtitle")}
        />
        <form className="surface surface-pad" onSubmit={submit} noValidate>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block sm:col-span-2">
              <span className="label">{t("admin.add.name")} *</span>
              <input
                className="field"
                value={form.name}
                onChange={(event) => setField("name", event.target.value)}
                placeholder={t("admin.form.namePlaceholder")}
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.strength")}</span>
              <input
                className="field"
                value={form.strength}
                onChange={(event) => setField("strength", event.target.value)}
                placeholder={t("admin.form.strengthPlaceholder")}
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.manufacturer")} *</span>
              <input
                className="field"
                value={form.manufacturer}
                onChange={(event) =>
                  setField("manufacturer", event.target.value)
                }
                placeholder={t("admin.form.manufacturerPlaceholder")}
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.registration")} *</span>
              <input
                className="field"
                value={form.regNo}
                onChange={(event) => setField("regNo", event.target.value)}
                placeholder={t("admin.form.registrationPlaceholder")}
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.barcode")}</span>
              <input
                className="field"
                value={form.barcode}
                onChange={(event) => setField("barcode", event.target.value)}
                placeholder={t("admin.form.barcodePlaceholder")}
                inputMode="numeric"
                dir="ltr"
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.barcodePrefix")}</span>
              <input
                className="field"
                value={form.barcodePrefix}
                onChange={(event) =>
                  setField("barcodePrefix", event.target.value)
                }
                placeholder={t("admin.form.prefixPlaceholder")}
                inputMode="numeric"
                dir="ltr"
                autoComplete="off"
              />
            </label>
            <label className="block">
              <span className="label">{t("admin.add.colorHex")}</span>
              <input
                className="field"
                value={form.colorHex}
                onChange={(event) => setField("colorHex", event.target.value)}
                placeholder={t("admin.form.colorPlaceholder")}
                dir="ltr"
                autoComplete="off"
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="label">{t("admin.add.batchRegex")}</span>
              <input
                className="field"
                value={form.batchRegex}
                onChange={(event) =>
                  setField("batchRegex", event.target.value)
                }
                placeholder={t("admin.form.batchRegexPlaceholder")}
                dir="ltr"
                autoComplete="off"
              />
            </label>
            <label className="block sm:col-span-2">
              <span className="label">{t("admin.add.regRegex")}</span>
              <input
                className="field"
                value={form.regRegex}
                onChange={(event) => setField("regRegex", event.target.value)}
                placeholder={t("admin.form.regRegexPlaceholder")}
                dir="ltr"
                autoComplete="off"
              />
            </label>
          </div>

          <fieldset className="mt-5">
            <legend className="label">{t("admin.add.images")}</legend>
            <div className="grid gap-3 sm:grid-cols-3">
              <ImageField
                label={`${t("admin.add.front")} *`}
                image={images.front}
                onChoose={(file) => void chooseImage("front", file)}
                onRemove={() => removeImage("front")}
                chooseLabel={t("actions.upload")}
                removeLabel={t("actions.remove")}
              />
              <ImageField
                label={t("admin.add.back")}
                image={images.back}
                onChoose={(file) => void chooseImage("back", file)}
                onRemove={() => removeImage("back")}
                chooseLabel={t("actions.upload")}
                removeLabel={t("actions.remove")}
              />
              <ImageField
                label={t("admin.add.batch")}
                image={images.batch}
                onChoose={(file) => void chooseImage("batch", file)}
                onRemove={() => removeImage("batch")}
                chooseLabel={t("actions.upload")}
                removeLabel={t("actions.remove")}
              />
            </div>
          </fieldset>

          {formError ? (
            <p className="callout callout-danger mt-4" role="alert">
              {formError}
            </p>
          ) : null}

          <button
            type="submit"
            className="btn btn-primary btn-block mt-5"
            disabled={submitting}
          >
            {submitting ? (
              <LoaderCircle className="spin" size={17} aria-hidden="true" />
            ) : (
              <Plus size={17} aria-hidden="true" />
            )}
            {submitting ? t("admin.add.saving") : t("admin.add.submit")}
          </button>
        </form>
      </section>

      <Link to="/how-it-works" className="btn btn-ghost btn-block mt-6">
        {t("admin.back")}
      </Link>

      <Dialog
        open={deleteTarget !== null}
        onClose={() => {
          if (!deleting) setDeleteTarget(null);
        }}
        title={t("admin.delete.title")}
        dismissible={!deleting}
        footer={
          <div className="flex flex-col gap-2 sm:flex-row-reverse">
            <button
              type="button"
              className="btn btn-danger flex-1"
              onClick={() => void confirmDelete()}
              disabled={deleting}
            >
              {deleting ? (
                <LoaderCircle className="spin" size={17} aria-hidden="true" />
              ) : (
                <Trash2 size={17} aria-hidden="true" />
              )}
              {t("admin.delete.confirm")}
            </button>
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setDeleteTarget(null)}
              disabled={deleting}
            >
              {t("actions.cancel")}
            </button>
          </div>
        }
      >
        <p>{t("admin.delete.body")}</p>
      </Dialog>
    </div>
  );
}

function ImageField({
  label,
  image,
  onChoose,
  onRemove,
  chooseLabel,
  removeLabel,
}: {
  label: string;
  image: SelectedImage | null;
  onChoose: (file: File | undefined) => void;
  onRemove: () => void;
  chooseLabel: string;
  removeLabel: string;
}) {
  return (
    <div>
      <p className="label">{label}</p>
      {image ? (
        <div className="overflow-hidden rounded-xl border border-[var(--line)]">
          <img
            src={image.preview}
            alt=""
            className="aspect-[4/3] w-full object-cover"
          />
          <div className="flex gap-1 p-2">
            <label className="btn btn-secondary btn-sm flex-1 cursor-pointer">
              <ImagePlus size={14} aria-hidden="true" />
              {chooseLabel}
              <input
                type="file"
                accept="image/*"
                className="visually-hidden"
                onChange={(event) => {
                  onChoose(event.target.files?.[0]);
                  event.target.value = "";
                }}
              />
            </label>
            <button
              type="button"
              className="icon-btn"
              onClick={onRemove}
              aria-label={removeLabel}
            >
              <X size={15} aria-hidden="true" />
            </button>
          </div>
        </div>
      ) : (
        <label className="flex aspect-[4/3] cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--line-strong)] bg-[var(--surface-soft)] p-3 text-center text-xs text-[var(--muted)]">
          <ImagePlus size={22} aria-hidden="true" />
          <span>{chooseLabel}</span>
          <input
            type="file"
            accept="image/*"
            className="visually-hidden"
            onChange={(event) => {
              onChoose(event.target.files?.[0]);
              event.target.value = "";
            }}
          />
        </label>
      )}
    </div>
  );
}
