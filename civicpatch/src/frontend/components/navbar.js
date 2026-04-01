import { component } from 'haunted';
import { html } from 'lit';
import { config } from '../assets/config.js';
import { useSummary } from '../hooks/useSummary.js';
const API_URL = config.apiUrl;

const NAVBAR_CSS = html`
  <style>
    civ-navbar {
      display: block;
      z-index: 100;
    }

    nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.875rem 0;
      background: transparent;
      border-bottom: 1px solid var(--pico-muted-border-color);
      user-select: none;
      max-width: 1200px;
      margin-inline: auto;
    }

    /* Brand */
    .nav-brand {
      font-weight: 700;
      font-size: 1.125rem;
      text-decoration: none;
      color: var(--pico-color);
      display: flex;
      align-items: center;
      gap: 0.5rem;
      letter-spacing: -0.01em;
      transition: opacity 0.15s ease;
    }
    .nav-brand:hover {
      opacity: 0.7;
      color: var(--pico-color);
      text-decoration: none;
    }
    .nav-brand-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 1.75rem;
      height: 1.75rem;
      background: var(--pico-primary);
      border-radius: 0.375rem;
      color: var(--pico-primary-inverse);
      font-size: 0.8rem;
      flex-shrink: 0;
    }

    /* Right side */
    .nav-links {
      display: flex;
      align-items: center;
      gap: 1.25rem;
    }

    /* User identity — avatar + display name */
    .user-info {
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      font-size: 0.9rem;
      font-weight: 400;
      color: var(--pico-color);
      cursor: default;
      max-width: 220px;
      text-decoration: none;
    }
    .user-avatar {
      width: 1.5rem;
      height: 1.5rem;
      border-radius: 50%;
      flex-shrink: 0;
      display: block;
    }
    .user-dot {
      width: 0.5rem;
      height: 0.5rem;
      border-radius: 50%;
      background: var(--pico-primary);
      flex-shrink: 0;
    }
    .user-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    /* Jobs — scoped colored link, no underline */
    .nav-link {
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--pico-primary);
      text-decoration: none;
      transition: opacity 0.15s ease;
    }
    .nav-link:hover {
      opacity: 0.75;
      color: var(--pico-primary);
      text-decoration: none;
    }

    /* Count badge on nav links */
    .nav-count--hidden {
      visibility: hidden;
    }
    .nav-count {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 1.5em;
      padding: 0.15em 0.45em;
      height: 1.5em;
      border-radius: 999px;
      font-size: 0.7rem;
      font-family: var(--pico-font-family-monospace);
      font-weight: 700;
      background: var(--pico-primary);
      color: var(--pico-primary-inverse);
      line-height: 1;
      vertical-align: middle;
      margin-left: 0.2em;
    }

    /* Logout — outline button, no fill */
    .btn-outline {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--pico-color);
      background: transparent;
      border: 1.5px solid var(--pico-muted-border-color);
      border-radius: var(--pico-border-radius);
      padding: 0.4rem 1.1rem;
      cursor: pointer;
      text-decoration: none;
      transition: border-color 0.15s ease, background 0.15s ease;
      white-space: nowrap;
    }
    .btn-outline:hover {
      border-color: var(--pico-color);
      background: transparent;
      color: var(--pico-color);
      text-decoration: none;
    }
    .btn-outline:active {
      background: var(--pico-muted-background);
    }

    /* Login — filled primary button */
    .btn-primary {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--pico-primary-inverse);
      background: var(--pico-primary);
      border: none;
      border-radius: 0.5rem;
      padding: 0.4rem 1.1rem;
      cursor: pointer;
      text-decoration: none;
      transition: opacity 0.15s ease;
      white-space: nowrap;
    }
    .btn-primary:hover {
      opacity: 0.85;
      color: var(--pico-primary-inverse);
      text-decoration: none;
    }
    .btn-primary:active {
      opacity: 0.95;
    }

    /* Loading skeleton */
    .loading-skeleton {
      display: inline-block;
      width: 7em;
      height: 0.75em;
      background: linear-gradient(
        90deg,
        var(--pico-muted-background) 25%,
        color-mix(in srgb, var(--pico-muted-background) 60%, transparent) 50%,
        var(--pico-muted-background) 75%
      );
      background-size: 200% 100%;
      border-radius: 0.4em;
      vertical-align: middle;
      animation: skeleton-shimmer 1.4s infinite ease-in-out;
    }
    @keyframes skeleton-shimmer {
      0%   { background-position: 200% 0; }
      100% { background-position: -200% 0; }
    }

    /* Rounded focus outlines */
    .nav-brand:focus-visible,
    .nav-link:focus-visible,
    .btn-primary:focus-visible {
      outline: var(--pico-outline-width) solid var(--pico-primary-focus);
      outline-offset: 0.2rem;
      border-radius: var(--pico-border-radius);
    }
    .btn-outline:focus-visible {
      outline: none;
      box-shadow: 0 0 0 var(--pico-outline-width) var(--pico-primary-focus);
    }

    @media (max-width: 640px) {
      .user-info { display: none; }
    }
  </style>
`;

function getTeamsTooltip(teams) {
  if (!teams || teams.length === 0) return 'No teams assigned';
  return `Teams: ${teams.map((t) => t.name || t).join(', ')}`;
}

function renderAuthed(user, summary) {
  const teams = user.teams || [];
  const tooltip = getTeamsTooltip(teams);
  return html`
    <span
      class="user-info"
      data-tooltip="${tooltip}"
      data-placement="bottom"
    >
      ${user.avatar_url
        ? html`<img class="user-avatar" src="${user.avatar_url}" alt="" />`
        : html`<span class="user-dot"></span>`}
      <span class="user-name">${user.display_name || user.email || 'User'}</span>
    </span>
    <a href="/" class="nav-link">Home</a>
    <a href="/queue" class="nav-link">Queue <span class="nav-count ${summary?.open_prs == null ? 'nav-count--hidden' : ''}">${summary?.open_prs ?? ''}</span></a>
    ${user.permissions?.can_view_issues_page ? html`<a href="/issues" class="nav-link">Issues <span class="nav-count ${!summary || (!summary.pipeline_errors && !summary.duplicate_jurisdictions) ? 'nav-count--hidden' : ''}">${summary ? (summary.pipeline_errors ?? 0) + (summary.duplicate_jurisdictions ?? 0) : ''}</span></a>` : ""}
    ${(user.permissions?.can_view_jobs_page) ? html`<a href="/review" class="nav-link">Review</a>` : ""}
    <a
      href="${API_URL}/api/v1/auth/logout?redirect=${encodeURIComponent(window.location.href)}"
      class="btn-outline"
    >
      Logout
    </a>
  `;
}

function renderLogin() {
  return html`
    <a
      href="${API_URL}/api/v1/auth/github/login?redirect=${encodeURIComponent(window.location.href)}"
      class="btn-primary"
    >
      <i class="fab fa-github"></i>
      Login with GitHub
    </a>
  `;
}

function Navbar({ user }) {
  let userData = null;
  try {
    userData = user ? JSON.parse(user) : null;
  } catch (e) {
    userData = null;
  }
  const isAuthed = userData?.authenticated;
  const canViewQueue = isAuthed && userData.permissions?.can_view_jobs_page;
  const summary = useSummary(canViewQueue);
  return html`
    ${NAVBAR_CSS}
    <nav>
      <a href="/" class="nav-brand">
        <span class="nav-brand-icon">
          <i class="fas fa-landmark"></i>
        </span>
        CivicPatch
      </a>
      <div class="nav-links">
        ${isAuthed ? renderAuthed(userData, summary) : renderLogin()}
      </div>
    </nav>
  `;
}

customElements.define(
  'civ-navbar',
  component(Navbar, { useShadowDOM: false, observedAttributes: ['user'] })
);