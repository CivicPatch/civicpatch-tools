import './contribution-card.css';
import { html } from 'lit-html';
import '../streak-graph/streak-graph.js';
import '../stat-cards/index.js';
import { formatDuration } from '../../utils/duration-utils.js';

export interface ContributionCardProps {
  isLoggedIn?: boolean;
  state?: string;
  toReviewCount?: number;
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
        { key: 'all_time', label: 'All time', value: allTimeResolved, sub: 'reviews' },
        {
          key: 'avg_time',
          label: 'Avg time',
          value: formatDuration(avgSecondsPerReview),
          sub: 'per review',
        },
      ]}
    ></stat-cards>
  `;
}

function renderLoggedOut({ state = '', toReviewCount = 0 }: ContributionCardProps) {
  return html`
    <p class="contribution-card__subheading">Help keep this data accurate</p>
    ${state && toReviewCount > 0
      ? html`
          <div class="contribution-card__opportunity">
            <span class="contribution-card__opportunity-dot"></span>
            <span>
              <strong>${toReviewCount}</strong>
              ${toReviewCount === 1 ? 'municipality' : 'municipalities'} in
              ${state.toUpperCase()} need review.
            </span>
          </div>
        `
      : ''}
    <a class="contribution-card__signin" href="/login">Sign in to help →</a>
  `;
}

export function renderContributionCard(props: ContributionCardProps) {
  return html`
    <div class="contribution-card">
      ${props.isLoggedIn ? renderLoggedIn(props) : renderLoggedOut(props)}
    </div>
  `;
}
