import { DEMO_PHOTOS, type DemoCaseId } from "./demo";
import type { LocalQuality, PhotoMap } from "../types";

export const QUALITY_ISSUE_KEYS: Record<string, string> = {
  too_small: "quality.localIssues.too_small",
  too_blurry: "quality.localIssues.too_blurry",
  slightly_blurry: "quality.localIssues.slightly_blurry",
  too_dark: "quality.localIssues.too_dark",
  dark: "quality.localIssues.dark",
  overexposed: "quality.localIssues.overexposed",
  bright: "quality.localIssues.bright",
  glare: "quality.localIssues.glare",
  glare_risk: "quality.localIssues.glare_risk",
  low_contrast: "quality.localIssues.low_contrast",
  flat_contrast: "quality.localIssues.flat_contrast",
};

export function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Image could not be loaded"));
    image.src = src;
  });
}

export function blobToDataUrl(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Image could not be read"));
    reader.readAsDataURL(blob);
  });
}

export async function compressImageSource(
  source: Blob | string,
  options: { maxSide?: number; quality?: number } = {},
): Promise<string> {
  const { maxSide = 1800, quality = 0.9 } = options;
  const objectUrl = typeof source === "string" ? null : URL.createObjectURL(source);
  const src = typeof source === "string" ? source : (objectUrl as string);
  try {
    const image = await loadImageElement(src);
    const ratio = Math.min(1, maxSide / Math.max(image.naturalWidth, image.naturalHeight));
    const width = Math.max(1, Math.round(image.naturalWidth * ratio));
    const height = Math.max(1, Math.round(image.naturalHeight * ratio));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) throw new Error("Canvas is unavailable");
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);
    return canvas.toDataURL("image/jpeg", quality);
  } finally {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
  }
}

export function compressForStorage(dataUrl: string): Promise<string> {
  return compressImageSource(dataUrl, { maxSide: 1100, quality: 0.78 });
}

export function captureVideoFrame(video: HTMLVideoElement): string | null {
  if (!video.videoWidth || !video.videoHeight) return null;
  const maxSide = 1800;
  const ratio = Math.min(
    1,
    maxSide / Math.max(video.videoWidth, video.videoHeight),
  );
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(video.videoWidth * ratio);
  canvas.height = Math.round(video.videoHeight * ratio);
  const context = canvas.getContext("2d");
  if (!context) return null;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.9);
}

function standardDeviation(values: Float32Array, mean: number): number {
  let total = 0;
  for (let index = 0; index < values.length; index += 1) {
    const diff = values[index] - mean;
    total += diff * diff;
  }
  return Math.sqrt(total / values.length);
}

export async function assessLocalQuality(dataUrl: string): Promise<LocalQuality> {
  const image = await loadImageElement(dataUrl);
  const originalWidth = image.naturalWidth;
  const originalHeight = image.naturalHeight;
  const scale = Math.min(1, 1000 / Math.max(originalWidth, originalHeight));
  const width = Math.max(1, Math.round(originalWidth * scale));
  const height = Math.max(1, Math.round(originalHeight * scale));
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) {
    return {
      status: "warn",
      width: originalWidth,
      height: originalHeight,
      brightness: 128,
      blur_score: 100,
      glare_ratio: 0,
      contrast: 30,
      issues: [],
    };
  }
  context.drawImage(image, 0, 0, width, height);
  const pixels = context.getImageData(0, 0, width, height).data;
  const gray = new Float32Array(width * height);
  let brightPixels = 0;
  let total = 0;
  for (let index = 0; index < gray.length; index += 1) {
    const offset = index * 4;
    const value =
      pixels[offset] * 0.299 +
      pixels[offset + 1] * 0.587 +
      pixels[offset + 2] * 0.114;
    gray[index] = value;
    total += value;
    if (value >= 251) brightPixels += 1;
  }
  const mean = total / gray.length;
  const contrast = standardDeviation(gray, mean);
  const glareRatio = brightPixels / gray.length;

  let lapTotal = 0;
  let lapSquares = 0;
  let lapCount = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const index = y * width + x;
      const lap =
        gray[index - 1] +
        gray[index + 1] +
        gray[index - width] +
        gray[index + width] -
        4 * gray[index];
      lapTotal += lap;
      lapSquares += lap * lap;
      lapCount += 1;
    }
  }
  const lapMean = lapCount ? lapTotal / lapCount : 0;
  const blur = lapCount ? lapSquares / lapCount - lapMean * lapMean : 0;

  const issues: LocalQuality["issues"] = [];
  if (Math.min(originalWidth, originalHeight) < 480) {
    issues.push({ code: "too_small", severity: "fail" });
  }
  if (blur < 15) issues.push({ code: "too_blurry", severity: "fail" });
  else if (blur < 100)
    issues.push({ code: "slightly_blurry", severity: "warn" });
  if (mean < 35) issues.push({ code: "too_dark", severity: "fail" });
  else if (mean < 60) issues.push({ code: "dark", severity: "warn" });
  if (mean > 250) issues.push({ code: "overexposed", severity: "fail" });
  else if (mean > 232) issues.push({ code: "bright", severity: "warn" });
  if (glareRatio > 0.97) issues.push({ code: "glare", severity: "fail" });
  else if (glareRatio > 0.85)
    issues.push({ code: "glare_risk", severity: "warn" });
  if (contrast < 12)
    issues.push({ code: "low_contrast", severity: "fail" });
  else if (contrast < 22)
    issues.push({ code: "flat_contrast", severity: "warn" });

  const status = issues.some((issue) => issue.severity === "fail")
    ? "fail"
    : issues.length
      ? "warn"
      : "ok";

  return {
    status,
    width: originalWidth,
    height: originalHeight,
    brightness: Math.round(mean * 10) / 10,
    blur_score: Math.round(blur * 10) / 10,
    glare_ratio: Math.round(glareRatio * 1000) / 1000,
    contrast: Math.round(contrast * 10) / 10,
    issues,
  };
}

export interface LiveFeedback {
  key: string;
  tone: "good" | "bad";
}

export function sampleVideoFeedback(
  video: HTMLVideoElement,
): LiveFeedback | null {
  if (!video.videoWidth || !video.videoHeight) return null;
  const width = 160;
  const height = Math.max(
    1,
    Math.round((video.videoHeight / video.videoWidth) * width),
  );
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) return null;
  context.drawImage(video, 0, 0, width, height);
  const data = context.getImageData(0, 0, width, height).data;
  let total = 0;
  let bright = 0;
  for (let index = 0; index < width * height; index += 1) {
    const offset = index * 4;
    const value =
      data[offset] * 0.299 +
      data[offset + 1] * 0.587 +
      data[offset + 2] * 0.114;
    total += value;
    if (value >= 250) bright += 1;
  }
  const mean = total / (width * height);
  const glare = bright / (width * height);
  if (mean < 45) return { key: "capture.camera.liveDark", tone: "bad" };
  if (mean > 243 || glare > 0.16) {
    return { key: "capture.camera.liveBright", tone: "bad" };
  }
  return { key: "capture.camera.liveGood", tone: "good" };
}

export async function loadDemoPhotos(id: DemoCaseId): Promise<PhotoMap> {
  const paths = DEMO_PHOTOS[id];
  const photos: PhotoMap = {};
  await Promise.all(
    Object.entries(paths).map(async ([view, path]) => {
      const response = await fetch(`${import.meta.env.BASE_URL}${path.replace(/^\//, "")}`);
      if (!response.ok) throw new Error("Demo image unavailable");
      const blob = await response.blob();
      photos[view as keyof PhotoMap] = await blobToDataUrl(blob);
    }),
  );
  return photos;
}
