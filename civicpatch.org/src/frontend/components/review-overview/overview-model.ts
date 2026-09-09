
import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { PersonStatus, type PersonCard } from "../people/person-cards.js";
import { isContextField, type SurvivingField } from "../fields/field-model.js";

const FIELD_ORDER = [
  "labels",
  "emails",
  "phones",
  "urls",
  "name",
  "other_names",
  "start_date",
  "end_date",
  "image",
];

const REASON_RANK: Record<string, number> = {
  error: 0,
  issue: 1,
  diff: 2,
  context: 3,
};

export const FIELD_CAP = 6;

export const STATUS_BADGE: Partial<Record<string, string>> = {
  [PersonStatus.CHANGED]: "Changed",
  [PersonStatus.ADDED]: "New",
  [PersonStatus.REMOVED]: "Not in scrape",
  [PersonStatus.DELETED]: "Removed",
  [PersonStatus.RESTORED]: "Restored",
};

export const ATTENTION_COPY = {
  error: { icon: "triangle-exclamation", label: "Blocks publishing" },
  issue: { icon: "circle-exclamation", label: "Has an issue" },
};

function fieldRank(key: string): number {
  const i = FIELD_ORDER.indexOf(key);
  return i === -1 ? FIELD_ORDER.length : i;
}

export function byRank(a: SurvivingField, b: SurvivingField): number {
  const reason = (REASON_RANK[a.reason] ?? 9) - (REASON_RANK[b.reason] ?? 9);
  return reason || fieldRank(a.field.key) - fieldRank(b.field.key);
}

export function attentionOf(card: PersonCard): "error" | "issue" | null {
  if (card.surviving.some((field) => field.error)) return "error";
  if (card.surviving.some((field) => field.reason === "issue")) return "issue";
  return null;
}

export interface TallyEntry {
  status: string;
  label: string;
  count: number;
}

const TALLY_LABEL: Record<string, string> = {
  [PersonStatus.ADDED]: "added",
  [PersonStatus.CHANGED]: "changed",
  [PersonStatus.REMOVED]: "not in scrape",
  [PersonStatus.DELETED]: "removed",
  [PersonStatus.RESTORED]: "restored",
  [PersonStatus.UNCHANGED]: "unchanged",
};

const TALLY_ORDER = [
  PersonStatus.ADDED,
  PersonStatus.CHANGED,
  PersonStatus.REMOVED,
  PersonStatus.DELETED,
  PersonStatus.RESTORED,
  PersonStatus.UNCHANGED,
];

export function tallyOf(cards: PersonCard[]): TallyEntry[] {
  const counts = new Map<string, number>();
  for (const card of cards) {
    counts.set(card.status, (counts.get(card.status) ?? 0) + 1);
  }
  return TALLY_ORDER.filter((status) => counts.get(status)).map((status) => ({
    status,
    label: TALLY_LABEL[status],
    count: counts.get(status) as number,
  }));
}

export function visibleFields(card: PersonCard): SurvivingField[] {
  return card.surviving
    .filter((field) => !isContextField(field.field))
    .sort(byRank);
}

export function fieldClass(field: SurvivingField): string {
  if (field.error) return "error";
  return field.reason === "issue" ? "issue" : field.state;
}

export type SourceMap = Map<string, { number: number; colorClass: string }>;

export function sourceMapFor(cards: PersonCard[]): SourceMap {
  const seen: { url: string }[] = [];
  const known = new Set<string>();
  for (const card of cards) {
    for (const url of card.newRecord?.source_urls ?? []) {
      if (url && !known.has(url)) {
        known.add(url);
        seen.push({ url });
      }
    }
  }
  return buildSourceUrlMap(seen);
}

export interface Run {
  folded: boolean;
  cards: PersonCard[];
}

export function runsOf(cards: PersonCard[]): Run[] {
  return cards.reduce<Run[]>((runs, card) => {
    const folded = card.status === PersonStatus.UNCHANGED;
    const last = runs[runs.length - 1];
    if (folded && last?.folded) last.cards.push(card);
    else runs.push({ folded, cards: [card] });
    return runs;
  }, []);
}
