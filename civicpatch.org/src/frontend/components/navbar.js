import { component, useEffect } from "haunted";
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
import {
  municipalitiesUrl,
  isMunicipalitiesPath,
} from "../pages/municipalities-page/municipalities-routes.ts";
import "./search-jurisdictions/select-state.js";
import "./navbar.css";
// Font Awesome, self-hosted. It was a CDN kit until that kit started returning
// a bare 403 to every caller and every page in every environment lost its icons.
// Imported here because all 12 Vite entries pull the navbar in, and vite_css()
// links the emitted stylesheet in <head> — so the fonts are hashed, cached, and
// have no third party in the render path.
import "@fortawesome/fontawesome-free/css/all.min.css";

const API_URL = config.apiUrl;


function getRoleTooltip(role) {
  if (!role) return "No role assigned";
  return `Role: ${role}`;
}

function activeClass(currentPath, href) {
  const isActive =
    href === "/" ? currentPath === "/" : currentPath.startsWith(href);
  return isActive ? "nav-link nav-link--active" : "nav-link";
}

// Pages that aren't scoped to a state. On these we hide the state selector
// (it doesn't apply) and show a static "Global" badge instead. The badge is
// presentational only — it never touches the stored app:default-state, so the
// user's selected state is preserved for when they return to a scoped page.
// "/" gets an exact match (its own state selector — the "Find Representatives"
// widget — is page-local and deliberately doesn't write app:default-state)
// since a prefix match would swallow every route.
const GLOBAL_ROUTES = ["/activity", "/blog", "/admin"];
const isGlobalRoute = (currentPath) =>
  currentPath === "/" || GLOBAL_ROUTES.some((route) => currentPath.startsWith(route));

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
    ${isGlobalRoute(currentPath)
      ? html`<span class="nav-state-badge">Global</span>`
      : html`<civ-select-state
          class="nav-state-selector"
          .selected=${stateCode}
          @state-change=${onStateChange}
        ></civ-select-state>`}
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

function Navbar(host) {
  const { user } = host;
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

  // Native <details> dropdowns don't light-dismiss; close any open one when a
  // click lands outside it (the contains() check skips the summary that just
  // opened it) or on Escape. One document listener, work only while open.
  useEffect(() => {
    const closeOnOutsideClick = (e) => {
      for (const dropdown of host.querySelectorAll(".nav-dropdown[open]")) {
        if (!dropdown.contains(e.target)) dropdown.open = false;
      }
    };
    const closeOnEscape = (e) => {
      if (e.key !== "Escape") return;
      for (const dropdown of host.querySelectorAll(".nav-dropdown[open]")) {
        dropdown.open = false;
      }
    };
    document.addEventListener("click", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("click", closeOnOutsideClick);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

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
    // State is a path segment here (/{state}/local), not a query param — the
    // default in-place branch below would leave a stale/mismatched path
    // (/wa/local?state=co) if we didn't navigate instead.
    if (isMunicipalitiesPath(path)) {
      window.location.href = municipalitiesUrl(newState);
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
