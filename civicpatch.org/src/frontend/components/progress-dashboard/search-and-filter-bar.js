import { html } from 'lit-html';
import { component } from 'haunted';

function SearchAndFilterBar() {
  return html`
    <div style="margin: 1em 0;">
      <input type="text" placeholder="Search..." style="margin-right: 1em;" />
      <select>
        <option>All Statuses</option>
        <option>Covered</option>
        <option>Not Covered</option>
      </select>
    </div>
  `;
}

customElements.define('search-and-filter-bar', component(SearchAndFilterBar, { useShadowDOM: false }));
export default SearchAndFilterBar;