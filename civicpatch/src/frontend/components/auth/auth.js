import { html } from 'lit-html';
import { component, useState, useEffect } from 'haunted';

function AuthStatus() {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [user, setUser] = useState(null);

  useEffect(() => {
    async function checkAuth() {
      try {
        const res = await fetch('/api/api_proxy/me', { credentials: 'include' });
        const data = await res.json();
        setAuthenticated(data.authenticated);
        setUser(data.authenticated ? data : null);
      } catch {
        setAuthenticated(false);
        setUser(null);
      }
      setLoading(false);
    }
    checkAuth();
  }, []);

  if (loading) {
    return html`<div>Loading...</div>`;
  }

  console.log("auth running")

  return authenticated
    ? html`<slot .user=${user}></slot>`
    : html`
        <button @click=${() => window.location.href = '/api/v1/auth/github/login'}>
          Login with GitHub
        </button>
      `;
}

customElements.define('auth-status', component(AuthStatus));