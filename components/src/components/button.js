class MyButton extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });

    // Create button
    this.button = document.createElement('button');
    this.button.textContent = this.getAttribute('label') || 'Click me';

    // Basic styles
    const style = document.createElement('style');
    style.textContent = `
      button {
        padding: 0.5rem 1rem;
        font-size: 1rem;
        border: 2px solid #333;
        border-radius: 4px;
        background: white;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }
    `;

    this.shadowRoot.append(style, this.button);

    // Handle click
    this.button.addEventListener('click', () => {
      alert('Button clicked!');
    });
  }

  static get observedAttributes() {
    return ['label', 'disabled'];
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (name === 'label') {
      this.button.textContent = newValue;
    }
    if (name === 'disabled') {
      this.button.disabled = newValue !== null;
    }
  }
}

// Define the custom element
customElements.define('my-button', MyButton);

