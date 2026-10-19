import type { Language } from "../i18n";

function locale(language: Language): string {
  return language === "ur" ? "ur-PK" : "en-GB";
}

export function formatDateTime(
  value: string | Date,
  language: Language,
): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(locale(language), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatDate(value: string | Date, language: Language): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat(locale(language), {
    dateStyle: "medium",
  }).format(date);
}

export function formatFieldDate(
  value: string | null,
  language: Language,
): string | null {
  if (!value) return null;
  const match = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/.exec(value.trim());
  if (!match) return value;
  const [, year, month] = match;
  const date = new Date(Date.UTC(Number(year), Number(month) - 1, 1));
  return new Intl.DateTimeFormat(locale(language), {
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

export function percent(value: number): number {
  return Math.round(value * 100);
}

export function formatPercent(value: number): number {
  return Math.round(Math.max(0, Math.min(1, value)) * 100);
}

export function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
