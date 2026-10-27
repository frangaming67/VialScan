export type Severity = "low" | "medium" | "high" | "unknown";
export type ReviewStatus = "pending" | "confirmed" | "dismissed";
export type DefectType = "longitudinal_crack" | "transverse_crack" | "alligator_crack" | "pothole" | "patch" | "rutting" | "deformation" | "raveling" | "edge_break" | "other";

export interface AnalysisSummary {
  frames_total: number;
  condition_counts: Record<string, number>;
  condition_percentages: Record<string, number>;
  defect_observations: number;
  consolidated_incidents: number;
  category_counts: Record<string, number>;
  severity_counts: Record<string, number>;
}

export interface ConditionPoint {
  frame_id: string;
  elapsed_seconds: number;
  road_condition: "good" | "fair" | "poor" | "not_assessable";
  confidence: number;
  summary: string;
  latitude: number | null;
  longitude: number | null;
  is_synthetic?: boolean;
}

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
  analysis_summary?: AnalysisSummary;
  condition_points?: ConditionPoint[];
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
