import "./contribution-card.css";
import { html } from "lit-html";
import "../streak-graph/streak-graph.js";
import "../stat-cards/index.js";
import { formatDuration } from "../../utils/duration-utils.js";

export interface ContributionCardProps {
  isLoggedIn?: boolean;
  dailyCounts?: { date: string; count: number }[];
  streak?: number;
  currentDate?: string | null;
  allTimeResolved?: number;
  avgSecondsPerReview?: number | null;
}

function renderLoggedIn({
  dailyCounts = [],
  streak = 0,
  currentDate = null,
  allTimeResolved = 0,
  avgSecondsPerReview = null,
}: ContributionCardProps) {
  return html`
    <p class="contribution-card__label">YOUR CONTRIBUTIONS</p>
    <civ-streak-graph
      .dailyCounts=${dailyCounts}
      .streak=${streak}
      .currentDate=${currentDate}
    ></civ-streak-graph>
    <stat-cards
      .stats=${[
        {
          key: "all_time",
          label: "All time",
          value: allTimeResolved,
          sub: "reviews",
        },
        {
          key: "avg_time",
          label: "Avg time",
          value: formatDuration(avgSecondsPerReview),
          sub: "per review",
        },
      ]}
    ></stat-cards>
  `;
}

function renderLoggedOut() {
  return html`
    <p class="contribution-card__subheading">Contribute to this data set</p>
    <a class="contribution-card__signin" href="/login"
      >Sign in to review data</a
    >
  `;
}

export function renderContributionCard(props: ContributionCardProps) {
  return html`
    <div class="contribution-card">
      ${props.isLoggedIn ? renderLoggedIn(props) : renderLoggedOut()}
    </div>
  `;
}
