import { html, component, useState, useLayoutEffect } from 'haunted';
import { css } from 'lit';
import "./cell"

const styles = css`
  :host {
    color: blue;
  }
  td {
    padding: 0;
    border: none;
    height: 100%;
    width: 1px; /* allow table layout to control width */
  }
  civ-table-cell {
    display: block;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
  }
`;

// See: https://www.w3.org/WAI/ARIA/apg/patterns/grid/examples/data-grids/
// See: https://www.w3.org/WAI/ARIA/apg/patterns/grid/examples/data-grids/#kbd_label
const KEYCODES = {
  TAB: 'Tab',
  RETURN: 'Return',
  ESCAPE: 'Escape',
  SPACE: 'Space',
  RIGHT_ARROW: 'ArrowRight',
  LEFT_ARROW: 'ArrowLeft',
  UP_ARROW: 'ArrowUp',
  DOWN_ARROW: 'ArrowDown',
  ENTER: 'Enter',
  BACKSPACE: 'Backspace',

  // Unable to test; don't have these on my keyboard
  //PAGE_UP: 'PageUp',
  //PAGE_DOWN: 'PageDown',
  //END: 'End',
  //HOME: 'Home',
  //CONTROL_HOME: 'Control+Home',
  //CONTROL_END: 'Control+End',
}

function BasicTable(props) {
  const [focusedCell, setFocusedCell] = useState({ row: null, col: null });
  const [editingCell, setEditingCell] = useState({ row: null, col: null });

  function handleCellFocus(rowIndex, colIndex) {
    setFocusedCell({ row: rowIndex, col: colIndex });
  }

  function handleCellBlur(e) {
    if (e.currentTarget.contains(e.relatedTarget)) {
      // Focus is still within the same cell, do not blur
      return;
    }
    setFocusedCell({ row: null, col: null });
  }

  function handleDataChange(event) {
    console.log("Data changed", event.detail);
  }

  function handleOnMove(event) {
    const { row, col, direction } = event.detail;
    let nextRow = row;
    let nextCol = col;
    if (direction === 'right') {
      nextCol = Math.min(props.columns.length - 1, col + 1);
    } else if (direction === 'left') {
      nextCol = Math.max(0, col - 1);
    } else if (direction === 'up') {
      nextRow = Math.max(0, row - 1);
    } else if (direction === 'down') {
      nextRow = Math.min(props.data.length - 1, row + 1);
    }
    setFocusedCell({ row: nextRow, col: nextCol });
  }

  function handleEditStart(event) {
    console.log("Edit started", event.detail);
    const { row, col, value } = event.detail;
    setEditingCell({ row, col });
  }

  function handleEditStop(event) {
    setEditingCell({ row: null, col: null });
    // ** actually change the data here **
  }

  function handleCellClick(rowIndex, colIndex) {
    setFocusedCell({ row: rowIndex, col: colIndex });
    setEditingCell({ row: rowIndex, col: colIndex });
  }

  return html`
    <style>${styles}</style>
    <table class="striped" role="grid">
      <thead>
        <tr>
          ${props.columns.map((col, colIndex) => html`
            <th tabindex="-1"
                @focus=${() => handleCellFocus(-1, colIndex)}
                @blur=${handleCellBlur}
            >${col.label}</th>
          `)}
        </tr>
      </thead>
      <tbody>
        ${props.data.map((row, rowIndex) => html`
          <tr>
            ${props.columns.map((col, colIndex) => {
            const value = row[col.field];
            const cellIsFocused = focusedCell.row === rowIndex && focusedCell.col === colIndex;
            return html`
              <td style="padding: 0">
                <civ-table-cell
                  .identifier=${props.identifier}
                  .rowIndex=${rowIndex}
                  .colIndex=${colIndex}
                  .field=${col.field}
                  .value=${value}
                  @data-change=${handleDataChange}
                  @edit-start=${handleEditStart}
                  @edit-stop=${handleEditStop}
                  @on-move=${handleOnMove}
                  @click=${() => handleCellClick(rowIndex, colIndex)}
                  .focused=${cellIsFocused}
                  .editing=${editingCell.row === rowIndex && editingCell.col === colIndex}
                ></civ-table-cell>
              </td>
  `;
  })}
          </tr>
        `)}
      </tbody>
    </table>
    <p>Focused: ${focusedCell.row}, ${focusedCell.col}</p>
    <p>Editing: ${editingCell.row}, ${editingCell.col}</p>
  `;
}

customElements.define('civ-table', component(BasicTable, { observedAttributes: ['columns', 'data', 'identifier'], useShadowDOM: false }));