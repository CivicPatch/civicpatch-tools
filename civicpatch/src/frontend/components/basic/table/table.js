import { html, component, useState, useLayoutEffect } from 'haunted';
import { css } from 'lit';
import { keyed } from 'lit/directives/keyed.js';
import "./cell"

const styles = css`
  table:focus {
    outline: 2px solid rgb(var(--catppuccin-sapphire));
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
  tr {
    border: 1px solid rgb(var(--catppuccin-crust));
  }
  tr:hover {
    background-color: rgba(var(--catppuccin-teal), 0.1);
  }
  td {
    background-color: inherit; 
  }
  td:focus-within {
    background-color: rgb(var(--catppuccin-base));
    border: 2px solid transparent;
    border-radius: 4px;
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

  function handleDataChange(event) {
    console.log("Data changed", event.detail);
    const { identifier, field, value, row, col } = event.detail;
    const currentlyEditing = editingCell.row === row && editingCell.col === col;
    if (!currentlyEditing) {
      console.warn("Received data change from a cell that is not currently being edited", { row, col });
      return;
    }

    // Data has been submitted from a cell, we should reset edit mode
    setEditingCell({ row: null, col: null });

    // Also, should submit the changes
    // Good time to validate, but tomorrow's me will implement that
  }

  function handleOnMove({row, col, direction}) {
    console.log("move", {row, col, direction})  
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

  function handleCellClick(rowIndex, colIndex) {
    setFocusedCell({ row: rowIndex, col: colIndex });
    setEditingCell({ row: rowIndex, col: colIndex });
  }

  function getNestedValue(obj, path) {
    return path.split('.').reduce((acc, key) => acc?.[key], obj);
  }

  function handleTableKeyDown(e) {
    // If no cell is focused, go to the first cell/last cell on any arrow key press
    const tableIsFocused = document.activeElement === e.currentTarget;

    if (tableIsFocused) {
      setFocusedCell({ row: null, col: null });

      if (['ArrowRight', 'ArrowDown'].includes(e.key)) {
        setFocusedCell({ row: 0, col: 0 });
        e.preventDefault();
      } else if (['ArrowLeft', 'ArrowUp'].includes(e.key)) {
        setFocusedCell({ row: props.data.length - 1, col: props.columns.length - 1 });
        e.preventDefault();
      }
    } else if (e.key === KEYCODES.ESCAPE) {
      setFocusedCell({ row: null, col: null });
      setEditingCell({ row: null, col: null });
    }
  }

  const isFirstCell = (rowIndex, colIndex) => {
    return rowIndex === 0 && colIndex === 0;
  }

  const isLastCell = (rowIndex, colIndex) => {
    return rowIndex === props.data.length - 1 && colIndex === props.columns.length - 1;
  }

  function handleCellKeyDown(e, { row, col, type, editable }) {
    const editing = editingCell.row === row && editingCell.col === col;
    const focused = focusedCell.row === row && focusedCell.col === col;

    switch (e.key) {
       case KEYCODES.TAB:
           if (isFirstCell(row, col) && e.shiftKey ||
               isLastCell(row, col) && !e.shiftKey
           ) {
             setFocusedCell({ row: null, col: null });
             setEditingCell({ row: null, col: null });
             return; // allow default tab behavior to move focus out of table
           }

           e.preventDefault();
           if (e.shiftKey) {
             handleOnMove({ row, col, direction: 'left' });
           } else {
             handleOnMove({ row, col, direction: 'right' });
           }
           return;
       case KEYCODES.ESCAPE:
           if (editing) {
             setEditingCell({ row: null, col: null });
             e.stopPropagation();
           } else if (focused) {
             setFocusedCell({ row: null, col: null });
             e.stopPropagation();
           }
           return;
       case KEYCODES.ENTER:
           if (editing) {
             setEditingCell({ row: null, col: null });
           } else {
             if (!editable) return;
             setEditingCell({ row, col });
           }
           return;
       case KEYCODES.RIGHT_ARROW:
           if (editing) return;
           e.preventDefault(); 
           handleOnMove({ row, col, direction: 'right' });
           return;
       case KEYCODES.LEFT_ARROW:
           if (editing) return;
           e.preventDefault();
           handleOnMove({ row, col, direction: 'left' });
           return;
       case KEYCODES.UP_ARROW:
           if (editing) return;
           e.preventDefault();
           handleOnMove({ row, col, direction: 'up' });
           return;
       case KEYCODES.DOWN_ARROW:
           if (editing) return;
           e.preventDefault();
           handleOnMove({ row, col, direction: 'down' });
           return;
       default:
           if (editing) {
               e.stopPropagation();
           }
           return;
      }
    }

  return html`
    <style>${styles}</style>
    <table 
      role="grid" 
      style="height: 100%" 
      tabindex="0"
      @keydown=${handleTableKeyDown}
    >
      <thead>
        <tr>
          ${props.columns.map((col, colIndex) => html`
            <th>${col.label}</th>
          `)}
        </tr>
      </thead>
      <tbody style="height: 100%">
        ${props.data.map((row, rowIndex) => html`
          <tr>
            ${props.columns.map((col, colIndex) => {
            const identifierValue = row[props.identifier];
            const mapKey = `${identifierValue}-${col.field}`;
            const value = getNestedValue(row, col.field);
            const cellIsFocused = focusedCell.row === rowIndex && focusedCell.col === colIndex;
            const cellIsEditing = editingCell.row === rowIndex && editingCell.col === colIndex;
            return keyed(mapKey, html`
              <td style="padding: 0;" 
                @keydown=${(e) => handleCellKeyDown(e, { row: rowIndex, col: colIndex, editable: col.editable })}
                @click=${() => handleCellClick(rowIndex, colIndex)}
              >
                <civ-table-cell
                  @data-change=${handleDataChange}
                  .identifier=${props.identifier}
                  .rowIndex=${rowIndex}
                  .colIndex=${colIndex}
                  .type=${col.type}
                  .field=${col.field}
                  .format=${col.format}
                  .value=${value}
                  .focused=${cellIsFocused}
                  .editing=${cellIsEditing}
                ></civ-table-cell>
              </td>
          `)
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