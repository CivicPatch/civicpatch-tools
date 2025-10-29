import { html, css, LitElement } from "lit";

class HelloWorld extends LitElement {
  // Define styles for the component
  static styles = css`
    p {
      color: green;
      font-size: 1.5rem;
    }
  `;
  // Define the component's template
  render() {
    return html`<p>Hello, World! This is a Lit component.</p>`;
  }
}

// Register the component as a custom element
customElements.define("hello-world", HelloWorld);
console.log("test 1");
