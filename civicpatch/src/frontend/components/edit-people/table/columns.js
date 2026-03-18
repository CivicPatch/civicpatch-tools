import { html } from "lit-html";
import { divisionOcdidToFriendly } from "../../../pages/jobs-page/ocdid-utils"

const customCss = (person, field) => {
    if (person._deleted) {
      return "opacity: 0.5; text-decoration: line-through; background-color: var(--pico-del-background);";
    } else if (person._changes?.includes(field)) {
      return "background-color: var(--pico-ins-background);";
    }
    return "";
}
export const getColumns = (openProfileModal) => {
    return [
        {
          field: "_isNew",
          editable: false,
          label: "New",
        },
        {
          field: "_selected",
          editable: true,
          type: "checkbox",
        },
        {
          type: "drag-row",
          editable: false,
          renderCell: (_person) => html`
            <span class="drag-handle" title="Drag to reorder">
              <i class="fas fa-grip-vertical"></i>
            </span>
          `, 
        },
        {
          field: "cdn_image",
          label: "Image",
          editable: false,
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
        },
        {
          field: "phones",
          label: "Phones",
          editable: true,
          format: "phone",
          type: "multiple",
          customCss: customCss,
        },
        {
          field: "emails",
          label: "Emails",
          editable: true,
          format: "email",
          type: "multiple",
          customCss: customCss,
        },
        {
          field: "urls",
          label: "URLs",
          editable: true,
          type: "multiple",
          customCss: customCss,
          renderValue: (url, index) => html`<a href="${url}" target="_blank" rel="noopener noreferrer" class="tag-link" tabindex="-1">[${index}]</a>`,
        },
        {
          field: "start_date",
          label: "Start Date",
          editable: true,
          type: "date",
          customCss: customCss,
        },
        {
          field: "end_date",
          label: "End Date",
          editable: true,
          type: "date",
          customCss: customCss,
        },
        {
          field: "office.name",
          label: "Office Name",
          editable: true,
          type: "single",
          customCss: customCss,
        },
        {
          field: "office.division_ocdid",
          label: "Division",
          editable: true,
          type: "single",
          customCss: customCss,
        },
        {
          field: "source_urls",
          label: "Source URLs",
          editable: true,
          type: "multiple",
          customCss: customCss,
          renderValue: (url, index) => html`<a href="${url}" target="_blank" rel="noopener noreferrer" class="tag-link" tabindex="-1">[${index}]</a>`,
        },
        //{
        //  field: "id",
        //  label: "ID",
        //  editable: false,
        //}
      ]
}