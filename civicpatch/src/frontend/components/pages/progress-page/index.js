import { component } from "haunted";
import { html } from "lit-html";

function ProgressPage() {
  return html`
    <div>
      <p>This is the progress page content.</p>
    </div>
  `;
}

customElements.define(
  "progress-page",

  component(ProgressPage, {
    useShadowDOM: false,
  }),
);