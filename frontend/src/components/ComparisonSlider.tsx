import { useId, useState, type CSSProperties } from "react";
import { Eye, EyeOff, MoveHorizontal } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ViewComparison } from "../types";
import { formatPercent } from "../lib/format";

export function ComparisonSlider({
  comparison,
}: {
  comparison: ViewComparison;
}) {
  const { t } = useTranslation();
  const [position, setPosition] = useState(50);
  const [overlay, setOverlay] = useState(false);
  const sliderId = useId();
  const images = comparison.images;
  const hasOverlay = Boolean(images.overlay);

  if (!images.reference || !images.captured) {
    return (
      <p className="callout">
        {t("result.comparison.none")}
      </p>
    );
  }

  const frameStyle = { "--position": `${position}%` } as CSSProperties;

  return (
    <div>
      <div
        className={`comparison-frame${comparison.view === "batch" ? " is-wide" : ""}`}
        style={frameStyle}
      >
        <img
          className="comparison-layer"
          src={overlay && images.overlay ? images.overlay : images.reference}
          alt={t("result.comparison.reference")}
        />
        {!overlay ? (
          <img
            className="comparison-layer comparison-after"
            src={images.captured}
            alt={t("result.comparison.photo")}
          />
        ) : null}
        {!overlay ? (
          <>
            <span className="comparison-label start">
              {t("result.comparison.reference")}
            </span>
            <span className="comparison-label end">
              {t("result.comparison.photo")}
            </span>
            <span className="comparison-divider" aria-hidden="true" />
            <span className="comparison-handle" aria-hidden="true">
              <MoveHorizontal size={18} />
            </span>
            <label htmlFor={sliderId} className="visually-hidden">
              {t("result.comparison.sliderLabel")}
            </label>
            <input
              id={sliderId}
              className="comparison-input"
              type="range"
              min={0}
              max={100}
              value={position}
              dir="ltr"
              onChange={(event) => setPosition(Number(event.target.value))}
            />
          </>
        ) : (
          <span className="comparison-label start">
            {t("result.comparison.overlay")}
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="chip chip-brand">
          {t("result.comparison.similarity", {
            percent: formatPercent(comparison.combined_similarity),
          })}
        </span>
        {comparison.alignment === "resize" ? (
          <span className="chip chip-warn">{t("result.comparison.resize")}</span>
        ) : null}
        {hasOverlay ? (
          <button
            type="button"
            className="btn btn-secondary btn-sm ms-auto"
            onClick={() => setOverlay((value) => !value)}
            aria-pressed={overlay}
          >
            {overlay ? (
              <EyeOff size={15} aria-hidden="true" />
            ) : (
              <Eye size={15} aria-hidden="true" />
            )}
            {overlay
              ? t("result.comparison.showComparison")
              : t("result.comparison.showOverlay")}
          </button>
        ) : null}
      </div>

      <div className="mt-4">
        <p className="text-sm font-semibold">
          {t("result.comparison.regions", {
            count: comparison.regions.length,
          })}
        </p>
        {comparison.regions.length ? (
          <ul className="mt-2 grid gap-1.5">
            {comparison.regions.map((region, index) => (
              <li
                key={`${region.label_key}-${index}`}
                className="flex items-start gap-2 text-sm text-[var(--muted)]"
              >
                <span
                  className="mt-1.5 inline-block h-2 w-2 flex-none rounded-full"
                  style={{
                    background:
                      region.severity === "fail"
                        ? "var(--danger)"
                        : "var(--warn)",
                  }}
                  aria-hidden="true"
                />
                <span>
                  {t(region.label_key, { defaultValue: region.label_en })}
                  <span className="faint"> · {Math.round(region.difference * 1000) / 10}%</span>
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted mt-1 text-sm">{t("result.comparison.noRegions")}</p>
        )}
      </div>
    </div>
  );
}
