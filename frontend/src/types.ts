export type Verdict = "consistent" | "suspicious" | "undetermined";
export type CheckStatus = "pass" | "warn" | "fail" | "unknown";
export type Confidence = "low" | "medium" | "high";
export type QualityStatus = "ok" | "warn" | "fail";
export type ViewName = "front" | "back" | "batch" | "blister";
export type PhotoMap = Partial<Record<ViewName, string>>;

export interface CheckResult {
  id: string;
  status: CheckStatus;
  title_key: string;
  explanation_key: string;
  explanation_en: string;
  params: Record<string, unknown>;
  why_key: string;
  confidence: number;
  weight: number;
  risk_points: number;
  metrics: Record<string, unknown>;
}

export interface ExtractedFields {
  product_name: string | null;
  strength: string | null;
  manufacturer: string | null;
  registration_number: string | null;
  batch_number: string | null;
  manufacturing_date: string | null;
  expiry_date: string | null;
  barcode: string | null;
}

export type FieldName = keyof ExtractedFields;

export interface QualityIssue {
  code: string;
  severity: "warn" | "fail";
  message_key: string;
  params: Record<string, unknown>;
}

export interface ImageQuality {
  view: string;
  width: number;
  height: number;
  status: QualityStatus;
  blur_score: number;
  brightness: number;
  glare_ratio: number;
  contrast: number;
  issues: QualityIssue[];
}

export interface ReferenceSummary {
  id: string;
  name: string;
  strength: string | null;
  manufacturer: string | null;
  registration_number: string | null;
  barcode: string | null;
  barcode_prefix: string | null;
  batch_regex: string | null;
  color_hex: string | null;
  demo: boolean;
}

export interface ReferenceMatch {
  matched_by: "explicit" | "barcode" | "name" | "none";
  score: number;
  label_key: string;
  detail: string | null;
}

export interface ComparisonRegion {
  label_key: string;
  label_en: string;
  bbox: number[];
  severity: "warn" | "fail";
  difference: number;
}

export interface ViewComparison {
  view: string;
  ssim: number;
  orb_inliers: number;
  color_distance: number;
  phash_distance: number;
  sharpness_ratio: number;
  combined_similarity: number;
  alignment: "homography" | "resize";
  regions: ComparisonRegion[];
  images: Record<string, string>;
}

export interface RegistrySummary {
  provider: string;
  is_demo: boolean;
  available: boolean;
  notice_key: string;
}

export interface Notice {
  key: string;
  text_en: string;
  params: Record<string, unknown>;
  tone: "info" | "warn" | "danger";
}

export interface AnalysisResult {
  analysis_id: string;
  created_at: string;
  verdict: Verdict;
  risk_score: number;
  confidence: Confidence;
  confidence_reason_key: string;
  confidence_reason_en: string;
  reference: ReferenceSummary | null;
  reference_match: ReferenceMatch | null;
  fields: ExtractedFields;
  checks: CheckResult[];
  quality: Record<string, ImageQuality>;
  quality_status: QualityStatus;
  comparisons: Record<string, ViewComparison>;
  registry: RegistrySummary;
  notices: Notice[];
  ocr_engine: string;
  ocr_confidence: number;
  processing_ms: number;
  scoring_version: string;
  overrides_applied: string[];
}

export interface ReferencePublic {
  id: string;
  name: string;
  aliases: string[];
  strength: string | null;
  manufacturer: string | null;
  registration_number: string | null;
  batch_regex: string | null;
  registration_regex: string | null;
  barcode: string | null;
  barcode_prefix: string | null;
  color_hex: string | null;
  demo: boolean;
  images: Record<string, string>;
}

export interface HealthResponse {
  status: string;
  version: string;
  ocr_engine: string;
  registry_provider: string;
  reference_count: number;
  demo_data: boolean;
}

export interface LocalQuality {
  status: QualityStatus;
  width: number;
  height: number;
  brightness: number;
  blur_score: number;
  glare_ratio: number;
  contrast: number;
  issues: { code: string; severity: "warn" | "fail" }[];
}

export interface ScanRecord {
  id: string;
  createdAt: string;
  result: AnalysisResult;
  photos: PhotoMap;
  language: string;
}
