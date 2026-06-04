import { html } from "lit-html";
import { divisionOcdidToFriendly } from "../../ocdid-utils"
import { getSourceColorClass } from "../../../utils/source-color-utils.js";

const customCss = (person, field) => {
    if (person._deleted) {
      return "opacity: 0.5; text-decoration: line-through; background-color: var(--pico-del-background);";
    } else if (person._changes?.includes(field)) {
      return "background-color: var(--pico-ins-background);";
    }
    return "";
}
export const getColumns = (openProfileModal, sourceUrlMap = new Map(), { showOtherNames = false, readOnly = false, onEdit = null } = {}) => {
    const editable = !readOnly;
    return [
        {
          type: "drag-row",
          editable: false,
          colClass: "col-shrink col-icon",
          renderCell: (_person) => html`
            <span class="drag-handle" title="Drag to reorder">
              <i class="fa-solid fa-grip-vertical"></i>
            </span>
          `,
        },
        ...(onEdit ? [{
          field: "_edit",
          editable: false,
          colClass: "col-shrink col-icon",
          renderCell: (person) => html`
            <button class="btn-ghost" title="Edit person" @click=${() => onEdit(person)}>
              <i class="fa-solid fa-pen"></i>
            </button>
          `,
        }] : []),
        {
          field: "_selected",
          editable: true,
          type: "checkbox",
          colClass: "col-shrink col-icon",
        },
        {
          field: "cdn_image",
          label: "Image",
          editable: false,
          colClass: "col-shrink col-icon",
          renderCell: (person) => html`
            <person-image .person=${person} .onClick=${openProfileModal}></person-image>
          `
        },
        {
          field: "name",
          label: "Name",
          editable: editable,
          type: "single",
          customCss: customCss,
          colClass: "col-name col-shrink",
        },
        ...(showOtherNames ? [{
          field: "other_names",
          label: "Other Names",
          editable: editable,
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink",
        }] : []),
        {
          field: "phones",
          label: "Phones",
          editable: editable,
          format: "phone",
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink col-phone",
        },
        {
          field: "emails",
          label: "Emails",
          editable: editable,
          format: "email",
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink col-email",
        },
        {
          field: "urls",
          label: "URLs",
          editable: editable,
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink",
          renderValue: (url, index) => html`<a href="${url}" target="_blank" rel="noopener noreferrer" class="tag-link" tabindex="-1">[${index}]</a>`,
        },
        {
          field: "start_date",
          label: "Start Date",
          editable: editable,
          type: "date",
          customCss: customCss,
          colClass: "col-shrink",
        },
        {
          field: "end_date",
          label: "End Date",
          editable: editable,
          type: "date",
          customCss: customCss,
          colClass: "col-shrink",
        },
        {
          field: "office.name",
          label: "Office Name",
          editable: editable,
          type: "single",
          customCss: customCss,
          colClass: "col-shrink col-office-name",
        },
        {
          field: "office.division_ocdid",
          label: "Division",
          editable: editable,
          type: "single",
          customCss: customCss,
          colClass: "col-shrink col-division",
          renderValue: (value) => value ? divisionOcdidToFriendly(value) : "",
        },
        {
          field: "source_urls",
          label: "Source URLs",
          editable: editable,
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink",
          renderValue: (url, index) => {
            const entry = sourceUrlMap.get(url);
            const colorClass = entry ? entry.colorClass : getSourceColorClass(url);
            const label = entry ? entry.number : index + 1;
            return html`<a href="${url}" target="_blank" rel="noopener noreferrer" class="tag-link ${colorClass}" tabindex="-1">[${label}]</a>`;
          },
        },
      ]
}