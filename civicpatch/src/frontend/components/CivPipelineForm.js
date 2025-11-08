import { component } from "haunted";
import { html } from "lit-html";

function CivPipelineForm() {


    const handleSelectJurisdictionChange = (event) => {
        const { state, jurisdiction } = event.detail;
        console.log("Selected State:", state);
        // TODO: pan the map if state but no jurisdiction
        console.log("Selected Jurisdiction:", jurisdiction);
        // TODO: pan the map & zoom if state and jurisdiction
    }

    const handleSubmitJurisdiction = (event) => {
        const { state, jurisdiction } = event.detail;
        console.log("Submitted State:", state);
        console.log("Submitted Jurisdiction:", jurisdiction);
    }

    return html`
    <div>
    <civ-select-jurisdiction 
        @select-jurisdiction-change=${handleSelectJurisdictionChange} 
        @select-jurisdiction-submit=${handleSubmitJurisdiction}></civ-select-jurisdiction>
    </div>`
}

customElements.define(
    "civ-pipeline-form",
    component(CivPipelineForm, { useShadowDOM: false })
)