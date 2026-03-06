import { component } from 'haunted';
import { html } from 'lit';
import { useAuth } from '../hooks/useAuth.js';
const API_URL = __API_URL__;

// Only keep layout and spacing styles, remove color/background overrides for nav-link, btn-login, btn-logout
const NAVBAR_CSS = html`
  <style>
    civ-navbar {
      display: block;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    nav {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0.875rem 0;
      background: var(--pico-background-color);
      border-bottom: 1px solid var(--pico-muted-border-color);
      user-select: none;
    }
    .nav-brand {
      font-weight: 700;
      font-size: 1.25rem;
      text-decoration: none;
      color: var(--pico-color);
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .nav-brand:hover {
      color: var(--pico-primary);
    }
    .nav-brand i {
      font-size: 1.1rem;
      color: var(--pico-primary);
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 0.75rem;
    }
    .user-info {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      color: var(--pico-muted-color);
      font-size: 0.875rem;
    }
    .user-info i {
      font-size: 0.5rem;
      color: var(--pico-primary-background);
    }
    .loading {
      color: var(--pico-muted-color);
      font-size: 0.875rem;
    }
    .button, .button.secondary {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-weight: 500;
      font-size: 0.95rem;
      padding: 0.5rem 1.1rem;
      border-radius: 0.375rem;
      border: none;
      cursor: pointer;
      text-decoration: none;
      transition: background 0.15s, color 0.15s;
      background: var(--pico-primary);
      color: var(--pico-primary-inverse);
    }
    .button.secondary {
      background: var(--pico-secondary-background);
      color: var(--pico-secondary-inverse);
    }
    .button:hover, .button.secondary:hover {
      background: var(--pico-primary-hover-background);
      color: var(--pico-primary-inverse);
      text-decoration: none;
    }
    .button.secondary:hover {
      background: var(--pico-secondary-hover-background);
      color: var(--pico-secondary-inverse);
    }
    .loading-skeleton {
      display: inline-block;
      width: 7em;
      height: 0.8em;
      background-color: var(--pico-muted-background);
      border-radius: 0.4em;
      margin: 0 0.2em;
      vertical-align: middle;
      /* No animation */
    }
    @keyframes loading-breadstick {
      0%, 80%, 100% {
        transform: scale(0);
      }
      40% {
        transform: scale(1);
      }
    }
  </style>
`;

function renderUserInfo(user) {
  return html`
    <span class="user-info">
      <i class="fas fa-circle"></i>
      ${user.email || 'User'}
    </span>
    <a
      href="${API_URL}/api/v1/auth/logout?redirect=${encodeURIComponent(window.location.href)}"
      class="button secondary"
    >
      Logout
    </a>
  `;
}

function renderLogin() {
  return html`
    <a
      href="${API_URL}/api/v1/auth/github/login?redirect=${encodeURIComponent(window.location.href)}"
      class="button"
    >
      <i class="fab fa-github"></i>
      Login
    </a>
  `;
}

function Navbar() {
  const { user, loading, permissions } = useAuth();

  return html`
    ${NAVBAR_CSS}
    <nav>
      <a href="/" class="nav-brand">
        <i class="fas fa-landmark"></i>
        CivicPatch
      </a>
      <div class="nav-links">
        ${user ? html`
          <a href="/progress" class="nav-link">Progress</a>
          <!-- Conditionally show admin links based on permissions -->
          <!--<a href="/jurisdictions" class="nav-link">Jurisdictions</a>-->
          <!--<a href="/jobs" class="nav-link">Jobs</a>-->
        ` : null
        }
        ${loading
          ? html`
              <span class="loading" style="display:inline-flex;align-items:center;">
                <span class="loading-skeleton"></span>
                <span class="loading-skeleton"></span>
                <span class="loading-skeleton"></span>
              </span>
            `
          : user
            ? renderUserInfo(user)
            : renderLogin()
        }
      </div>
    </nav>
  `;
}

customElements.define('civ-navbar', component(Navbar, { useShadowDOM: false }));