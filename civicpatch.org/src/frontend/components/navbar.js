import { component } from "haunted";
import { html } from "lit";
import { config } from "../assets/config.js";
import { useSummary } from "../hooks/useSummary.js";
import {
  useLocalStorage,
  PERSIST_FOREVER,
} from "../hooks/use-local-storage.js";
import { STORAGE_KEYS } from "../utils/storage-keys.js";
import {
  STATE_PARAM,
  REVIEW_PATH,
  REVIEW_SESSION_PATH,
  landingUrl,
} from "../pages/review-routes.ts";
import "./search-jurisdictions/select-state.js";
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
      flex-wrap: wrap;
      gap: 0.85rem;
      padding: 0.875rem 0;
      background: transparent;
      border-bottom: 3px solid var(--civ-border-strong, #111);
      user-select: none;
      max-width: var(--page-width);
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
      padding-top: 1.25rem;
      padding-bottom: 1.25rem;
    }
    nav.nav--logged-out .nav-brand {
      font-size: 2.25rem;
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
    }

    /* Brand */
    .nav-brand {
      font-family: "Space Grotesk", sans-serif;
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
    .nav-beta-badge {
      font-size: 0.6rem;
      font-family: var(--pico-font-family-monospace);
      font-weight: 700;
      letter-spacing: 0.05em;
      line-height: 1;
      color: rgb(var(--catppuccin-yellow));
      border: 1px solid rgb(var(--catppuccin-yellow));
      border-radius: 4px;
      padding: 0.2em 0.35em;
      opacity: 0.7;
      position: relative;
      bottom: 0.35em;
    }

    /* Right side */
    .nav-links {
      display: flex;
      align-items: center;
      gap: 0.85rem;
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
      white-space: nowrap;
    }
    .nav-link:hover {
      opacity: 0.7;
      color: var(--pico-primary);
      text-decoration: none;
    }
    .nav-link--active {
      opacity: 1;
    }

    /* Admin disclosure menu — native <details>/<summary> (tap + keyboard, no JS) */
    /* Override Pico's accordion <details>/<summary> defaults that misalign it in the nav:
       its margin-bottom (shifts the item up), its ::after chevron marker, and the
       margin it adds to summary when open (shifts the row). */
    .nav-dropdown {
      position: relative;
      margin: 0;
    }
    summary.nav-dropdown-trigger {
      list-style: none;
      cursor: pointer;
      line-height: inherit;
    }
    summary.nav-dropdown-trigger::-webkit-details-marker {
      display: none;
    }
    summary.nav-dropdown-trigger::after {
      display: none;
    }
    .nav-dropdown[open] > summary {
      margin-bottom: 0;
    }
    .nav-dropdown-caret {
      font-size: 0.6em;
      opacity: 0.6;
      margin-left: 0.3rem;
      transition: transform 0.15s ease;
      display: inline-block;
    }
    .nav-dropdown[open] .nav-dropdown-caret {
      transform: rotate(180deg);
    }
    /* Menu is hidden by the UA when <details> is closed; only style the open state. */
    .nav-dropdown[open] .nav-dropdown__menu {
      position: absolute;
      top: 100%;
      right: 0;
      display: flex;
      flex-direction: column;
      min-width: 9rem;
      padding: 0.35rem 0;
      background: var(--pico-background-color);
      border: 1px solid var(--pico-muted-border-color);
      border-radius: var(--pico-border-radius);
      box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
      z-index: 200;
    }
    .nav-dropdown__menu .nav-link {
      display: block;
      padding: 0.4rem 0.9rem;
      white-space: nowrap;
      opacity: 0.8;
    }
    .nav-dropdown__menu .nav-link:hover {
      opacity: 1;
      color: var(--pico-primary);
      background: color-mix(in srgb, var(--pico-primary) 14%, transparent);
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

    .nav-state-selector select {
      font-size: 0.8rem;
      font-family: var(--pico-font-family-monospace);
      color: var(--pico-muted-color);
      background-color: transparent;
      border: 1px solid var(--pico-muted-border-color);
      border-radius: 4px;
      padding-block: 0.15em;
      padding-inline: 0.45em;
      padding-inline-end: 1.5em;
      margin: 0;
      width: auto;
      height: auto;
      line-height: 1.2;
      background-size: 0.6em;
      background-position: right 0.4em center;
    }

    /* Count badge on nav links */
    .nav-count--hidden {
      visibility: hidden;
    }
    .nav-count--error {
      background: var(--pico-del-color);
      color: #fff;
      font-size: 0.85rem;
      min-width: 1.6em;
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
      transition:
        border-color 0.15s ease,
        background 0.15s ease;
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
      0% {
        background-position: 200% 0;
      }
      100% {
        background-position: -200% 0;
      }
    }

    /* Theme toggle */
    .theme-toggle {
      background: none;
      border: none;
      cursor: pointer;
      color: var(--pico-muted-color);
      font-size: 0.9rem;
      padding: 0.25rem;
      display: inline-flex;
      align-items: center;
      opacity: 0.6;
      transition: opacity 0.15s ease;
    }
    .theme-toggle:hover {
      opacity: 1;
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
      .user-info {
        display: none;
      }
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

function getRoleTooltip(role) {
  if (!role) return "No role assigned";
  return `Role: ${role}`;
}

function activeClass(currentPath, href) {
  const isActive =
    href === "/" ? currentPath === "/" : currentPath.startsWith(href);
  return isActive ? "nav-link nav-link--active" : "nav-link";
}

function renderPublicLinks(currentPath) {
  return html`
    <a href="/blog" class="${activeClass(currentPath, "/blog")}">Blog</a>
    <a
      href="/blog/volunteer"
      class="${activeClass(currentPath, "/blog/volunteer")}"
      >Volunteer</a
    >
  `;
}

function renderAuthed(user, summary, currentPath, stateCode, onStateChange) {
  const tooltip = getRoleTooltip(user.role);
  const active = (href) => activeClass(currentPath, href);
  return html`
    <span class="user-info" data-tooltip="${tooltip}" data-placement="bottom">
      ${user.avatar_url
        ? html`<img class="user-avatar" src="${user.avatar_url}" alt="" />`
        : html`<span class="user-dot"></span>`}
      <span class="user-name"
        >${user.display_name || user.email || "User"}</span
      >
    </span>
    <civ-select-state
      class="nav-state-selector"
      .selected=${stateCode}
      @state-change=${onStateChange}
    ></civ-select-state>
    <a href="/" class="${active("/")}">Home</a>
    <a href="/blog" class="${active("/blog")}">Blog</a>
    ${user.permissions?.can_view_reviews_page
      ? html`<a href="/review" class="${active("/review")}">Reviews</a>`
      : ""}
    ${user.permissions?.can_view_activity_page
      ? html`<a href="/activity" class="${active("/activity")}">Activity</a>`
      : ""}
    ${user.permissions?.can_view_queue_page
      ? html`<details class="nav-dropdown">
          <summary class="nav-link nav-dropdown-trigger">
            Manage <i class="fa-solid fa-chevron-down nav-dropdown-caret"></i>
          </summary>
          <div class="nav-dropdown__menu">
            <a href="/queue" class="${active("/queue")}">Bulk review
              <span class="nav-count ${summary == null ? "nav-count--hidden" : ""}"
                >${summary?.open_prs ?? 0}</span
              ></a>
            ${user.permissions?.can_write_config
              ? html`<a href="/roles" class="${active("/roles")}">Roles</a>`
              : ""}
          </div>
        </details>`
      : ""}
    ${user.permissions?.can_manage_roles
      ? html`<details class="nav-dropdown">
          <summary class="nav-link nav-dropdown-trigger">
            Admin <i class="fa-solid fa-chevron-down nav-dropdown-caret"></i>
          </summary>
          <div class="nav-dropdown__menu">
            <a href="/admin" class="${active("/admin")}">Users</a>
            ${user.permissions?.can_view_issues_page
              ? html`<a href="/issues" class="${active("/issues")}">Issues</a>`
              : ""}
          </div>
        </details>`
      : ""}
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
  const [stateCode, setStateCode] = useLocalStorage("app:default-state", "", {
    ttl: PERSIST_FOREVER,
  });

  const handleNavStateChange = (e) => {
    const newState = (e.detail.state || "").toLowerCase();
    setStateCode(newState);
    const path = window.location.pathname;
    // On the review routes, switch state with a full navigation back to the new
    // state's landing — an in-place URL change would leave the previous state's
    // in-memory session showing. The landing's Review/Resume button takes it from
    // there.
    if (path === REVIEW_PATH || path === REVIEW_SESSION_PATH) {
      window.location.href = landingUrl(newState);
      return;
    }
    const params = new URLSearchParams(window.location.search);
    if (newState) params.set(STATE_PARAM, newState);
    else params.delete(STATE_PARAM);
    const qs = params.toString();
    window.history.replaceState(
      {},
      "",
      `${window.location.pathname}${qs ? "?" + qs : ""}`,
    );
  };
  const [theme, setTheme] = useLocalStorage(STORAGE_KEYS.THEME, "", {
    ttl: PERSIST_FOREVER,
  });
  const resolvedTheme =
    theme ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light");
  document.documentElement.dataset.theme = resolvedTheme;
  const toggleTheme = () =>
    setTheme(resolvedTheme === "dark" ? "light" : "dark");
  const onLogoutClick = () => localStorage.removeItem("app:default-state");
  const summary = useSummary(canViewQueue, stateCode);
  const currentPath = window.location.pathname;
  return html`
    ${NAVBAR_CSS}
    <nav class="${!isAuthed ? "nav--logged-out" : ""}">
      <a href="/" class="nav-brand">
        <span class="nav-brand-icon">
          <i class="fa-solid fa-landmark"></i>
        </span>
        CivicPatch
        <span class="nav-beta-badge">BETA</span>
      </a>
      ${isAuthed
        ? html`<a
            href="${API_URL}/api/v1/auth/logout?redirect=${encodeURIComponent(
              window.location.href,
            )}"
            class="nav-logout"
            @click=${onLogoutClick}
            ><i class="fa-solid fa-right-from-bracket"></i> Logout</a
          >`
        : ""}
      <div class="nav-links">
        <button
          class="theme-toggle"
          @click=${toggleTheme}
          aria-label="Toggle theme"
          title="${resolvedTheme === "dark"
            ? "Switch to light mode"
            : "Switch to dark mode"}"
        >
          <i
            class="fa-solid ${resolvedTheme === "dark" ? "fa-sun" : "fa-moon"}"
          ></i>
        </button>
        ${isAuthed
          ? renderAuthed(
              userData,
              summary,
              currentPath,
              stateCode,
              handleNavStateChange,
            )
          : html`
              ${renderPublicLinks(currentPath)}
              <a class="login-link" href="/login"
                ><i class="fa-solid fa-envelope"></i> Sign in</a
              >
            `}
      </div>
    </nav>
  `;
}

customElements.define(
  "civ-navbar",
  component(Navbar, { useShadowDOM: false, observedAttributes: ["user"] }),
);
