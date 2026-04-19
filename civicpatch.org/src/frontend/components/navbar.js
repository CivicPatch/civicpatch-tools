import { component } from 'haunted';
import { html } from 'lit';
import { config } from '../assets/config.js';
import { useSummary } from '../hooks/useSummary.js';
import { useLocalStorage, PERSIST_FOREVER } from '../hooks/use-local-storage.js';
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
      gap: 1.25rem;
      padding: 0.875rem 0;
      background: transparent;
      border-bottom: 1px solid var(--pico-muted-border-color);
      user-select: none;
      max-width: 1200px;
      margin-inline: auto;
    }

    .nav-logout {
      font-size: var(--text-sm);
      font-weight: 400;
      color: var(--pico-muted-color);
      text-decoration: none;
      opacity: 0.7;
      transition: opacity 0.15s ease;
      white-space: nowrap;
    }
    .nav-logout:hover {
      opacity: 1;
      color: var(--pico-muted-color);
      text-decoration: none;
    }
    nav.nav--logged-out {
      border-bottom: none;
      position: relative;
      padding-top: 2.5rem;
      padding-bottom: 2.5rem;
    }
    nav.nav--logged-out .nav-brand {
      font-size: 2.25rem;
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
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
      margin-left: auto;
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
      opacity: 0.45;
      transition: opacity 0.15s ease;
    }
    .nav-link:hover {
      opacity: 0.7;
      color: var(--pico-primary);
      text-decoration: none;
    }
    .nav-link--active {
      opacity: 1;
    }

    /* Active state indicator */
    .nav-state-badge {
      font-size: 0.7rem;
      font-family: var(--pico-font-family-monospace);
      font-weight: 700;
      color: var(--pico-muted-color);
      border: 1px solid var(--pico-muted-border-color);
      border-radius: 4px;
      padding: 0.15em 0.4em;
      margin-right: 0.25rem;
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
    .btn-primary:focus-visible,
    .btn-outline:focus-visible {
      outline: none;
      box-shadow: 0 0 0 var(--pico-outline-width) var(--pico-primary-focus);
    }

    /* Login link when logged out */
    .login-link {
      font-size: 0.85rem;
      color: var(--pico-muted-color);
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      transition: color 0.15s ease;
    }
    .login-link:hover {
      color: var(--pico-color);
      text-decoration: none;
    }

    @media (max-width: 640px) {
      .user-info { display: none; }
      nav {
        flex-wrap: wrap;
        gap: 0.75rem;
        padding-top: 1rem;
        padding-bottom: 1rem;
        padding-inline: 0.5rem;
      }
      nav.nav--logged-out {
        flex-direction: column;
        align-items: center;
        padding-top: 1.5rem;
        padding-bottom: 1.5rem;
      }
      nav.nav--logged-out .nav-brand {
        position: static;
        transform: none;
      }
      .nav-links {
        width: 100%;
        margin-left: 0;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 0.5rem;
      }
    }
  </style>
`;

function getTeamsTooltip(teams) {
  if (!teams || teams.length === 0) return 'No teams assigned';
  return `Teams: ${teams.map((t) => t.name || t).join(', ')}`;
}

function renderAuthed(user, summary, currentPath, stateCode) {
  const teams = user.teams || [];
  const tooltip = getTeamsTooltip(teams);
  const active = (href) => {
    const isActive = href === '/' ? currentPath === '/' : currentPath.startsWith(href);
    return isActive ? 'nav-link nav-link--active' : 'nav-link';
  };
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
    ${stateCode ? html`<span class="nav-state-badge">${stateCode.toUpperCase()}</span>` : ""}
    <a href="/" class="${active('/')}">Home</a>
    <a href="/queue" class="${active('/queue')}">Queue <span class="nav-count ${summary == null ? 'nav-count--hidden' : ''}">${summary?.open_prs ?? 0}</span></a>
    ${user.permissions?.can_view_issues_page ? html`<a href="/issues" class="${active('/issues')}">Issues <span class="nav-count ${summary == null ? 'nav-count--hidden' : ''}">${summary?.issues_total ?? 0}</span></a>` : ""}
    ${(user.permissions?.can_view_queue_page) ? html`<a href="/review" class="${active('/review')}">Review</a>` : ""}
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
  const canViewQueue = isAuthed && userData.permissions?.can_view_queue_page;
  const [stateCode] = useLocalStorage("app:default-state", "", { ttl: PERSIST_FOREVER });
  const summary = useSummary(canViewQueue, stateCode);
  const currentPath = window.location.pathname;
  return html`
    ${NAVBAR_CSS}
    <nav class="${!isAuthed ? 'nav--logged-out' : ''}">
      <a href="/" class="nav-brand">
        <span class="nav-brand-icon">
          <i class="fa-solid fa-landmark"></i>
        </span>
        CivicPatch
      </a>
      ${isAuthed ? html`<a href="${API_URL}/api/v1/auth/logout?redirect=${encodeURIComponent(window.location.href)}" class="nav-logout"><i class="fab fa-github"></i> Logout</a>` : ''}
      <div class="nav-links">
        ${isAuthed
          ? renderAuthed(userData, summary, currentPath, stateCode)
          : html`<a class="login-link" href="${API_URL}/api/v1/auth/github/login?redirect=${encodeURIComponent(window.location.href)}"><i class="fab fa-github"></i> Log in</a>`}
      </div>
    </nav>
  `;
}

customElements.define(
  'civ-navbar',
  component(Navbar, { useShadowDOM: false, observedAttributes: ['user'] })
);