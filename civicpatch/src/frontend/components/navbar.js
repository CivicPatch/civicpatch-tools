import { component } from 'haunted';
import { html } from 'lit';
import { useAuth } from './hooks/useAuth.js';
const API_URL = __API_URL__;

function Navbar() {
  const { user, loading } = useAuth();

  return html`
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
        padding: 0.875rem 2rem;
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
        color: #22c55e;
      }
      .btn-login, .btn-logout {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        text-decoration: none;
        font-weight: 500;
        font-size: 0.875rem;
        padding: 0.5rem 1rem;
        border-radius: 0.375rem;
        transition: all 0.15s ease;
      }
      .btn-login {
        background: var(--pico-primary);
        color: white;
      }
      .btn-login:hover {
        background: var(--pico-primary-hover);
      }
      .btn-logout {
        background: transparent;
        color: var(--pico-muted-color);
        border: 1px solid var(--pico-muted-border-color);
      }
      .btn-logout:hover {
        background: var(--pico-muted-border-color);
        color: var(--pico-color);
      }
      .loading {
        color: var(--pico-muted-color);
        font-size: 0.875rem;
      }
    </style>
    <nav>
      <a href="/" class="nav-brand">
        <i class="fas fa-landmark"></i>
        CivicPatch
      </a>
      <div class="nav-links">
        ${loading
          ? html`<span class="loading">Loading...</span>`
          : user
            ? html`
                <span class="user-info">
                  <i class="fas fa-circle"></i>
                  ${user.email || 'User'}
                </span>
                <a href="${API_URL}/api/v1/auth/logout?redirect=${encodeURIComponent(window.location.href)}" class="btn-logout">
                  Logout
                </a>
              `
            : html`
                <a href="${API_URL}/api/v1/auth/github/login?redirect=${encodeURIComponent(window.location.href)}" class="btn-login">
                  <i class="fab fa-github"></i>
                  Login
                </a>
              `
        }
      </div>
    </nav>
  `;
}

customElements.define('civ-navbar', component(Navbar, { useShadowDOM: false }));