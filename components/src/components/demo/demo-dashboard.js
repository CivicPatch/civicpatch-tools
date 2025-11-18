import { html, css } from 'lit';
import { component, useState, useEffect } from 'haunted';
import { useApi } from '../../hooks/use-api.js';
import { apiConfig } from '../../api-config.js';

// Import other components to include them in the dashboard
import '../example.js';
import '../map.js';
import './demo-api-config.js';

function DemoDashboard() {
  const [activeTab, setActiveTab] = useState('config');
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
      background-color: var(--pico-color-green-500, #28a745);
    }
    
    .status-indicator.disconnected {
      background-color: var(--pico-color-amber-500, #ffc107);
    }
    
    /* Tab styling with proper contrast */
    .nav-tabs {
      display: flex;
      margin-bottom: 0;
      border-bottom: 1px solid var(--pico-muted-border-color, #dee2e6);
      list-style: none;
      padding: 0;
    }
    
    .nav-tabs li {
      margin: 0;
    }
    
    .nav-tab {
      padding: 0.75rem 1rem;
      border: 1px solid transparent;
      border-bottom: none;
      background-color: var(--pico-card-background-color, #f8f9fa);
      color: var(--pico-muted-color, #6c757d);
      cursor: pointer;
      border-radius: 0.375rem 0.375rem 0 0;
      margin-right: 0.125rem;
      font-weight: 500;
      transition: all 150ms ease;
    }
    
    .nav-tab:hover {
      background-color: var(--pico-secondary-hover, #e9ecef);
      color: var(--pico-color, #212529);
    }
    
    .nav-tab.active {
      background-color: var(--pico-background-color, #fff);
      color: #F0F1F3;
      border-color: var(--pico-muted-border-color, #dee2e6);
      border-bottom-color: var(--pico-background-color, #fff);
      font-weight: 600;
    }
    
    .tab-content {
      padding-top: 1rem;
    }
  `;

  const renderTabContent = () => {
    switch (activeTab) {
      case 'config':
        return html`
          <div class="content-section active">
            <hgroup>
              <h2>API Configuration</h2>
              <p>Configure your API settings to connect to CivicPatch services.</p>
            </hgroup>
            <demo-api-config></demo-api-config>
          </div>
        `;
      
      case 'example':
        return html`
          <div class="content-section active">
            <hgroup>
              <h2>Example API Data</h2>
              <p>This component demonstrates fetching data from the CivicPatch API.</p>
            </hgroup>
            <my-example></my-example>
          </div>
        `;
      
      case 'map':
        return html`
          <div class="content-section active">
            <hgroup>
              <h2>Interactive Map</h2>
              <p>Explore geographical data with our interactive mapping component.</p>
            </hgroup>
            <article>
              <div class="map-container">
                <civ-map canmove="true"></civ-map>
              </div>
            </article>
          </div>
        `;
      
      case 'overview':
        return html`
          <div class="content-section active">
            <hgroup>
              <h2>Component Overview</h2>
              <p>A comprehensive view of all available components in the CivicPatch toolkit.</p>
            </hgroup>
            
            <div class="grid">
              <article>
                <header><strong>API Configuration</strong></header>
                <demo-api-config></demo-api-config>
              </article>
              
              <article>
                <header><strong>Example Data</strong></header>
                <my-example></my-example>
              </article>
            </div>
            
            <article>
              <header><strong>Interactive Map</strong></header>
              <div class="map-container">
                <civ-map canmove="true"></civ-map>
              </div>
            </article>
          </div>
        `;
      
      default:
        return html`<p><em>Select a tab to view content</em></p>`;
    }
  };

  return html`
    <style>${styles}</style>
    <main class="container">
      <header>
        <hgroup>
          <h1>CivicPatch Components Dashboard</h1>
          <p>Interactive demonstration of CivicPatch web components</p>
        </hgroup>
        
        <details role="status" ${baseUrl ? 'open' : ''}>
          <summary>
            <span class="status-indicator ${baseUrl ? 'connected' : 'disconnected'}"></span>
            API Status: ${baseUrl ? `Connected to ${baseUrl}` : 'Not configured'}
          </summary>
          ${!baseUrl ? html`<p><small>Configure your API settings in the API Config tab to get started.</small></p>` : ''}
        </details>
      </header>
      
      <nav>
        <ul class="nav-tabs" role="tablist">
          <li>
            <button 
              class="nav-tab ${activeTab === 'config' ? 'active' : ''}"
              role="tab"
              aria-selected="${activeTab === 'config'}"
              @click=${() => setActiveTab('config')}
            >
              API Config
            </button>
          </li>
          <li>
            <button 
              class="nav-tab ${activeTab === 'example' ? 'active' : ''}"
              role="tab"
              aria-selected="${activeTab === 'example'}"
              @click=${() => setActiveTab('example')}
            >
              Example Data
            </button>
          </li>
          <li>
            <button 
              class="nav-tab ${activeTab === 'map' ? 'active' : ''}"
              role="tab"
              aria-selected="${activeTab === 'map'}"
              @click=${() => setActiveTab('map')}
            >
              Map
            </button>
          </li>
          <li>
            <button 
              class="nav-tab ${activeTab === 'overview' ? 'active' : ''}"
              role="tab"
              aria-selected="${activeTab === 'overview'}"
              @click=${() => setActiveTab('overview')}
            >
              Overview
            </button>
          </li>
        </ul>
      </nav>
      
      <section class="tab-content" role="tabpanel">
        ${renderTabContent()}
      </section>
    </main>
  `;
}

customElements.define('demo-dashboard', component(DemoDashboard, { useShadowDOM: false }));