import { html, render } from 'lit';
import { component, useState, useEffect } from 'haunted';

function MyExample() {
  const [data, setData] = useState(null);

  // Example: fetch data from proxy on mount
  useEffect(() => {
    fetch('/api/api_proxy/jurisdictions/states')
      .then((res) => res.json())
      .then(setData)
      .catch(console.error);
  }, []);

  return html`
    <div style="font-family: sans-serif; border: 1px solid #ccc; padding: 1rem;">
      <h3>Example Component (tbd: replace with others)</h3>
      <div>
        <strong>Data from proxy:</strong>
        <pre>${data ? JSON.stringify(data, null, 2) : 'Loading...'}</pre>
      </div>
    </div>
  `;
}

// Register as a web component
customElements.define('my-example', component(MyExample));

