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
                padding: 0.25em 0.5em;
            }
            .diff-cell.removed {
                background: color-mix(in srgb, var(--pico-del-color, #c00) 10%, transparent 90%);
            }
            .diff-cell.added {
                background: color-mix(in srgb, var(--pico-ins-color, #080) 10%, transparent 90%);
            }
            .line-number {
                text-align: right;
                color: #aaa;
                font-family: var(--pico-font-monospace, monospace);
                padding: 0.25em 0.5em;
                user-select: none;
                background: #f6f8fa;
                min-width: 2em;
            }
            table.diff-table {
                width: 100%;
                border-collapse: collapse;
            }
            table.diff-table th, table.diff-table td {
                vertical-align: top;
                border-bottom: 1px solid #eee;
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