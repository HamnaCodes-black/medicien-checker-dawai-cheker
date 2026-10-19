import type { ReactNode } from "react";
import {
  CircleCheck,
  CircleHelp,
  CircleX,
  TriangleAlert,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import type {
  CheckStatus,
  Confidence,
  Verdict,
} from "../types";

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <span
      className="spinner"
      style={{ width: size, height: size }}
      aria-hidden="true"
    />
  );
}

export function StatusIcon({
  status,
  size = 17,
}: {
  status: CheckStatus;
  size?: number;
}) {
  const common = { size, "aria-hidden": true } as const;
  if (status === "pass") return <CircleCheck {...common} />;
  if (status === "warn") return <TriangleAlert {...common} />;
  if (status === "fail") return <CircleX {...common} />;
  return <CircleHelp {...common} />;
}

export function StatusBadge({
  status,
  label,
}: {
  status: CheckStatus;
  label?: string;
}) {
  const { t } = useTranslation();
  const labels: Record<CheckStatus, string> = {
    pass: t("status.pass"),
    warn: t("status.warn"),
    fail: t("status.fail"),
    unknown: t("status.unknown"),
  };
  return (
    <span className={`badge badge-${status}`}>
      <StatusIcon status={status} size={12} />
      {label ?? labels[status]}
    </span>
  );
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const { t } = useTranslation();
  const labels: Record<Verdict, string> = {
    consistent: t("result.labels.consistent"),
    suspicious: t("result.labels.suspicious"),
    undetermined: t("result.labels.undetermined"),
  };
  const Icon =
    verdict === "consistent"
      ? CircleCheck
      : verdict === "suspicious"
        ? TriangleAlert
        : CircleHelp;
  return (
    <span className="verdict-badge" data-verdict={verdict}>
      <Icon size={16} aria-hidden="true" />
      {labels[verdict]}
    </span>
  );
}

export function ConfidenceMeter({
  level,
  showLabel = true,
}: {
  level: Confidence;
  showLabel?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="flex items-center gap-2">
      <div
        className="meter"
        data-level={level}
        role="img"
        aria-label={`${t("result.confidence.title")}: ${t(`confidence.${level}.label`)}`}
      >
        <span className="meter-seg" />
        <span className="meter-seg" />
        <span className="meter-seg" />
      </div>
      {showLabel ? (
        <span className="text-sm font-semibold">
          {t(`confidence.${level}.label`)}
        </span>
      ) : null}
    </div>
  );
}

export function Skeleton({
  width,
  height,
  radius,
  className,
}: {
  width?: string | number;
  height?: string | number;
  radius?: string | number;
  className?: string;
}) {
  return (
    <span
      className={`skeleton${className ? ` ${className}` : ""}`}
      style={{
        display: "block",
        width,
        height,
        borderRadius: radius,
      }}
      aria-hidden="true"
    />
  );
}

export function HistorySkeleton() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div key={index} className="surface flex gap-3 p-3">
          <Skeleton width={72} height={88} radius={12} />
          <div className="flex-1 space-y-2 py-1">
            <Skeleton width="65%" height={16} />
            <Skeleton width="45%" height={13} />
            <Skeleton width="80%" height={13} />
            <Skeleton width={92} height={22} radius={999} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function ReferenceSkeleton() {
  return (
    <div className="grid gap-3" aria-hidden="true">
      {[0, 1, 2].map((index) => (
        <div key={index} className="surface flex items-center gap-3 p-3">
          <Skeleton width={56} height={72} radius={10} />
          <div className="flex-1 space-y-2">
            <Skeleton width="55%" height={15} />
            <Skeleton width="75%" height={12} />
            <Skeleton width="40%" height={12} />
          </div>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  body,
  action,
}: {
  icon: ReactNode;
  title: string;
  body: string;
  action?: ReactNode;
}) {
  return (
    <div className="surface surface-pad py-10 text-center">
      <div className="empty-visual">{icon}</div>
      <h2 className="display-section font-display mt-4">{title}</h2>
      <p className="muted mx-auto mt-2 max-w-sm text-sm leading-relaxed">
        {body}
      </p>
      {action ? <div className="mt-5 flex justify-center">{action}</div> : null}
    </div>
  );
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  id,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  description?: string;
  id: string;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <label htmlFor={id} className="label mb-0">
          {label}
        </label>
        {description ? <p className="hint mt-1">{description}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        className="toggle-switch"
        onClick={() => onChange(!checked)}
      >
        <span className="toggle-knob" />
      </button>
    </div>
  );
}

export function DemoBadge() {
  const { t } = useTranslation();
  return <span className="badge badge-demo">{t("app.demoData")}</span>;
}
