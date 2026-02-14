import { component } from 'haunted';
import { html } from 'lit';
import { diffLines } from 'diff';

function DiffPreview({ original, updated }) {
    const diff = diffLines(original, updated);

    const rows = [];
    let origLineNum = 1;
    let updLineNum = 1;

    diff.forEach(part => {
        const lines = part.value.split('\n');
        if (lines[lines.length - 1] === '') lines.pop();

        lines.forEach(line => {
            let origNum = '', updNum = '';
            let origCell = '', updCell = '';
            let origClass = 'diff-cell', updClass = 'diff-cell';

            if (part.removed) {
                origNum = origLineNum++;
                origCell = line;
                origClass += ' removed';
            } else if (part.added) {
                updNum = updLineNum++;
                updCell = line;
                updClass += ' added';
            } else {
                origNum = origLineNum++;
                updNum = updLineNum++;
                origCell = updCell = line;
            }

            rows.push(html`
                <tr>
                    <td class="line-number">${origNum}</td>
                    <td class="${origClass}">${origCell}</td>
                    <td class="line-number">${updNum}</td>
                    <td class="${updClass}">${updCell}</td>
                </tr>
            `);
        });
    });

    return html`
        <style>
            .diff-cell {
                font-family: var(--pico-font-monospace, monospace);
                white-space: pre-wrap;
                max-height: 200px;
                overflow: auto;
                padding: var(--pico-form-element-spacing-vertical) var(--pico-form-element-spacing-horizontal);
                border-radius: var(--pico-border-radius);
            }
            .diff-cell.removed {
                background-color: rgba(var(--catppuccin-red), 0.2); /* Softer red for removed lines */
                color: rgb(var(--catppuccin-red)); /* Red text for removed lines */
            }
            .diff-cell.added {
                background-color: rgba(var(--catppuccin-green), 0.2); /* Softer green for added lines */
                color: rgb(var(--catppuccin-green)); /* Green text for added lines */
            }
            .line-number {
                text-align: right;
                color: rgb(var(--catppuccin-subtext0)); /* Muted text for line numbers */
                font-family: var(--pico-font-monospace, monospace);
                padding: var(--pico-form-element-spacing-vertical) var(--pico-form-element-spacing-horizontal);
                user-select: none;
                background: rgb(var(--catppuccin-surface1)); /* Darker background for line numbers */
                border-right: 1px solid rgb(var(--catppuccin-surface2)); /* Subtle border */
                min-width: 3em;
            }
            table.diff-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                background-color: rgb(var(--catppuccin-base)); /* Table background */
                border: 1px solid rgb(var(--catppuccin-mantle)); /* Table border */
                border-radius: var(--pico-border-radius);
                overflow: hidden;
            }
            table.diff-table th {
                background-color: rgb(var(--catppuccin-mantle)); /* Header background */
                color: rgb(var(--catppuccin-text)); /* Header text color */
                font-weight: bold;
                padding: var(--pico-form-element-spacing-vertical) var(--pico-form-element-spacing-horizontal);
                text-align: left;
                border-bottom: 1px solid rgb(var(--catppuccin-surface2));
            }
            table.diff-table td {
                vertical-align: top;
                border-bottom: 1px solid rgb(var(--catppuccin-surface2)); /* Row separator */
                padding: var(--pico-form-element-spacing-vertical) var(--pico-form-element-spacing-horizontal);
            }
            table.diff-table tr:nth-child(even) {
                background-color: rgba(var(--catppuccin-surface1), 0.5); /* Alternate row background */
            }
        </style>
        <table class="table diff-table">
            <thead>
                <tr>
                    <th></th>
                    <th>Original</th>
                    <th></th>
                    <th>Updated</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

customElements.define(
    'diff-preview',
    component(DiffPreview, {
        useShadowDOM: false
    })
);