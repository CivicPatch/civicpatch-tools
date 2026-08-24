// Overview's pure logic — no lit, no haunted, no DOM.
//
// Split out so it is unit-testable with zero mocks, and because each of these
// encodes a decision from the spec rather than a rendering detail.

import { buildSourceUrlMap } from "../../utils/source-color-utils.js";
import { PersonStatus, type PersonCard } from "../people/person-cards.js";
import { isContextField, type SurvivingField } from "../fields/field-model.js";

// Who they are in the government, then how to reach them, then the rest. Schema
// order buries both behind Photo and Name.
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

// Six fields fit two rows at every width; the rest collapse to a count.
export const FIELD_CAP = 6;

// Word, not colour alone — nothing else names the status now that the list is one
// roster, and `removed` / `deleted` share a hue. "Removed" echoes the editor's own
// Remove button, so the reviewer sees back the verb they pressed.
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

// Attention is its own axis: an error blocks publishing whichever field it sits on,
// and outranks an issue. Derived, never stored.
export function attentionOf(card: PersonCard): "error" | "issue" | null {
  if (card.surviving.some((field) => field.error)) return "error";
  if (card.surviving.some((field) => field.reason === "issue")) return "issue";
  return null;
}

// The list the card actually shows: context fields render as numbered links, and
// the rest are ranked. Opening the card must focus the field a reviewer sees
// first, so both come from here.
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

// One map for the whole review card, so a url keeps its number and colour on every
// person who cites it.
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

// Consecutive untouched people share one strip, which is what keeps seat order: the
// strip sits exactly where those seats fall between the cards.
export function runsOf(cards: PersonCard[]): Run[] {
  return cards.reduce<Run[]>((runs, card) => {
    const folded = card.status === PersonStatus.UNCHANGED;
    const last = runs[runs.length - 1];
    if (folded && last?.folded) last.cards.push(card);
    else runs.push({ folded, cards: [card] });
    return runs;
  }, []);
}
