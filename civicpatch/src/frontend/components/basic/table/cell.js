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
    ESCAPE: 'Escape',
    BACKSPACE: 'Backspace',
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
            flex: 1;
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

        .tag-list {
            display: flex;
            flex-direction: row;
            flex-wrap: wrap;
            align-items: flex-start;
            align-content: flex-start;
            gap: 0.25rem;
            padding: 0.4rem;
            width: 100%;
            height: 100%;
            box-sizing: border-box;
        }

        .tag-list button {
            appearance: none;
            border: 1px solid #d0d0d0;
            background: #f0f2f5;
            border-radius: 999px;
            padding: 0.15rem 0.6rem;
            font-size: 0.72rem;
            font-family: inherit;
            cursor: pointer;
            color: #333;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            display: inline-flex;
            align-items: center;
            gap: 0.25rem;
        }

        .tag-list button:hover {
            background: #e2e6ea;
            border-color: #b0b8c1;
        }

        .tag-input {
            flex-basis: 100%;
            min-height: 1.2em;
            outline: none;
            border: none;
            background: transparent;
            padding: 0;
            font-size: inherit;
            font-family: inherit;
            color: inherit;
            white-space: normal;
            word-break: break-word;
            overflow-wrap: break-word;
        }

        .tag-input:empty::before {
            content: attr(data-placeholder);
            color: #aaa;
            pointer-events: none;
        }
  }
`;

function TableCell({ 
    isFirstCell,
    isLastCell,
    identifier, 
    rowIndex, 
    colIndex, 
    field, 
    type,
    value, 
    focused,
    editing
 }) {
    const [editValue, setEditValue] = useState(type === 'multiple' ? (Array.isArray(value) ? value : []) : value);
    const didMount = useRef(false);
    const element = this;

    useEffect(() => {
        if (didMount.current) {
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
                setTimeout(() => {
                    contentEditableDiv.focus();
                    const range = document.createRange();
                    range.selectNodeContents(contentEditableDiv);
                    range.collapse(false);
                    const sel = window.getSelection();
                    sel.removeAllRanges();
                    sel.addRange(range);
                }, 0);
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

    function dispatchFocusStop() {
        element.dispatchEvent(new CustomEvent('focus-stop', {
            detail: { row: rowIndex, col: colIndex },
            bubbles: true,
            composed: true
        }));
    }

    function dispatchEditStart() {
        element.dispatchEvent(new CustomEvent('edit-start', {
            detail: { row: rowIndex, col: colIndex, value },
            bubbles: true,
            composed: true
        }));
    }

    function dispatchEditStop() {
        element.dispatchEvent(new CustomEvent('edit-stop', {
            detail: { row: rowIndex, col: colIndex, identifier, value: editValue },
            bubbles: true,
            composed: true
        }));
    }

    function dispatchOnMove(direction) {
        element.dispatchEvent(new CustomEvent('edit-stop', {
            detail: { row: rowIndex, col: colIndex, identifier, value: editValue },
            bubbles: true,
            composed: true
        }));
        element.dispatchEvent(new CustomEvent('on-move', {
            detail: { row: rowIndex, col: colIndex, identifier, direction },
            bubbles: true,
            composed: true
        }));
    }

    function handleKeyDown(e) {
        console.log("Cell pressed", e.key);
        switch (e.key) {
            case KEYCODES.TAB:
                dispatchEditStop();

                if (isFirstCell && e.shiftKey ||
                    isLastCell && !e.shiftKey
                ) {
                    dispatchFocusStop();
                    dispatchEditStop();
                    return; // allow default tab behavior to move focus out of table
                }

                e.preventDefault();
                if (e.shiftKey) {
                    dispatchOnMove('left');
                } else {
                    dispatchOnMove('right');
                }
                return;
            case KEYCODES.ESCAPE:
                if (editing) {
                    setEditValue(value);
                    dispatchEditStop();
                } else if (focused) {
                    dispatchFocusStop();
                }
                return
            case KEYCODES.ENTER:
                if (editing) {
                    dispatchEditStop();
                } else {
                    dispatchEditStart();
                }
                return;
            case KEYCODES.BACKSPACE:
                if (!editing) return;

                if (type != 'multiple') return;

                if (Array.isArray(editValue) && editValue.length > 0) {
                    setEditValue(editValue.slice(0, -1));
                }
            case KEYCODES.RIGHT_ARROW:
                if (editing) return;
                e.preventDefault(); 
                dispatchOnMove('right');
                return;
            case KEYCODES.LEFT_ARROW:
                if (editing) return;
                e.preventDefault();
                dispatchOnMove('left');
                return;
            case KEYCODES.UP_ARROW:
                if (editing) return;
                e.preventDefault();
                dispatchOnMove('up');
                return;
            case KEYCODES.DOWN_ARROW:
                if (editing) return;
                e.preventDefault();
                dispatchOnMove('down');
                return;
            default:
                if (editing) {
                    e.stopPropagation();
                }
                return;
        }
    }


    const addItem = val => setEditValue([...editValue, val]);
    const removeItem = i => setEditValue(editValue.filter((_, idx) => idx !== i));
    
    function renderListCell() {
        const editList = Array.isArray(editValue) ? editValue : [];

        return html`
            <div class="tag-list ${editing ? 'editing' : ''}">
                ${editList.map((item, i) => editing
                    ? html`
                        <button type="button" @click=${() => removeItem(i)}>
                            ${item} ×
                        </button>`
                    : html`
                        <a href="${item}" target="_blank" rel="noopener noreferrer" class="tag-link" tabIndex="-1">
                            ${item}
                        </a>`
                )}
                ${editing ? html`
                    <span
                        class="tag-input"
                        contenteditable="true"
                        data-placeholder="Add…"
                        ${ref(el => { if (el && !el.dataset.initialized) { el.innerText = ''; el.dataset.initialized = 'true'; } })}
                        @keydown=${e => {
                            if (e.key === 'Enter') {
                                e.preventDefault();
                                e.stopPropagation();
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

    function renderImageCell() {
        return html`
            <div style="width: 100%; height: 100%; display: flex; align-items: center; justify-content: center; padding: 0.25rem; box-sizing: border-box;">
                ${value 
                    ? html`<img src="${value}" alt="Profile image" style="
                        width: min(100%, 100cqh, 4rem);
                        height: min(100%, 100cqh, 4rem);
                        border-radius: 50%;
                        object-fit: cover;
                        object-position: center;
                        display: block;
                        flex-shrink: 0;
                      " />`
                    : html`<div style="
                        width: min(100%, 100cqh, 4rem);
                        height: min(100%, 100cqh, 4rem);
                        border-radius: 50%;
                        background: #e0e0e0;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        flex-shrink: 0;
                        font-size: 0.7rem;
                        color: #aaa;
                      ">?</div>`
                }
            </div>
        `;
}

    function renderCell() {
        switch (type) {
            case 'multiple':
                return renderListCell();
            case 'image':
                return renderImageCell();
            default:
                return renderSingleCell();
        }
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
            ${renderCell()}
        </div>
    `;
}

customElements.define('civ-table-cell', component(TableCell, { observedAttributes: ['identifier', 'rowIndex', 'colIndex', 'field', 'value'], useShadowDOM: false }));