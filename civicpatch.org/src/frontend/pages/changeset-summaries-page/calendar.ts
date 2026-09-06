// The calendar strip: one column per day, banded by what became of that day's runs, with a
// week scale above it and a popover naming the counts.

import { html, nothing } from "lit-html";

export interface CalendarDay {
  state: string;
  day: string;
  published: number;
  to_review: number;
  dismissed: number;
  scrapes: number;
  imports: number;
}

// Keyed `state|YYYY-MM-DD`. Quiet days send no row, so the strip fills its own gaps.
export const dayKey = (state: string, day: string) => `${state}|${day}`;

export const shortDate = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });

export function windowDays(count: number): string[] {
  const today = new Date();
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(today);
    d.setUTCDate(d.getUTCDate() - (count - 1 - i));
    return d.toISOString().slice(0, 10);
  });
}

// A date every 7 columns, so a band can be placed in time without counting cells. Weeks are
// cut from the left; the last one is the 2-day remainder of a 30-day window.
const WEEK = 7;

function weekMarks(days: string[]) {
  const marks = [];
  for (let start = 0; start < days.length; start += WEEK) {
    marks.push({ label: shortDate(days[start]), span: Math.min(WEEK, days.length - start) });
  }
  return marks;
}

// The lead and tail already span exactly the figures either side of the calendar, so they are
// where the group headings belong — no new row, and the headings cannot drift from the columns
// they name.
//
// This resolves a stock-and-flow mix: `to review` is everything outstanding and deliberately
// unwindowed, while everything to the right of the calendar happened inside the window. Without
// the headings the two read as one set of columns measured the same way.
export function renderScale(days: string[]) {
  return html`
    <div class="cs-scale">
      <span class="cs-scale__lead">outstanding</span>
      <span class="cs-scale__track">
        ${weekMarks(days).map(
          (mark) => html`<span class="cs-scale__mark" style="flex: ${mark.span} 1 0"
            >${mark.label}</span
          >`,
        )}
      </span>
      <span class="cs-scale__tail">last 30 days</span>
    </div>
  `;
}

// Bands are proportional to that day's runs, so a day of twelve outcomes is not flattened into
// one hue the way a single colour per day would flatten it.
//
// A button, not a span: the popover opens on focus as well as hover, so the strip is readable
// without a mouse.
const BANDS = [
  { key: "dismissed", label: "dismissed" },
  { key: "review", label: "to review" },
  { key: "published", label: "published" },
] as const;

const countOf = (day: CalendarDay, key: string) =>
  key === "published" ? day.published : key === "review" ? day.to_review : day.dismissed;

// What ran, not just how it ended. Imports are most of what runs, so a day reading "12 published"
// without saying no scraper produced them would mislead.
//
// Only collection attempts appear here at all — a hand edit has no run, so it has no outcome
// to band and is counted nowhere on this page except `roster edits`.
const KINDS = [
  { key: "scrapes", label: "scrape" },
  { key: "imports", label: "import" },
] as const;

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

function renderPopover(day: CalendarDay | undefined, date: string, state: string) {
  const total = day ? day.published + day.to_review + day.dismissed : 0;
  return html`
    <span class="cs-pop">
      <span class="cs-pop__head">${state.toUpperCase()} — ${shortDate(date)}</span>
      ${!day || !total
        ? html`<span class="cs-pop__quiet">Nothing ran</span>`
        : BANDS.filter((band) => countOf(day, band.key)).map(
            (band) => html`
              <span class="cs-pop__line">
                <span class="cs-pop__swatch cs-cal__seg--${band.key}"></span>
                <span class="cs-pop__n">${countOf(day, band.key)}</span> ${band.label}
              </span>
            `,
          )}
      ${day && total
        ? html`<span class="cs-pop__kinds">
            ${KINDS.filter((kind) => day[kind.key]).map(
              (kind) => html`<span class="cs-pop__line cs-pop__quiet"
                >${plural(day[kind.key], kind.label)}</span
              >`,
            )}
          </span>`
        : nothing}
    </span>
  `;
}

export function renderDay(day: CalendarDay | undefined, date: string, state: string) {
  const seg = (count: number, kind: string) =>
    count
      ? html`<span
          class="cs-cal__seg--${kind}"
          style="flex: ${count} 1 0; min-height: 2px"
        ></span>`
      : nothing;
  return html`
    <button class="cs-cal__cell ${day ? "" : "cs-cal__cell--idle"}">
      ${day ? html`${seg(day.dismissed, "dismissed")} ${seg(day.to_review, "review")} ${seg(day.published, "published")}` : nothing}
      ${renderPopover(day, date, state)}
    </button>
  `;
}

