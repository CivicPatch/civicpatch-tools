import "../../components/basic/modal.js";
import { component, useState } from "haunted";
import { html } from "lit-html";

import { saveCollectorCaps } from "../../api.js";
import { inputValue } from "../../components/fields/field-controls.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { collectorCapsToSave, collectorLabel, type CollectorPanel } from "./scrape-settings.js";

export const SAVED_EVENT = "settings-saved";
export const CANCEL_EVENT = "cancel";

type Host = HTMLElement & { panel: CollectorPanel };

function CollectorBudgetModal(host: Host) {
  const settings = host.panel.settings;
  const [runCap, setRunCap] = useState(settings.pipeline_run_cap_usd);
  const [monthCap, setMonthCap] = useState(settings.monthly_cap_usd ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);

  const handleSave = async () => {
    const caps = collectorCapsToSave(runCap, monthCap);
    if ("error" in caps) {
      setError(caps.error);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await saveCollectorCaps(settings.kind, caps.run, caps.month);
      hostDispatch(host, SAVED_EVENT);
    } catch (cause) {
      setError(String(cause));
      setSaving(false);
    }
  };

  const fields = html`
    <div class="cs-settings-form">
      <label class="cs-settings-form__field">
        <span class="cs-settings-form__label">Per run</span>
        <span class="cs-settings-form__control">
          $
          <input
            type="number"
            min="0"
            step="0.01"
            required
            .value=${runCap}
            @input=${(e: Event) => setRunCap(inputValue(e))}
          />
        </span>
      </label>
      <label class="cs-settings-form__field">
        <span class="cs-settings-form__label">Monthly cap</span>
        <span class="cs-settings-form__control">
          $
          <input
            type="number"
            min="0"
            step="0.01"
            placeholder="none"
            .value=${monthCap}
            @input=${(e: Event) => setMonthCap(inputValue(e))}
          />
        </span>
      </label>
      <p class="cs-settings-form__hint">
        One jurisdiction's collection stops at the per-run cap. The monthly cap is this collector's
        across every state, apart from the scrape budget.
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
      .title=${`${collectorLabel(settings.kind)} collector budget`}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-collector-budget-modal",
  component(CollectorBudgetModal as any, { useShadowDOM: false }),
);
