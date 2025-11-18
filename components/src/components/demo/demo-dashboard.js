import { html, css } from 'lit';
import { component, useState } from 'haunted';
import { useApi } from '../../hooks/use-api.js';
import { registerCivMap } from '../map.js';

registerCivMap();

// Lazy loading configuration
const TAB_CONFIG = [
  {
    id: 'config',
    label: 'API Config',
    title: 'API Configuration',
    description: 'Configure your API settings to connect to CivicPatch services.',
    loader: () => import('./demo-api-config.js').then(() => html`<demo-api-config></demo-api-config>`),
  },
  {
    id: 'example',
    label: 'Example Data',
    title: 'Example API Data',
    description: 'This component demonstrates fetching data from the CivicPatch API.',
    loader: () => import('../example.js').then(() => html`<my-example></my-example>`),
  },
  {
    id: 'map',
    label: 'Map',
    title: 'Interactive Map',
    description: 'Explore geographical data with our interactive mapping component.',
    loader: () => import('../map.js').then(() => html`<civ-map canmove="true"></civ-map>`),
  }
];

function DemoDashboard() {
  const { baseUrl } = useApi();
  const [loadedComponents, setLoadedComponents] = useState(new Set());
  const [componentTemplates, setComponentTemplates] = useState(new Map());

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
    
    .loading {
      padding: 2rem;
      text-align: center;
      color: var(--pico-muted-color);
    }

    header {
      margin-bottom: 2rem;
    }
  `;

  const handleAccordionToggle = async (event, section) => {
    if (event.target.open && !loadedComponents.has(section.id)) {
      try {
        const template = await section.loader();
        setComponentTemplates(prev => new Map(prev).set(section.id, template));
        setLoadedComponents(prev => new Set(prev).add(section.id));
      } catch (error) {
        console.error(`Failed to load component ${section.id}:`, error);
        setComponentTemplates(prev => new Map(prev).set(section.id, 
          html`<p class="error">Failed to load component</p>`
        ));
      }
    }
  };

  const renderComponent = (section) => {
    if (!loadedComponents.has(section.id)) {
      return html`<div class="loading">Loading component...</div>`;
    }
    return componentTemplates.get(section.id) || html`<div class="loading">Loading...</div>`;
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
      
      ${TAB_CONFIG.map(section => html`
        <details 
          ${section.id === 'config' ? 'open' : ''} 
          @toggle=${(e) => handleAccordionToggle(e, section)}
        >
          <summary role="button" class="outline">${section.title}</summary>
          <article>
            <p>${section.description}</p>
            ${renderComponent(section)}
          </article>
        </details>
      `)}
    </main>
  `;
}

customElements.define('demo-dashboard', component(DemoDashboard, { useShadowDOM: false }));