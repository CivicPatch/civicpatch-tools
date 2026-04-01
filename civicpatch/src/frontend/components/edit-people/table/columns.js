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
export const getColumns = (openProfileModal, sourceUrlMap = new Map()) => {
    return [
        {
          type: "drag-row",
          editable: false,
          colClass: "col-shrink col-icon",
          renderCell: (_person) => html`
            <span class="drag-handle" title="Drag to reorder">
              <i class="fas fa-grip-vertical"></i>
            </span>
          `,
        },
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
          editable: true,
          type: "single",
          customCss: customCss,
          colClass: "col-name col-shrink",
        },
        {
          field: "phones",
          label: "Phones",
          editable: true,
          format: "phone",
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink col-phone",
        },
        {
          field: "emails",
          label: "Emails",
          editable: true,
          format: "email",
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink col-email",
        },
        {
          field: "urls",
          label: "URLs",
          editable: true,
          type: "multiple",
          customCss: customCss,
          colClass: "col-shrink",
          renderValue: (url, index) => html`<a href="${url}" target="_blank" rel="noopener noreferrer" class="tag-link" tabindex="-1">[${index}]</a>`,
        },
        {
          field: "start_date",
          label: "Start Date",
          editable: true,
          type: "date",
          customCss: customCss,
          colClass: "col-shrink",
        },
        {
          field: "end_date",
          label: "End Date",
          editable: true,
          type: "date",
          customCss: customCss,
          colClass: "col-shrink",
        },
        {
          field: "office.name",
          label: "Office Name",
          editable: true,
          type: "single",
          customCss: customCss,
          colClass: "col-shrink col-office-name",
        },
        {
          field: "office.division_ocdid",
          label: "Division",
          editable: true,
          type: "single",
          customCss: customCss,
          colClass: "col-shrink col-division",
          renderValue: (value) => value ? divisionOcdidToFriendly(value) : "",
        },
        {
          field: "source_urls",
          label: "Source URLs",
          editable: true,
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
        //{
        //  field: "id",
        //  label: "ID",
        //  editable: false,
        //}
      ]
}