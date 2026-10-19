import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { CheckResult } from "../types";
import { formatScore } from "../lib/format";
import { StatusBadge, StatusIcon } from "./Ui";

export function CheckCard({ check }: { check: CheckResult }) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(check.status === "fail");
  const detailId = useId();
  const title = t(check.title_key, { defaultValue: check.id });
  const explanation = t(check.explanation_key, {
    ...check.params,
    defaultValue: check.explanation_en,
  });
  const why = t(check.why_key, { defaultValue: "" });

  return (
    <article className="check-card" data-status={check.status}>
      <button
        type="button"
        className="check-summary"
        aria-expanded={expanded}
        aria-controls={detailId}
        onClick={() => setExpanded((value) => !value)}
      >
        <span className="status-icon" data-status={check.status}>
          <StatusIcon status={check.status} size={17} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-[0.95rem] font-semibold leading-snug">
              {title}
            </span>
            <StatusBadge status={check.status} />
          </span>
          <span className="muted mt-1 block text-[0.8rem] leading-snug">
            {check.weight > 0
              ? t("result.checks.points", {
                  points: formatScore(check.risk_points),
                  weight: formatScore(check.weight),
                })
              : t("result.checks.confidence", {
                  percent: Math.round(check.confidence * 100),
                })}
          </span>
        </span>
        <ChevronDown
          size={18}
          className={`mt-1 flex-none text-[var(--muted)] transition-transform ${
            expanded ? "rotate-180" : ""
          }`}
          aria-hidden="true"
        />
      </button>
      {expanded ? (
        <div id={detailId} className="check-expanded">
          <p className="check-explanation">{explanation}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <span className="chip">
              {t("result.checks.confidence", {
                percent: Math.round(check.confidence * 100),
              })}
            </span>
            {check.weight > 0 ? (
              <span className="chip">
                {t("result.checks.points", {
                  points: formatScore(check.risk_points),
                  weight: formatScore(check.weight),
                })}
              </span>
            ) : null}
          </div>
          {why ? (
            <div className="mt-3 rounded-xl bg-[var(--surface-soft)] p-3">
              <p className="text-xs font-bold uppercase tracking-wide text-[var(--muted)]">
                {t("result.checks.why")}
              </p>
              <p className="muted mt-1 text-sm leading-relaxed">{why}</p>
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
