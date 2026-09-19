import { html } from "lit-html";

// Font Awesome's spinner, the same `fa-spin` idiom the Re-scrape button uses.
export function loadingLine(label: string) {
  return html`<p class="import-hint">
    <i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i> ${label}
  </p>`;
}
