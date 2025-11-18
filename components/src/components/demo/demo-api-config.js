import { html } from 'lit';
import { component, useState, useEffect } from 'haunted';
import { useApi } from '../../hooks/use-api.js';
import { apiConfig } from '../../api-config.js';

function DemoApiConfig() {
  const [token, setToken] = useState(sessionStorage.getItem('authToken') || '');
  const [baseUrl, setBaseUrl] = useState(sessionStorage.getItem('baseUrl') || '');
  const results = useApi(this)

  useEffect(() => {
      apiConfig.setApi(baseUrl, token)
  }, [])

  function saveConfig() {
      sessionStorage.setItem('baseUrl', baseUrl);
      sessionStorage.setItem('authToken', token);
      apiConfig.setApi(baseUrl, token);
      alert("Api config saved")
  }

  return html`
    <p>Note: if developing locally, use /api/api_proxy and fill out .env file</p>
    <div class="container" style="max-width: 400px; margin-top: 2rem;">
      <label>
        Base URL:<br />
        <input
          type="text"
          class="contrast"
          .value=${baseUrl}
          @input=${(e) => setBaseUrl(e.target.value)}
          placeholder="https://api.civicpatch.org/api or /api/api_proxy"
        />
      </label>
      <label>
        API token:<br />
        <input
          type="password"
          class="contrast"
          .value=${token}
          @input=${(e) => setToken(e.target.value)}
          placeholder="API token from api.civicpatch.org"
        />
      </label>
      <button @click=${saveConfig} style="margin-top: 0.5rem;">
        Save Config 
      </button>
    </div>
  `;
}

customElements.define('demo-api-config', component(DemoApiConfig, { useShadowDOM: false }));


