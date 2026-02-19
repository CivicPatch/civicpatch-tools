import { useState, component, useEffect, useRef } from 'haunted';
import { html, css } from 'lit';
import { ref, createRef } from 'lit/directives/ref.js';
import { keyed } from 'lit/directives/keyed.js';

const KEYCODES = {
    RIGHT_ARROW: 'ArrowRight',
    LEFT_ARROW: 'ArrowLeft',
    UP_ARROW: 'ArrowUp',
    DOWN_ARROW: 'ArrowDown',
    ENTER: 'Enter',
    TAB: 'Tab',
}

const styles = css`
  civ-table-cell {
    display: block;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
        div {
            width: 100%;
            height: 100%;
            min-height: 1em;
            display: flex;
            align-items: stretch;
        }
        span {
            width: 100%;
            height: 100%;
            display: block;
            min-height: 1em;
            box-sizing: border-box;
            border: 2px solid transparent;
            padding: 0.4rem;
            white-space: normal;
            word-break: break-word;
            overflow-wrap: break-word;
        }
        span.cell-content[contenteditable="true"]:focus {
            box-sizing: border-box;
            outline: 2px solid rgb(var(--catppuccin-sapphire));
            outline-offset: -2px;
            border: 2px solid transparent;
            border-radius: 4px;
        }
        div:focus {
            outline: 1px solid rgb(var(--catppuccin-sapphire));
            outline-offset: -2px;
        }
        .tag-list button {
            font-size: 0.7em;
        }
        .tag-list {
            flex-direction: row;
            flex-wrap: wrap;
            align-items: flex-start;
            gap: 0.25rem;
            padding: 0.4rem;
        }
        .tag-input {
            flex-basis: 100%;  /* forces own line */
            min-height: 1.2em;
            outline: none;
            border: none;
            background: transparent;
        }
        .tag-input:empty::before {
            content: attr(data-placeholder);
            color: #aaa;
            pointer-events: none;
        }
  }
`;

function TableCell({ 
    identifier, 
    rowIndex, 
    colIndex, 
    field, 
    value, 
    //onDataChange,
    //onEditStart,
    //onMove,
    focused,
    editing
 }) {
    const isSingle = typeof value === 'string' || value === null
    const [editValue, setEditValue] = useState(isSingle ? value || '' : Array.isArray(value) ? [...value] : []);
    const didMount = useRef(false);
    const element = this;

    useEffect(() => {
        if (didMount.current) {
            console.log(element)
            element.dispatchEvent(new CustomEvent('data-change', {
                detail: { identifier, field, value: editValue },
                bubbles: true,
                composed: true
            }));
        } else {
            didMount.current = true;
        }
    }, [editValue]);


    useEffect(() => {
        if (editing) { 
            const contentEditableDiv = element.querySelector('span[contenteditable="true"]');
            if (contentEditableDiv) {
                contentEditableDiv.focus();
                // Move cursor to end
                const range = document.createRange();
                range.selectNodeContents(contentEditableDiv);
                range.collapse(false); // false = collapse to END
                const sel = window.getSelection();
                sel.removeAllRanges();
                sel.addRange(range);
            }
        } else if (focused) {
            const divToFocus = element.querySelector('div');
            if (divToFocus) {
                divToFocus.focus();
            }
        }
    }, [focused, editing]);


    function renderSingleCell() {
        if (!editing) {
            return keyed('display', html`
                <span class="cell-content">${value}</span>
            `);
        }
        return keyed('edit', html`
            <span
                class="cell-content"
                contenteditable="true"
                ${ref(el => { if (el && !el.dataset.initialized) { el.innerText = editValue; el.dataset.initialized = 'true'; } })}
                @input=${e => setEditValue(e.currentTarget?.innerText)}
            ></span>
        `);
    }

    function dispatchEditStart() {
        this.dispatchEvent(new CustomEvent('edit-start', {
            detail: { row: rowIndex, col: colIndex, value },
            bubbles: true,
            composed: true
        }));
    }

    function dispatchEditStop () {
        this.dispatchEvent(new CustomEvent('edit-stop', {
            detail: { row: rowIndex, col: colIndex, identifier, value: editValue },
            bubbles: true,
            composed: true
        }));
    }

    function dispatchOnMove(direction) {
        this.dispatchEvent(new CustomEvent('edit-stop', {
            detail: { row: rowIndex, col: colIndex, identifier, value: editValue },
            bubbles: true,
            composed: true
        }));
        this.dispatchEvent(new CustomEvent('on-move', {
            detail: { row: rowIndex, col: colIndex, identifier, direction },
            bubbles: true,
            composed: true
        }));
    }


    function handleKeyDown(e) {
        // console.log("Key down in cell", e.key, { editing, focused });

        // If editing is active, and directional key, return and allow
        // input to handle it

        switch (e.key) {
            case KEYCODES.TAB:
                e.preventDefault();

                if (e.shiftKey) {
                    dispatchOnMove.call(this, 'left');
                } else {
                    dispatchOnMove.call(this, 'right');
                }
                return;
            case KEYCODES.ENTER:
                e.preventDefault();
                if (editing) {
                    // Exit edit mode
                    dispatchEditStop.call(this);
                } else {
                    // Trigger edit mode
                    dispatchEditStart.call(this);
                }
                return;
            case KEYCODES.RIGHT_ARROW:
                if (editing) return;

                e.preventDefault();
                dispatchOnMove.call(this, 'right');
                return;
            case KEYCODES.LEFT_ARROW:
                if (editing) return;

                e.preventDefault();
                dispatchOnMove.call(this, 'left');
                return;
            case KEYCODES.UP_ARROW:
                if (editing) return;

                e.preventDefault();
                dispatchOnMove.call(this, 'up');
                return;
            case KEYCODES.DOWN_ARROW:
                if (editing) return;

                e.preventDefault();
                dispatchOnMove.call(this, 'down');
                return;
            default:
                return;
        }
    }

    const addItem = val => setEditValue([...editValue, val]);
    const removeItem = i => setEditValue(editValue.filter((_, idx) => idx !== i));

    function renderListCell() {
        const displayList = Array.isArray(value) ? value : [];
        const editList = Array.isArray(editValue) ? editValue : [];

        return html`
            <div class="tag-list ${editing ? 'editing' : ''}">
                ${editList.map((item, i) => html`
                        <button type="button" @click=${() => removeItem(i)}>
                            ${item} ×
                        </button>`
                )}
                ${editing ? html`
                    <span
                        class="tag-input"
                        contenteditable="true"
                        data-placeholder="Add…"
                        ${ref(el => { if (el && !el.dataset.initialized) { el.innerText = ''; el.dataset.initialized = 'true'; } })}
                        @keydown=${e => {
                            if (e.key === 'Enter' || e.key === ',') {
                                e.preventDefault();
                                const val = e.currentTarget.innerText.trim();
                                if (val) {
                                    addItem(val);
                                    e.currentTarget.innerText = '';
                                }
                            }
                        }}
                    ></span>
                ` : ''}
            </div>
        `;
    }

    return html`
        <style>${styles}</style>
        <div
            tabIndex="-1"
            data-col=${colIndex} 
            data-row=${rowIndex} 
            data-field=${field} 
            @keydown=${handleKeyDown}
        >
            ${isSingle ? renderSingleCell() : renderListCell()}
        </div>
    `;
}

customElements.define('civ-table-cell', component(TableCell, { observedAttributes: ['identifier', 'rowIndex', 'colIndex', 'field', 'value'], useShadowDOM: false }));