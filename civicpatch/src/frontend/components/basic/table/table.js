import { html, component, useState, useLayoutEffect } from 'haunted';
import { css } from 'lit';
import { keyed } from 'lit/directives/keyed.js';
import { ref, createRef } from 'lit/directives/ref.js';
import { useSortableList } from '../../../hooks/useSortableList.js';
import "./cell"

const styles = css`
  civ-table table {
    border: 2px solid transparent;
    border-radius: var(--pico-border-radius);
  }
  civ-table table:focus {
    outline: none;
    box-shadow: 0 0 0 2px var(--pico-background-color), 0 0 0 4px rgb(var(--catppuccin-sapphire)) !important;
  }

  civ-table tr:last-child {
    border: none;
  }
  civ-table td {
      padding: 0;
      border: none;
      height: 100%;
  }
  civ-table td:focus-within {
    background-color: rgb(var(--catppuccin-base));
  }
  civ-table-cell {
    display: block;
    width: 100%;
    height: 100%;
    box-sizing: border-box;
  }
  civ-table tr {
    border: 1px solid rgb(var(--catppuccin-crust));
    transition: transform 300ms ease, opacity 300ms ease, background-color 150ms ease;
  }
  civ-table tr:focus-within {
    background-color: rgba(var(--catppuccin-teal), 0.1);
  }
  civ-table tr.dragging {
    opacity: 0.3;
  }
  civ-table tr.drop-indicator td div {
    animation: expand 250ms ease-out forwards;
  }
  @keyframes expand {
    from {
      height: 0;
      opacity: 0;
    }
    to {
      height: 8rem;
      opacity: 1;
    }
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
  
  const tableRef = createRef();

  const {
    draggedIndex,
    dragOverIndex,
    handleDragStart,
    handleDragOver,
    handleDrop,
    handleDragEnd,
  } = useSortableList(props.data, props.identifier, (newOrder) => {
    // Dispatch or handle the new order as needed
    tableRef.current.dispatchEvent(new CustomEvent('reorder', {
      detail: { newOrder },
      bubbles: true,
      composed: true
    }));
  });

  function handleDataChange(event, row) {
    const { identifier, field, value } = event.detail;

    const actualField = getResponseField(field);
    const newValue = getResponseValue(row[actualField], field, value);

    // Data has been submitted from a cell, we should reset edit mode
    setEditingCell({ row: null, col: null });

    // Also, should submit the changes
    // Good time to validate, but tomorrow's me will implement that
    console.log("Data change:", identifier, field, value);
    tableRef.current.dispatchEvent(new CustomEvent('data-change', {
      detail: { identifier, field: actualField, value: newValue },
      bubbles: true,
      composed: true
    }));
  }

  function handleOnMove({ row, col, direction, isSelectCell }) {
    let nextRow = row;
    let nextCol = col;

    if (direction === 'right') {
      nextCol = Math.min(props.columns.length, col + 1);
    } else if (direction === 'left') {
      nextCol = Math.max(0, col - 1);
    } else if (direction === 'up') {
      nextRow = Math.max(0, row - 1);
    } else if (direction === 'down') {
      nextRow = Math.min(props.data.length - 1, row + 1);
    }

    setFocusedCell({ row: nextRow, col: nextCol });
    setEditingCell({ row: null, col: null })
  }

  function handleCellClick({ row, col, editable }) {
    setFocusedCell({ row, col });
    if (editable) {
      setEditingCell({ row, col });
    }
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

  function handleCellKeyDown(e, { row, col, type, editable, isSelectCell }) {
    const editing = editingCell.row === row && editingCell.col === col;
    const focused = focusedCell.row === row && focusedCell.col === col;

    switch (e.code) {
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
          handleOnMove({ row, col, direction: 'left', isSelectCell });
        } else {
          handleOnMove({ row, col, direction: 'right', isSelectCell });
        }
        return;
      case KEYCODES.ESCAPE:
        if (editing) {
          setEditingCell({ row: null, col: null });
          e.stopPropagation();
        } else if (focused) {
          setFocusedCell({ row: null, col: null });
          // Focus on table
          tableRef.current.focus();
          e.stopPropagation();
        }
        return;
      case KEYCODES.ENTER:
        if (editing) {
          console.log("Submitting stop edit for cell", { row, col });
          setEditingCell({ row: null, col: null });
        } else {
          if (!editable) return;
          setEditingCell({ row, col });
        }

        return;
      case KEYCODES.SPACE:
        // Focused cell: space should enter edit mode
        // Editing cell: e.preventDefault()
        // If it's a selectCell, do nothing; edit mode should already be active
        if (isSelectCell)  { return; }

        if (editing) return;

        if (focused) {
          if (!editable) return;
          setEditingCell({ row, col });
          e.preventDefault();
        }
        return;
      case KEYCODES.RIGHT_ARROW:
        if (editing && !isSelectCell) return;

        e.preventDefault();
        handleOnMove({ row, col, direction: 'right', isSelectCell });
        return;
      case KEYCODES.LEFT_ARROW:
        if (editing && !isSelectCell) return;

        e.preventDefault();

        handleOnMove({ row, col, direction: 'left', isSelectCell });
        return;
      case KEYCODES.UP_ARROW:
        if (editing && !isSelectCell) return;

        e.preventDefault();
        handleOnMove({ row, col, direction: 'up', isSelectCell });
        return;
      case KEYCODES.DOWN_ARROW:
        if (editing && !isSelectCell) return;
        e.preventDefault();
        handleOnMove({ row, col, direction: 'down', isSelectCell });
        return;
      default:
        if (editing) {
          e.stopPropagation();
        }
        return;
    }
  }

  function renderDropIndicator(colspan, dragOverIndex) {
    return html`
      <tr class="drop-indicator">
        <td 
          colspan=${colspan} 
          style="padding:0;"
          @dragover=${e => handleDragOver(dragOverIndex, e)}
          @drop=${e => handleDrop(dragOverIndex, e)}
          >
          <div style="background:rgba(var(--catppuccin-mauve),0.18); border-radius:var(--pico-border-radius);"></div>
        </td>
      </tr>
    `;
  }

  function renderDataCell(col, colIndex, rowIndex) {
    const row = props.data[rowIndex];
    const identifierValue = row[props.identifier];
    const mapKey = `${identifierValue}-${col.field}`;
    const actualField = getResponseField(col.field);
    const value = actualField ? getNestedValue(row[actualField], col.field) : null;
    const cellIsFocused = focusedCell.row === rowIndex && focusedCell.col === colIndex;
    const cellIsEditing = editingCell.row === rowIndex && editingCell.col === colIndex;
    return keyed(mapKey, html`
      <td style="padding: 0;" 
        data-row=${rowIndex}
        data-col=${colIndex}
        style=${col.customCss ? col.customCss(row, actualField) : ""}
        @keydown=${(e) => handleCellKeyDown(e, { row: rowIndex, col: colIndex, editable: col.editable, isSelectCell: col.type === 'checkbox' })}
        @click=${() => handleCellClick({ row: rowIndex, col: colIndex, editable: col.editable })}
        @dragover=${e => handleDragOver(rowIndex, e)}
        @drop=${e => handleDrop(rowIndex, e)}
      >
        <civ-table-cell
          @cell-change=${(e) => handleDataChange(e, row)}
          @cell-cancel=${handleCellBlur}
          .identifier=${identifierValue}
          .rowIndex=${rowIndex}
          .colIndex=${colIndex}
          .type=${col.type}
          .field=${col.field}
          .format=${col.format}
          .value=${value}
          .focused=${cellIsFocused}
          .editing=${cellIsEditing}
          .customCell=${col.renderCell}
        ></civ-table-cell>
      </td>
    `)
  }

  function handleTableBlur(e) {
    setFocusedCell({ row: null, col: null });
    setEditingCell({ row: null, col: null });
  }

  function handleCellBlur(e) {
    setEditingCell({ row: null, col: null });
  }

  const isRedundantDrop = dragOverIndex === draggedIndex || dragOverIndex === draggedIndex + 1;

  function getResponseField(nestedField) {
    if (!nestedField) return null;

    let parts = nestedField.split('.');
    return parts[0];
  }

  function getNestedValue(maybeObj, nestedField) {
    if (!maybeObj) return null;
    // Nested field is in the format "office.name", we need to drill down into the object to get the value
    // There will either be only 1 level of nesting, or none
    let parts = nestedField.split('.')
    if (parts.length === 1) {
      return maybeObj; // It is not nested, it's just a direct value
    } else if (parts.length === 2) {
      const [_parentKey, childKey] = parts;
      return maybeObj ? maybeObj[childKey] : null; // Drill down into the object to get the nested value
    }
  }

  function getResponseValue(maybeObj, nestedField, newValue) {
    if (!nestedField) return null;

    let parts = nestedField.split('.');
    if (parts.length === 1) {
      return newValue;
    } else if (parts.length === 2) {
      const [_parentKey, childKey] = parts;
      return {
        ...maybeObj,
        [childKey]: newValue
      };
    }
  }

  return html`
    <style>${styles}</style>
    <table 
      role="grid" 
      style="height: 100%" 
      tabindex="0"
      @keydown=${handleTableKeyDown}
      @blur=${handleTableBlur}
      ${ref(el => tableRef.current = el)}
    >
      <thead>
        <tr>
          ${props.columns.map((col, colIndex) => html`
            <th>${col.label}</th>
          `)}
        </tr>
      </thead>
      <tbody style="height: 100%">
        ${[...Array(props.data.length + 1)].map((_, dropIndex) => html`
          ${!isRedundantDrop && dropIndex === dragOverIndex ? renderDropIndicator(props.columns.length, dropIndex) : null}
          ${dropIndex < props.data.length ? html`
            <tr
              draggable="true"
              class=${dropIndex === draggedIndex ? "dragging" : ""}
              @dragstart=${e => handleDragStart(dropIndex, e)}
              @dragend=${handleDragEnd}
            >
              ${props.columns.map((col, colIndex) => {
                return renderDataCell(col, colIndex, dropIndex);
              })}
            </tr>
          ` : null}
        `)}
        <!-- Always-present drop zone for the end of the list -->
        ${dragOverIndex !== props.data.length ? html`
          <tr>
            <td
              colspan=${props.columns.length}
              style="height: 10rem; padding: 0;"
              @dragover=${e => handleDragOver(props.data.length, e)}
              @drop=${e => handleDrop(props.data.length, e)}
            ></td>
          </tr>
        ` : null}
      </tbody>
    </table>
  `;
}


customElements.define('civ-table', component(BasicTable, { observedAttributes: ['columns', 'data', 'identifier'], useShadowDOM: false }));