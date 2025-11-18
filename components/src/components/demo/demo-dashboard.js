import { html, css } from 'lit';
import { component, useState, useEffect } from 'haunted';
import { useApi } from '../../hooks/use-api.js';

// Tab configuration with HTML templates
const TAB_CONFIG = [
  {
    id: 'config',
    label: 'API Config',
    title: 'API Configuration',
    description: 'Configure your API settings to connect to CivicPatch services.',
    template: html`<demo-api-config></demo-api-config>`,
  },
  {
    id: 'example',
    label: 'Example Data',
    title: 'Example API Data',
    description: 'This component demonstrates fetching data from the CivicPatch API.',
    template: html`<my-example></my-example>`,
  },
  {
    id: 'map',
    label: 'Map',
    title: 'Interactive Map',
    description: 'Explore geographical data with our interactive mapping component.',
    template: html`<civ-map canmove="true"></civ-map>`,
  }
];

function DemoDashboard() {
  const [activeTab, setActiveTab] = useState(TAB_CONFIG[0].id);
  const { baseUrl } = useApi();

  const styles = css`
    /* Minimal styles to complement Pico CSS */
    .status-indicator {
      display: inline-block;
      width: 0.75rem;
      height: 0.75rem;
      border-radius: 50%;
      margin-right: 0.5rem;
    }
    
    .status-indicator.connected {
      background-color: var(--pico-color-green-500);
    }
    
    .status-indicator.disconnected {
      background-color: var(--pico-color-amber-500);
    }
    
    /* API Status styling */
    .api-status {
      margin-top: 1rem;
      display: flex;
      align-items: center;
      gap: 0.25rem;
    }
    
    .api-status small {
      color: var(--pico-muted-color);
    }
    
    /* Tab styling with better contrast */
    .nav-tabs {
      display: flex;
      margin-bottom: 0;
      border-bottom: 2px solid var(--pico-color-slate-200);
      list-style: none;
      padding: 0;
    }
    
    .nav-tabs li {
      margin: 0;
    }
    
    .nav-tab {
      padding: 0.5rem 1rem;
      border: none;
      background-color: transparent;
      color: var(--pico-color-azure-50);
      cursor: pointer;
      border-radius: 0.5rem 0.5rem 0 0;
      margin-right: 0.25rem;
      font-weight: 500;
      transition: all 200ms ease;
      border-bottom: 3px solid transparent;
    }
    
    .nav-tab:hover {
      background-color: var(--pico-color-slate-100);
      color: var(--pico-color-slate-800);
      border-bottom-color: var(--pico-color-blue-300);
    }
    
    .nav-tab.active {
      background-color: var(--pico-color-azure-500);
      color: var(--pico-color-azure-50);
      border-bottom-color: var(--pico-color-azure-850);
      font-weight: 600;
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    .tab-content {
      padding-top: 1.5rem;
      border-radius: 0 0 0.5rem 0.5rem;
      min-height: 400px;
    }
    
    /* Make child components blend with background */
    .tab-content article {
      background-color: var(--pico-background-color, #f8f9fa);
    }
  `;

  const renderComponent = (config) => {
    return config.template;
  };

  const renderTabContent = () => {
    const activeConfig = TAB_CONFIG.find(tab => tab.id === activeTab);
    if (!activeConfig) return html`<p><em>Tab not found</em></p>`;

    return html`
      <div class="content-section active">
        <hgroup>
          <h2>${activeConfig.title}</h2>
          <p>${activeConfig.description}</p>
        </hgroup>
        ${renderComponent(activeConfig)}
      </div>
    `;
  };

  return html`
    <style>${styles}</style>
    <main class="container">
      <header>
        <hgroup>
          <h1>CivicPatch Components Dashboard</h1>
          <p>Interactive demonstration of CivicPatch web components</p>
        </hgroup>
        
        <div class="api-status">
          <span class="status-indicator ${baseUrl ? 'connected' : 'disconnected'}"></span>
          <span>API Status: ${baseUrl ? `Connected to ${baseUrl}` : 'Not configured'}</span>
          ${!baseUrl ? html`<small> - Configure your API settings in the API Config tab to get started.</small>` : ''}
        </div>
      </header>
      
      <nav>
        <ul class="nav-tabs" role="tablist">
          ${TAB_CONFIG.map(tab => html`
            <li>
              <button 
                class="nav-tab ${activeTab === tab.id ? 'active' : ''}"
                role="tab"
                aria-selected="${activeTab === tab.id}"
                @click=${() => setActiveTab(tab.id)}
              >
                ${tab.label}
              </button>
            </li>
          `)}
        </ul>
      </nav>
      
      <section class="tab-content" role="tabpanel">
        ${renderTabContent()}
      </section>
    </main>
  `;
}

customElements.define('demo-dashboard', component(DemoDashboard, { useShadowDOM: false }));