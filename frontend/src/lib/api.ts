import type {
  AnalysisResult,
  ExtractedFields,
  HealthResponse,
  PhotoMap,
  ReferencePublic,
} from "../types";

const rawBase = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api";
export const API_BASE = rawBase.replace(/\/+$/, "");

export class ApiError extends Error {
  status: number | null;
  kind: "network" | "server" | "validation";
  detail: string | null;

  constructor(
    message: string,
    options: {
      status?: number | null;
      kind?: "network" | "server" | "validation";
      detail?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = options.status ?? null;
    this.kind = options.kind ?? "server";
    this.detail = options.detail ?? null;
  }
}

export function apiAssetUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("/api/") && API_BASE !== "/api") {
    const origin = API_BASE.endsWith("/api")
      ? API_BASE.slice(0, -4)
      : API_BASE;
    return `${origin}${path}`;
  }
  return path;
}

function dataUrlToBlob(dataUrl: string): Blob {
  const [header, encoded] = dataUrl.split(",");
  if (!header || encoded === undefined) {
    throw new ApiError("Invalid image data");
  }
  const mime = /data:([^;]+)/.exec(header)?.[1] ?? "image/jpeg";
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new Blob([bytes], { type: mime });
}

async function readError(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (body.detail) return JSON.stringify(body.detail);
  } catch {
    // Fall back to status text.
  }
  return response.statusText || null;
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw error;
    }
    throw new ApiError("Network request failed", { kind: "network" });
  }
  if (!response.ok) {
    const detail = await readError(response);
    throw new ApiError(detail || `Request failed (${response.status})`, {
      status: response.status,
      detail,
      kind: response.status >= 500 ? "server" : "validation",
    });
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const MANDATORY_VIEWS = ["front", "back", "batch"] as const;

export interface AnalyzeOptions {
  overrides?: Partial<ExtractedFields> | null;
  referenceId?: string | null;
  signal?: AbortSignal;
}

export async function analyzePack(
  photos: PhotoMap,
  options: AnalyzeOptions = {},
): Promise<AnalysisResult> {
  const form = new FormData();
  for (const view of MANDATORY_VIEWS) {
    const value = photos[view];
    if (!value) {
      throw new ApiError("Missing required photo", {
        kind: "validation",
        detail: view,
      });
    }
    form.append(view, dataUrlToBlob(value), `${view}.jpg`);
  }
  if (photos.blister) {
    form.append("blister", dataUrlToBlob(photos.blister), "blister.jpg");
  }
  if (options.overrides) {
    form.append("overrides", JSON.stringify(options.overrides));
  }
  if (options.referenceId) {
    form.append("reference_id", options.referenceId);
  }
  return requestJson<AnalysisResult>("/analyze", {
    method: "POST",
    body: form,
    signal: options.signal,
  });
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health");
}

export function listReferences(): Promise<ReferencePublic[]> {
  return requestJson<ReferencePublic[]>("/references");
}

export function deleteReference(id: string): Promise<void> {
  return requestJson<void>(`/references/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export interface NewReferenceInput {
  name: string;
  manufacturer: string;
  regNo: string;
  strength?: string;
  barcode?: string;
  barcodePrefix?: string;
  batchRegex?: string;
  regRegex?: string;
  colorHex?: string;
  front?: File | null;
  back?: File | null;
  batch?: File | null;
}

export async function addReference(
  input: NewReferenceInput,
): Promise<ReferencePublic> {
  const form = new FormData();
  form.append("name", input.name);
  form.append("manufacturer", input.manufacturer);
  form.append("reg_no", input.regNo);
  const optional: [string, string | undefined][] = [
    ["strength", input.strength],
    ["barcode", input.barcode],
    ["barcode_prefix", input.barcodePrefix],
    ["batch_regex", input.batchRegex],
    ["reg_regex", input.regRegex],
    ["color_hex", input.colorHex],
  ];
  for (const [key, value] of optional) {
    if (value) form.append(key, value);
  }
  if (input.front) form.append("front", input.front, input.front.name);
  if (input.back) form.append("back", input.back, input.back.name);
  if (input.batch) form.append("batch", input.batch, input.batch.name);
  return requestJson<ReferencePublic>("/references", {
    method: "POST",
    body: form,
  });
}
