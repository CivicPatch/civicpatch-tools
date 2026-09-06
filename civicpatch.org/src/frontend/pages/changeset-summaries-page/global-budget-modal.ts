import "../../components/basic/modal.js";
import { component, useState } from "haunted";
import { html } from "lit-html";

import { saveGlobalCap } from "../../api.js";
import { inputValue } from "../../components/fields/field-controls.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { describeStateCaps, type GlobalScrapePanel } from "./scrape-settings.js";

export const SAVED_EVENT = "settings-saved";
export const CANCEL_EVENT = "cancel";

type Host = HTMLElement & { panel: GlobalScrapePanel };

function GlobalBudgetModal(host: Host) {
  const [cap, setCap] = useState(host.panel.monthly_cap_usd ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveGlobalCap(cap.trim() === "" ? null : cap.trim());
      hostDispatch(host, SAVED_EVENT);
    } catch (cause) {
      setError(String(cause));
      setSaving(false);
    }
  };

  const fields = html`
    <div class="cs-settings-form">
      <label class="cs-settings-form__field">
        <span>Monthly cap, all states</span>
        <input
          type="number"
          min="0"
          step="0.01"
          placeholder="no cap"
          .value=${cap}
          @input=${(e: Event) => setCap(inputValue(e))}
        />
      </label>
      <p class="cs-settings-form__hint">
        A shared ceiling, not an allocation: states draw from it first-come, and each state's
        own monthly cap is what stops one state emptying it. ${describeStateCaps(host.panel)} —
        the state caps may add up past this, which is normal.
      </p>
      ${error ? html`<p class="cs-settings-form__error">${error}</p>` : ""}
    </div>
  `;

  const footer = html`
    <button class="btn btn-sm secondary" @click=${handleCancel}>Cancel</button>
    <button class="btn btn-sm" ?disabled=${saving} @click=${handleSave}>
      ${saving ? "Saving…" : "Save"}
    </button>
  `;

  return html`
    <civ-modal
      .title=${"Scrape budget"}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-global-budget-modal",
  component(GlobalBudgetModal as any, { useShadowDOM: false }),
);
