/** Types of the BustGuard API (backend/app/api/routes). Values always come from the API. */

export type Risk = "Low" | "Medium" | "High";
export type SpreadSays = "confident" | "uncertain" | "no spread";

export interface Region {
  id: string;
  name: string;
  subdivision: string;
  zone: string;
  lat: number;
  lon: number;
}

export interface Headline {
  test_years: number[];
  base_rate: number;
  pr_auc: Record<string, number>;
  pr_auc_ci?: Record<string, [number, number]>;
  recall_at_operating_point: Record<string, number>;
  far_at_operating_point: Record<string, number>;
  n_low_spread_busts: number;
  recall_low_spread_busts: Record<string, number | null>;
  cw_alerts: { n_alerts: number; n_alert_busts: number; precision: number | null; base_rate_low_spread: number | null };
}

export interface Meta {
  schema_version: number;
  source: string;
  is_synthetic: boolean;
  banner: string;
  default_label: string;
  label_definition: Record<string, unknown>;
  variables: string[];
  variables_unavailable: Record<string, string>;
  lead_days: number[];
  init_dates: string[];
  test_init_dates: string[];
  latest_date: string;
  split: { train_years: number[]; calibration_years: number[]; test_years: number[] };
  families: string[];
  family_labels: Record<string, string>;
  families_present: string[];
  risk_thresholds: { medium: number; high: number };
  methods: string[];
  spread_note: string;
  headline: Headline;
}

export interface Reliability {
  observed_bust_rate: number | null;
  n: number;
}

export interface RegionConfidence {
  id: string;
  name: string;
  zone: string;
  lat: number;
  lon: number;
  rank: number;
  fc: number | null;
  obs: number | null;
  bust: number | null;
  bust_prob: number;
  confidence: number;
  risk: Risk;
  reliability: Reliability;
  confidently_wrong: boolean;
  low_spread: boolean;
  spread: number | null;
  spread_says: SpreadSays;
  spread_prob: number | null;
  lr_prob: number | null;
  regime: string;
  likely_driver: string | null;
  valid_date: string;
}

export interface LeadSummary {
  lead_day: number;
  max_risk: Risk;
  n_high: number;
  n_medium: number;
  n_cw: number;
  max_prob: number;
}

export interface ConfidenceMap {
  source: string;
  is_synthetic: boolean;
  date: string;
  lead: number;
  variable: string;
  valid_date: string;
  split: string;
  regions: RegionConfidence[];
  error_prone: string[];
  lead_summary: LeadSummary[];
  summary: {
    mean_bust_prob: number;
    base_rate: number;
    risk_counts: Record<Risk, number>;
    n_confidently_wrong: number;
    verified: boolean;
    busts_observed: number | null;
  };
}

export interface Family {
  family: string;
  label: string;
  pct: number;
  direction: "raises" | "neutral";
}

export interface Reason {
  feature: string;
  text: string;
  contribution: number;
  value: number;
}

export interface PathwayStep {
  family: string;
  text: string;
}

export interface AnalogCase {
  init_date: string;
  valid_date: string;
  region_id: string;
  region: string;
  lead_day: number;
  fc: number | null;
  obs: number | null;
  bust: number | null;
  regime: string;
}

export interface Analogs {
  n_total: number;
  n_bust: number;
  text: string;
  cases: AnalogCase[];
}

export interface LeadDetail {
  lead_day: number;
  init_date: string;
  valid_date: string;
  fc: number | null;
  obs: number | null;
  abs_error: number | null;
  bust: number | null;
  bust_prob: number;
  confidence: number;
  risk: Risk;
  reliability: Reliability;
  confidently_wrong: boolean;
  low_spread: boolean;
  spread: number | null;
  spread_says: SpreadSays;
  spread_prob: number | null;
  lr_prob: number | null;
  regime: string;
  likely_driver: string | null;
  families: Family[];
  family_sentence: string;
  reasons: Reason[];
  pathway: PathwayStep[] | null;
  analogs: Analogs;
}

export interface RiskWindow {
  from_lead: number;
  to_lead: number;
  max_risk: Risk;
}

export interface RegionDetail {
  source: string;
  is_synthetic: boolean;
  region: { id: string; name: string; zone: string; lat: number; lon: number };
  date: string;
  variable: string;
  risk_window: RiskWindow[];
  any_confidently_wrong: boolean;
  leads: LeadDetail[];
}

export interface ScoreBlock {
  n: number;
  n_busts: number;
  base_rate: number;
  pr_auc: number | null;
  roc_auc: number | null;
  brier: number | null;
  brier_skill_vs_climatology: number | null;
  recall_at_far: Record<string, { recall: number; far: number; threshold: number }>;
  operating_point: { threshold: number; recall: number; far: number; precision: number; csi: number; n_flagged: number };
}

export interface ReliabilityBin {
  bin_lo: number;
  bin_hi: number;
  mean_prob: number;
  obs_freq: number;
  count: number;
}

export interface EarlyWarning {
  n_events: number;
  [method: string]: number | { mean_days: number | null; median_days: number | null; share_warned: number | null; share_3plus_days: number | null };
}

export interface Metrics {
  label: string;
  label_definition: Record<string, unknown>;
  split: Meta["split"];
  headline: Headline;
  spread_note: string;
  is_synthetic: boolean;
  methods: Record<string, string>;
  overall: Record<string, ScoreBlock>;
  per_lead: Record<string, Record<string, ScoreBlock>>;
  reliability: Record<string, ReliabilityBin[]>;
  confidently_wrong: {
    n_low_spread: number;
    n_low_spread_busts: number;
    n_busts: number;
    share_of_busts_with_low_spread: number;
    alerts: Headline["cw_alerts"] & { share_low_spread_busts_alerted: number };
    [method: string]: unknown;
  };
  early_warning: EarlyWarning;
  ablation?: { family: string; n_features: number; pr_auc: number; delta: number }[];
  bootstrap?: { pr_auc_ci: Record<string, [number, number]>; diff_vs_first_ci: Record<string, [number, number]> };
  test_period: { from: string; to: string; n: number };
  operating_far: number;
}

export interface ScorecardCell {
  regime: string;
  lead_day: number;
  n: number;
  n_busts: number;
  pr_auc: Record<string, number> | null;
  improvement: number | null;
  base_rate: number | null;
}

export interface Scorecard {
  regimes: string[];
  leads: number[];
  cells: ScorecardCell[];
  min_busts: number;
  methods: Record<string, string>;
}

export interface CostLoss {
  user: string;
  preset: { alpha: number; label: string; action: string; value: Record<string, number | null> };
  users: Record<string, { label: string; alpha: number; action: string }>;
  curves: Record<string, { alpha: number; value: number | null }[]>;
  base_rate: number;
}

export interface BlindspotItem {
  region_id: string;
  region: string;
  init_date: string;
  valid_date: string;
  lead_day: number;
  bust_prob: number;
  risk: Risk;
  confidently_wrong: boolean;
  spread: number | null;
  spread_says: SpreadSays;
  regime: string;
  likely_driver: string | null;
  fc: number | null;
  obs: number | null;
  bust: number | null;
  analogs: Analogs;
}

export interface Blindspots {
  date: string | null;
  n: number;
  n_confidently_wrong: number;
  verified_busts: number;
  verified: number;
  items: BlindspotItem[];
  note: string;
}

export interface ReplayStep {
  lead_day: number;
  init_date: string;
  fc: number | null;
  obs: number | null;
  bust: number | null;
  model_prob: number | null;
  model_risk: Risk;
  model_flag: boolean;
  spread: number | null;
  spread_prob: number | null;
  spread_says: SpreadSays;
  spread_flag: boolean;
  confidently_wrong: boolean;
}

export interface ReplayRegion {
  region_id: string;
  region: string;
  obs: number | null;
  busted_day1: boolean;
  first_warning: { BustGuard: number; spread: number };
  steps: ReplayStep[];
}

export interface ReplayEventSummary {
  id: string;
  title: string;
  window: [string, string];
  split: string;
  region_names: string[];
  peak: { valid_date?: string; region?: string; imd_mm?: number; hres_day1_mm?: number };
  n_days: number;
}

export interface ReplayEvent extends Omit<ReplayEventSummary, "n_days"> {
  regions: string[];
  days: { valid_date: string; regions: ReplayRegion[] }[];
  is_synthetic: boolean;
}

export interface DateEntry {
  date: string;
  split: string;
}
