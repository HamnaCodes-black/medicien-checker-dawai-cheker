import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
} from "react";
import {
  Camera,
  CameraOff,
  Check,
  ImagePlus,
  LoaderCircle,
  RefreshCw,
  ScanLine,
  ShieldAlert,
  SwitchCamera,
  Trash2,
  TriangleAlert,
  Upload,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { Dialog } from "../components/Dialog";
import { PageHeader, SectionHeader } from "../components/PageHeader";
import { useApp } from "../context/AppContext";
import { useToast } from "../context/ToastContext";
import {
  QUALITY_ISSUE_KEYS,
  assessLocalQuality,
  captureVideoFrame,
  compressImageSource,
  sampleVideoFeedback,
  type LiveFeedback,
} from "../lib/images";
import type { LocalQuality, PhotoMap, ViewName } from "../types";

const REQUIRED_VIEWS = ["front", "back", "batch"] as const;
const ALL_VIEWS: ViewName[] = ["front", "back", "batch", "blister"];
const MAX_FILE_SIZE = 15 * 1024 * 1024;

type CameraFacing = "environment" | "user";
type CameraError = "denied" | "unavailable" | "insecure" | "error" | null;

export function CapturePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pendingPhotos, setPendingPhotos } = useApp();
  const { showToast } = useToast();

  const [photos, setPhotos] = useState<PhotoMap>(() => pendingPhotos ?? {});
  const [qualities, setQualities] = useState<
    Partial<Record<ViewName, LocalQuality>>
  >({});
  const [view, setView] = useState<ViewName>(() => {
    if (!pendingPhotos?.front) return "front";
    if (!pendingPhotos.back) return "back";
    if (!pendingPhotos.batch) return "batch";
    return "front";
  });
  const [cameraStarting, setCameraStarting] = useState(false);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<CameraError>(null);
  const [facing, setFacing] = useState<CameraFacing>("environment");
  const [liveFeedback, setLiveFeedback] = useState<LiveFeedback | null>(null);
  const [processing, setProcessing] = useState(false);
  const [qualityDialog, setQualityDialog] = useState<{
    view: ViewName;
    quality: LocalQuality;
  } | null>(null);
  const [online, setOnline] = useState(() => navigator.onLine);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const uploadRef = useRef<HTMLInputElement>(null);
  const deviceRef = useRef<HTMLInputElement>(null);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setCameraActive(false);
    setCameraStarting(false);
    setLiveFeedback(null);
  }, []);

  const startCamera = useCallback(async (nextFacing: CameraFacing) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCameraError(window.isSecureContext ? "unavailable" : "insecure");
      return;
    }
    if (!window.isSecureContext) {
      setCameraError("insecure");
      return;
    }
    setCameraError(null);
    setCameraStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: nextFacing },
          width: { ideal: 1920 },
          height: { ideal: 1440 },
        },
      });
      streamRef.current = stream;
      setFacing(nextFacing);
      setCameraActive(true);
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        void videoRef.current.play().catch(() => undefined);
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setCameraError("denied");
      } else if (
        error instanceof DOMException &&
        (error.name === "NotFoundError" ||
          error.name === "OverconstrainedError")
      ) {
        setCameraError("unavailable");
      } else {
        setCameraError("error");
      }
    } finally {
      setCameraStarting(false);
    }
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!cameraActive || !video || !streamRef.current) return;
    video.srcObject = streamRef.current;
    void video.play().catch(() => undefined);
  }, [cameraActive]);

  useEffect(() => {
    if (!cameraActive) return;
    const interval = window.setInterval(() => {
      if (videoRef.current) {
        setLiveFeedback(sampleVideoFeedback(videoRef.current));
      }
    }, 700);
    return () => window.clearInterval(interval);
  }, [cameraActive]);

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  useEffect(() => {
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  const applyPhoto = (target: ViewName, dataUrl: string, quality: LocalQuality) => {
    setPhotos((current) => ({ ...current, [target]: dataUrl }));
    setQualities((current) => ({ ...current, [target]: quality }));
    setProcessing(false);
    if (quality.status === "fail") {
      setQualityDialog({ view: target, quality });
      return;
    }
    showToast(t("capture.photoAdded"));
    const requiredIndex = REQUIRED_VIEWS.indexOf(target as (typeof REQUIRED_VIEWS)[number]);
    if (requiredIndex >= 0 && requiredIndex < REQUIRED_VIEWS.length - 1) {
      setView(REQUIRED_VIEWS[requiredIndex + 1]);
    }
  };

  const processSource = async (
    target: ViewName,
    source: File | string,
  ) => {
    setProcessing(true);
    try {
      const compressed = await compressImageSource(source, {
        maxSide: 1800,
        quality: 0.9,
      });
      const quality = await assessLocalQuality(compressed);
      applyPhoto(target, compressed, quality);
    } catch {
      setProcessing(false);
      showToast(t("capture.error"), "error");
    }
  };

  const handleFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (
      file.size > MAX_FILE_SIZE ||
      (file.type && !file.type.startsWith("image/"))
    ) {
      showToast(t("capture.error"), "error");
      return;
    }
    void processSource(view, file);
  };

  const takePhoto = () => {
    const video = videoRef.current;
    if (!video) return;
    const frame = captureVideoFrame(video);
    if (!frame) {
      setCameraError("error");
      return;
    }
    stopCamera();
    void processSource(view, frame);
  };

  const switchCamera = () => {
    const next = facing === "environment" ? "user" : "environment";
    stopCamera();
    void startCamera(next);
  };

  const selectView = (next: ViewName) => {
    stopCamera();
    setCameraError(null);
    setView(next);
  };

  const removePhoto = (target: ViewName) => {
    setPhotos((current) => {
      const next = { ...current };
      delete next[target];
      return next;
    });
    setQualities((current) => {
      const next = { ...current };
      delete next[target];
      return next;
    });
  };

  const retakeFromDialog = () => {
    if (!qualityDialog) return;
    const target = qualityDialog.view;
    setQualityDialog(null);
    removePhoto(target);
    setView(target);
    void startCamera(facing);
  };

  const requiredReady = REQUIRED_VIEWS.every((item) => Boolean(photos[item]));
  const canAnalyze = requiredReady && online && !processing;

  const beginAnalysis = () => {
    if (!requiredReady) {
      showToast(t("capture.missing"), "error");
      return;
    }
    setPendingPhotos(photos);
    navigate("/analyzing");
  };

  const quality = qualities[view];
  const cameraVisible = cameraStarting || cameraActive;
  const viewIcon =
    view === "front"
      ? ScanLine
      : view === "back"
        ? Camera
        : view === "batch"
          ? ShieldAlert
          : ImagePlus;
  const ViewIcon = viewIcon;

  return (
    <div className="page py-5">
      <PageHeader
        eyebrow={t("capture.progress", {
          current: REQUIRED_VIEWS.filter((item) => photos[item]).length,
          total: REQUIRED_VIEWS.length,
        })}
        title={t("capture.title")}
        description={t("capture.subtitle")}
      />

      <div className="stepper mb-5">
        {ALL_VIEWS.map((item) => {
          const done = Boolean(photos[item]);
          const active = view === item;
          return (
            <button
              key={item}
              type="button"
              className="stepper-item"
              data-state={done ? "done" : active ? "active" : "pending"}
              onClick={() => selectView(item)}
              disabled={processing}
              aria-current={active ? "step" : undefined}
            >
              <span className="dot">
                {done ? <Check size={13} aria-hidden="true" /> : null}
              </span>
              <span>{t(`capture.steps.${item}.label`)}</span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="display-section font-display">
                  {t(`capture.steps.${view}.title`)}
                </h2>
                <span
                  className={`chip ${view === "blister" ? "" : "chip-brand"}`}
                >
                  {view === "blister"
                    ? t("capture.optional")
                    : t("capture.required")}
                </span>
              </div>
              <p className="muted mt-1 text-sm leading-relaxed">
                {t(`capture.steps.${view}.instruction`)}
              </p>
            </div>
            {photos[view] && !cameraVisible && quality ? (
              <span
                className={`badge badge-${quality.status === "ok" ? "pass" : quality.status}`}
              >
                {quality.status === "ok" ? (
                  <Check size={12} aria-hidden="true" />
                ) : (
                  <TriangleAlert size={12} aria-hidden="true" />
                )}
                {t(`quality.status.${quality.status}`)}
              </span>
            ) : null}
          </div>

          {cameraVisible ? (
            <div className="camera-stage">
              <video
                ref={videoRef}
                className="camera-video"
                autoPlay
                muted
                playsInline
                aria-label={t(`capture.steps.${view}.frame`)}
              />
              <div className="camera-overlay">
                <span className="camera-frame" aria-hidden="true" />
                <span className="live-pill" data-tone={liveFeedback?.tone}>
                  {cameraStarting ? (
                    <LoaderCircle className="spin" size={12} aria-hidden="true" />
                  ) : (
                    <span className="status-dot" aria-hidden="true" />
                  )}
                  {cameraStarting
                    ? t("capture.camera.starting")
                    : t("capture.camera.live")}
                </span>
                {!cameraStarting && liveFeedback ? (
                  <span
                    className="live-pill"
                    data-tone={liveFeedback.tone}
                    style={{ insetInlineStart: "auto", insetInlineEnd: 10 }}
                  >
                    {t(liveFeedback.key)}
                  </span>
                ) : null}
                <span className="camera-hint">
                  {t(`capture.steps.${view}.frame`)}
                </span>
              </div>
            </div>
          ) : photos[view] ? (
            <div className="photo-slot">
              <img
                src={photos[view]}
                alt={t(`capture.steps.${view}.title`)}
              />
              <div className="photo-slot-actions">
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  onClick={() => void startCamera(facing)}
                  disabled={processing}
                >
                  <RefreshCw size={15} aria-hidden="true" />
                  {t("actions.retake")}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => uploadRef.current?.click()}
                  disabled={processing}
                >
                  <Upload size={15} aria-hidden="true" />
                  {t("capture.changePhoto")}
                </button>
                <button
                  type="button"
                  className="icon-btn icon-btn-bordered"
                  onClick={() => removePhoto(view)}
                  aria-label={t("capture.removePhoto")}
                  disabled={processing}
                >
                  <Trash2 size={16} aria-hidden="true" />
                </button>
              </div>
            </div>
          ) : (
            <div className="photo-slot is-empty">
              <div className="grid h-full place-items-center p-5 text-center">
                <div>
                  <span className="empty-visual mx-auto">
                    <ViewIcon size={28} aria-hidden="true" />
                  </span>
                  <p className="mt-4 font-semibold">
                    {t(`capture.steps.${view}.frame`)}
                  </p>
                  <p className="hint mt-1">{t("capture.uploadHint")}</p>
                </div>
              </div>
            </div>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            {cameraVisible ? (
              <>
                <button
                  type="button"
                  className="btn btn-primary flex-1"
                  onClick={takePhoto}
                  disabled={cameraStarting || !cameraActive}
                >
                  <Camera size={18} aria-hidden="true" />
                  {t("actions.takePhoto")}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={switchCamera}
                  aria-label={t("actions.switchCamera")}
                  disabled={cameraStarting}
                >
                  <SwitchCamera size={18} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={stopCamera}
                >
                  <CameraOff size={18} aria-hidden="true" />
                  {t("actions.closeCamera")}
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="btn btn-primary flex-1"
                  onClick={() => void startCamera(facing)}
                  disabled={processing}
                >
                  <Camera size={18} aria-hidden="true" />
                  {t("actions.openCamera")}
                </button>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => uploadRef.current?.click()}
                  disabled={processing}
                >
                  <Upload size={18} aria-hidden="true" />
                  {t("actions.upload")}
                </button>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => deviceRef.current?.click()}
                  disabled={processing}
                  title={t("actions.deviceCamera")}
                  aria-label={t("actions.deviceCamera")}
                >
                  <ImagePlus size={18} aria-hidden="true" />
                </button>
              </>
            )}
          </div>

          {cameraVisible ? (
            <p className="hint mt-2 text-center">
              {t("capture.camera.facing", {
                facing: t(`capture.camera.${facing}`),
              })}
            </p>
          ) : null}

          <input
            ref={uploadRef}
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="visually-hidden"
            onChange={handleFile}
            tabIndex={-1}
          />
          <input
            ref={deviceRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="visually-hidden"
            onChange={handleFile}
            tabIndex={-1}
          />

          {processing ? (
            <div className="notice mt-3" role="status">
              <LoaderCircle className="spin" size={17} aria-hidden="true" />
              <span>{t("capture.quality.checking")}</span>
            </div>
          ) : null}

          {cameraError ? (
            <div className="callout callout-warn mt-3" role="alert">
              <div className="flex items-start gap-2">
                <TriangleAlert size={18} aria-hidden="true" />
                <span>{t(`capture.camera.${cameraError}`)}</span>
              </div>
            </div>
          ) : null}

          {quality && quality.status !== "ok" && !cameraVisible ? (
            <div className="quality-card mt-3" data-status={quality.status}>
              <StatusIcon status={quality.status} />
              <div>
                <strong>{t(`capture.quality.${quality.status}`)}</strong>
                {quality.issues.length ? (
                  <ul className="mt-1 space-y-1 text-sm">
                    {quality.issues.map((issue, index) => (
                      <li key={`${issue.code}-${index}`}>
                        {QUALITY_ISSUE_KEYS[issue.code]
                          ? t(QUALITY_ISSUE_KEYS[issue.code])
                          : issue.code}
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </div>
          ) : null}

          {view !== "blister" && !photos.blister && !cameraVisible ? (
            <button
              type="button"
              className="btn btn-soft mt-3 w-full"
              onClick={() => selectView("blister")}
              disabled={processing}
            >
              <ImagePlus size={17} aria-hidden="true" />
              {t("capture.addOptional")}
            </button>
          ) : null}
        </div>

        <aside className="space-y-4">
          <section className="surface surface-pad">
            <SectionHeader
              title={
                requiredReady
                  ? t("capture.readyTitle")
                  : t("capture.progress", {
                      current: REQUIRED_VIEWS.filter((item) => photos[item])
                        .length,
                      total: REQUIRED_VIEWS.length,
                    })
              }
              description={
                requiredReady ? t("capture.readyBody") : t("capture.missing")
              }
            />
            <ul className="checklist">
              {REQUIRED_VIEWS.map((item, index) => {
                const done = Boolean(photos[item]);
                return (
                  <li
                    key={item}
                    className="checklist-item"
                    data-state={done ? "done" : "pending"}
                  >
                    <span className="checklist-dot">
                      {done ? (
                        <Check size={13} aria-hidden="true" />
                      ) : (
                        <span className="text-[10px]">{index + 1}</span>
                      )}
                    </span>
                    <span className="flex-1">
                      {t(`capture.steps.${item}.label`)}
                    </span>
                    <span className="text-xs">
                      {done ? t("quality.status.ok") : t("capture.required")}
                    </span>
                  </li>
                );
              })}
              {photos.blister ? (
                <li className="checklist-item" data-state="done">
                  <span className="checklist-dot">
                    <Check size={13} aria-hidden="true" />
                  </span>
                  <span className="flex-1">
                    {t("capture.steps.blister.label")}
                  </span>
                  <span className="text-xs">{t("capture.optional")}</span>
                </li>
              ) : null}
            </ul>

            {!online ? (
              <div className="callout callout-warn mt-3" role="alert">
                {t("capture.offline")}
              </div>
            ) : null}

            <button
              type="button"
              className="btn btn-primary btn-block btn-lg mt-4"
              onClick={beginAnalysis}
              disabled={!canAnalyze}
            >
              <ScanLine size={18} aria-hidden="true" />
              {t("capture.analyze")}
            </button>
            {view === "blister" && requiredReady ? (
              <button
                type="button"
                className="btn btn-secondary btn-block mt-2"
                onClick={beginAnalysis}
                disabled={!canAnalyze}
              >
                {t("capture.skipBlister")}
              </button>
            ) : null}
          </section>

          <section className="surface surface-pad">
            <h2 className="display-section font-display">
              {t("capture.tips.title")}
            </h2>
            <ul className="mt-3 space-y-2 text-sm leading-relaxed">
              <li className="flex gap-2">
                <Check
                  size={16}
                  className="mt-0.5 flex-none text-[var(--brand)]"
                  aria-hidden="true"
                />
                <span>{t("capture.tips.light")}</span>
              </li>
              <li className="flex gap-2">
                <Check
                  size={16}
                  className="mt-0.5 flex-none text-[var(--brand)]"
                  aria-hidden="true"
                />
                <span>{t("capture.tips.fill")}</span>
              </li>
              <li className="flex gap-2">
                <Check
                  size={16}
                  className="mt-0.5 flex-none text-[var(--brand)]"
                  aria-hidden="true"
                />
                <span>{t("capture.tips.flat")}</span>
              </li>
              <li className="flex gap-2">
                <Check
                  size={16}
                  className="mt-0.5 flex-none text-[var(--brand)]"
                  aria-hidden="true"
                />
                <span>{t("capture.tips.clean")}</span>
              </li>
            </ul>
          </section>

          <button
            type="button"
            className="btn btn-soft btn-block"
            onClick={() => {
              stopCamera();
              navigate("/");
            }}
          >
            {t("actions.cancel")}
          </button>
        </aside>
      </div>

      <Dialog
        open={qualityDialog !== null}
        onClose={() => setQualityDialog(null)}
        title={t("capture.quality.retakeTitle")}
        dismissible={false}
        footer={
          <div className="flex flex-col gap-2 sm:flex-row-reverse">
            <button
              type="button"
              className="btn btn-primary flex-1"
              onClick={retakeFromDialog}
            >
              {t("actions.retake")}
            </button>
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={() => setQualityDialog(null)}
            >
              {t("capture.quality.useAnyway")}
            </button>
          </div>
        }
      >
        <p>{t("capture.quality.retakeBody")}</p>
        {qualityDialog?.quality.issues.length ? (
          <ul className="mt-3 space-y-1.5 text-sm">
            {qualityDialog.quality.issues.map((issue, index) => (
              <li key={`${issue.code}-${index}`} className="flex gap-2">
                <TriangleAlert
                  size={15}
                  className="mt-0.5 flex-none text-[var(--warn)]"
                  aria-hidden="true"
                />
                <span>
                  {QUALITY_ISSUE_KEYS[issue.code]
                    ? t(QUALITY_ISSUE_KEYS[issue.code])
                    : issue.code}
                </span>
              </li>
            ))}
          </ul>
        ) : null}
      </Dialog>
    </div>
  );
}

function StatusIcon({ status }: { status: LocalQuality["status"] }) {
  if (status === "fail") {
    return <ShieldAlert size={18} className="mt-0.5 flex-none" aria-hidden="true" />;
  }
  return (
    <TriangleAlert size={18} className="mt-0.5 flex-none" aria-hidden="true" />
  );
}
