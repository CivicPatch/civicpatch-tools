import { component, useState } from "haunted";
import { html } from "lit-html";

function CivPipelineForm() {
    // const [isLoading, setIsLoading] = useState(false);

    const handleSelectJurisdictionChange = (event) => {
        const { state, jurisdiction } = event.detail;
        console.log("Selected State:", state);
        // TODO: pan the map if state but no jurisdiction
        console.log("Selected Jurisdiction:", jurisdiction);
        // TODO: pan the map & zoom if state and jurisdiction
    }

    //const handleSubmitJurisdiction = (event) => {
    //    const { state, jurisdiction } = event.detail;
    //    console.log("Submitted State:", state);
    //    console.log("Submitted Jurisdiction:", jurisdiction);

    //    const jurisdiction_ocdid_slug = jurisdiction["jurisdiction_ocdid_slug"];
    
    //    setIsLoading(true)

    //    fetch(`/api/crudder/jurisdictions/${jurisdiction_ocdid_slug}/people`)
    //        .then((response) => response.json())
    //        .then((data) => {
    //            console.log("Fetched People Data:", data);
    //        });
    //    
    //    // TODO: then go to a separate page

    //}

    return html`
    <div>
    <civ-select-jurisdiction 
        @select-jurisdiction-change=${handleSelectJurisdictionChange} 
    ></civ-select-jurisdiction>
    </div>`
}

customElements.define(
    "civ-pipeline-form",
    component(CivPipelineForm, { useShadowDOM: false })
)