// Mirrors schemas/roster_comparisons.py.

export const OUTCOME_MATCHED = "matched";
export const OUTCOME_POSSIBLE_MATCH = "possible_match";
export const OUTCOME_ONLY_IN_UPLOADED_DATA = "only_in_uploaded_data";
export const OUTCOME_ONLY_IN_CIVICPATCH = "only_in_civicpatch";

export const OUTCOMES = [
  OUTCOME_MATCHED,
  OUTCOME_POSSIBLE_MATCH,
  OUTCOME_ONLY_IN_UPLOADED_DATA,
  OUTCOME_ONLY_IN_CIVICPATCH,
] as const;
export type Outcome = (typeof OUTCOMES)[number];

export const COMPARED_FIELDS = ["role", "emails", "phones", "urls", "start_date"] as const;
export type ComparedField = (typeof COMPARED_FIELDS)[number];

export const FIELD_FILTER_CONFLICT = "conflict";
export const FIELD_FILTER_ONE_SIDE_HAS_MORE = "one_side_has_more";
export type FieldFilter = typeof FIELD_FILTER_CONFLICT | typeof FIELD_FILTER_ONE_SIDE_HAS_MORE;

export interface UploadedRow {
  source_row: number;
  jurisdiction_ocdid: string;
  name: string;
  role: string | null;
  emails: string[];
  phones: string[];
  urls: string[];
  start_date: string | null;
  not_compared: Record<string, unknown>;
}

export interface Candidate {
  person_id: string;
  name: string;
  reason: string;
  already_matched_by_row: number | null;
}

export interface FieldComparison {
  level: string;
  uploaded: string[];
  civicpatch: string[];
}

export interface RowWarning {
  code: string;
  message: string;
}

export interface PersonComparison {
  outcome: Outcome;
  uploaded: UploadedRow | null;
  person_id: string | null;
  person_name: string | null;
  candidates: Candidate[];
  fields: Partial<Record<ComparedField, FieldComparison>>;
  warnings: RowWarning[];
}

export type OutcomeCounts = Record<Outcome, number>;

export interface FieldCounts {
  agreement: number;
  one_side_has_more: number;
  conflict: number;
  unknown: number;
  uploaded_data_has_it: number;
  civicpatch_has_it: number;
}

export interface ComparisonRates {
  outcomes: OutcomeCounts;
  fields: Partial<Record<ComparedField, FieldCounts>>;
  rows_with_warnings: number;
}

export interface RosterComparisonRun {
  id: string;
  state: string;
  started_by_user_id: string;
  started_at: string;
  source_columns: Record<string, string[]>;
  corrections: string[];
  rates: ComparisonRates;
  jurisdictions_not_named: number;
}

export interface JurisdictionRates {
  jurisdiction_ocdid: string;
  rates: ComparisonRates;
}

export interface RosterComparisonSummary {
  run: RosterComparisonRun;
  page_url: string;
  jurisdictions: JurisdictionRates[];
}

export interface RosterComparisonListItem {
  id: string;
  state: string;
  started_at: string;
  started_by: string;
  jurisdictions_named: number;
  rates: ComparisonRates;
  page_url: string;
}

export interface RosterComparisonListPage {
  total_items: number;
  page: number;
  total_pages: number;
  data: RosterComparisonListItem[];
}

export interface FieldPerson {
  jurisdiction_ocdid: string;
  person: PersonComparison;
}

export interface FieldPage {
  total_items: number;
  page: number;
  total_pages: number;
  data: FieldPerson[];
}
