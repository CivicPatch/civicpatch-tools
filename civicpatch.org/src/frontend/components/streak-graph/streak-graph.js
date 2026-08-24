import "./streak-graph.css";
import { html } from "lit-html";
import { component, useState } from "haunted";
import { toLocalDateStr } from "../../utils/date-utils.js";

const WEEKS = 16;
const DOW_LABELS = ["Mon", "", "Wed", "", "Fri", "", "Sun"];
const BARS = "▁▂▃▄▅▆▇█";
const MAX_COUNT = 10;

function getOpacity(count) {
  if (count === 0) return 0;
  return Math.min(0.2 + (count / MAX_COUNT) * 0.8, 1);
}

function buildGrid(dailyCounts, currentDate) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const todayStr = currentDate ?? toLocalDateStr(today);

  const dow = today.getDay();
  const daysFromMonday = dow === 0 ? 6 : dow - 1;
  const currentMonday = new Date(today);
  currentMonday.setDate(today.getDate() - daysFromMonday);

  const startDate = new Date(currentMonday);
  startDate.setDate(currentMonday.getDate() - (WEEKS - 1) * 7);

  const countMap = {};
  for (const { date, count } of (dailyCounts || [])) {
    countMap[date] = count;
  }

  const days = [];
  for (let i = 0; i < WEEKS * 7; i++) {
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);
    const dateStr = toLocalDateStr(d);
    days.push({
      date: dateStr,
      count: countMap[dateStr] || 0,
      isFuture: dateStr > todayStr,
      isToday: dateStr === todayStr,
    });
  }
  return days;
}

function buildMonthLabels(days) {
  return Array.from({ length: WEEKS }, (_, w) => {
    const firstDay = days[w * 7];
    const prevFirstDay = w > 0 ? days[(w - 1) * 7] : null;
    const d = new Date(firstDay.date + "T00:00:00");
    const prevMonth = prevFirstDay ? new Date(prevFirstDay.date + "T00:00:00").getMonth() : -1;
    return d.getMonth() !== prevMonth
      ? d.toLocaleString("default", { month: "short" })
      : "";
  });
}

function buildCopyText(days, streak) {
  const thisWeek = days.filter((d) => !d.isFuture).slice(-7);
  const total = thisWeek.reduce((sum, d) => sum + d.count, 0);
  const max = Math.max(...thisWeek.map((d) => d.count), 1);
  const sparkline = thisWeek.map((d) => {
    if (d.count === 0) return "▁";
    return BARS[Math.round((d.count / max) * (BARS.length - 1))];
  }).join("");
  return `${streak ?? 0} day streak, ${total} review${total === 1 ? "" : "s"} this week — civicpatch.org
${sparkline}`;
}

function StreakGraph({ dailyCounts, streak, currentDate }) {
  const [copied, setCopied] = useState(false);
  const days = buildGrid(dailyCounts, currentDate);
  const monthLabels = buildMonthLabels(days);

  const handleCopy = () => {
    navigator.clipboard.writeText(buildCopyText(days, streak));
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return html`
    <div class="streak-graph" @click=${handleCopy}>
      <div class="streak-graph__header">
        <span class="streak-graph__streak">${streak ?? 0}</span>
        <span class="streak-graph__label">day streak</span>
      </div>
      <div class="streak-graph__body">
        <div class="streak-graph__dow-col">
          ${DOW_LABELS.map((d) => html`<span class="streak-graph__dow">${d}</span>`)}
        </div>
        <div class="streak-graph__right">
          <div class="streak-graph__months">
            ${monthLabels.map((label) => html`<span class="streak-graph__month">${label}</span>`)}
          </div>
          <div class="streak-graph__grid">
            ${days.map(({ date, count, isFuture, isToday }) => html`
              <div
                class="streak-graph__day ${count > 0 ? "streak-graph__day--active" : isFuture ? "streak-graph__day--future" : "streak-graph__day--empty"}${isToday ? " streak-graph__day--today" : ""}"
                style="${count > 0 ? `--day-opacity:${getOpacity(count).toFixed(2)}` : ""}"
                title="${!isFuture ? (count ? `${date}: ${count} review${count === 1 ? "" : "s"}` : date) : ""}"
              ></div>
            `)}
          </div>
        </div>
      </div>
      <i class="streak-graph__copy-icon ${copied ? "streak-graph__copy-icon--copied fa-solid fa-check" : "fa-regular fa-copy"}"></i>
    </div>
  `;
}

customElements.define("civ-streak-graph", component(StreakGraph, { useShadowDOM: false }));
