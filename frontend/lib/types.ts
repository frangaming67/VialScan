export type Severity = "low" | "medium" | "high" | "unknown";
export type ReviewStatus = "pending" | "confirmed" | "dismissed";
export type DefectType = "pothole" | "crack" | "patch" | "deformation" | "other";

export interface Defect {
  id: string;
  session_id: string;
  defect_type: DefectType;
  severity_estimated: Severity;
  severity_score: number;
  review_status: ReviewStatus;
  description: string;
  first_observed_at: number;
  last_observed_at: number;
  confidence: number;
  latitude: number | null;
  longitude: number | null;
  evidence_url: string | null;
  is_synthetic: boolean;
}

export interface ScanSession {
  id: string;
  name: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  defects: Defect[];
}

export interface DemoResponse {
  synthetic: boolean;
  message: string;
  sessions: ScanSession[];
}

export interface ConfigStatus {
  real_processing_ready: boolean;
  missing_variables: string[];
  frame_interval_seconds: number;
  model: string | null;
}
