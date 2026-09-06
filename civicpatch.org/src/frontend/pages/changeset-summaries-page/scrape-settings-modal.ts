import "../../components/basic/modal.js";
import { component, useState } from "haunted";
import { html } from "lit-html";

import { saveCadence, saveCaps } from "../../api.js";
import { inputValue } from "../../components/fields/field-controls.js";
import { hostDispatch } from "../../utils/host-dispatch.js";
import { estimateMonthlyCost, type StateScrapePanel } from "./scrape-settings.js";
import { formatUsd } from "./spend.js";

export const SAVED_EVENT = "settings-saved";
export const CANCEL_EVENT = "cancel";

type Host = HTMLElement & { panel: StateScrapePanel };

// Blank means "no cap"; "0" means spend nothing. The two must not collapse into each other.
const toDecimal = (raw: string): string | null => (raw.trim() === "" ? null : raw.trim());
const toInt = (raw: string): number | null => (raw.trim() === "" ? null : Number(raw));

function ScrapeSettingsModal(host: Host) {
  const panel = host.panel;
  const [cadenceDays, setCadenceDays] = useState(String(panel.cadence_days ?? ""));
  const [anchor, setAnchor] = useState(panel.cadence_anchor ?? "");
  const [runCap, setRunCap] = useState(panel.pipeline_run_cap_usd ?? "");
  const [monthlyCap, setMonthlyCap] = useState(panel.monthly_cap_usd ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCancel = () => hostDispatch(host, CANCEL_EVENT);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await saveCadence(panel.state, toInt(cadenceDays), toDecimal(anchor));
      await saveCaps(panel.state, toDecimal(runCap), toDecimal(monthlyCap));
      hostDispatch(host, SAVED_EVENT);
    } catch (cause) {
      setError(String(cause));
      setSaving(false);
    }
  };

  const estimate = estimateMonthlyCost(
    toInt(cadenceDays),
    panel.candidates_due,
    toDecimal(runCap),
    toDecimal(monthlyCap),
  );

  const fields = html`
    <div class="cs-settings-form">
      <label class="cs-settings-form__field">
        <span>Cadence</span>
        <span class="cs-settings-form__row">
          every
          <input
            type="number"
            min="1"
            placeholder="manual"
            .value=${cadenceDays}
            @input=${(e: Event) => setCadenceDays(inputValue(e))}
          />
          days, landing on
          <input
            type="date"
            .value=${anchor}
            @input=${(e: Event) => setAnchor(inputValue(e))}
          />
        </span>
      </label>
      <p class="cs-settings-form__hint">
        Leave the cadence blank for manual — no schedule, and this state's candidates never
        drain on their own. The date picks which day the cadence lands on, not the day it
        starts: Sep 1 at 30 days gives Sep 1, Oct 1, Nov 1 — and Aug 2 before that.
      </p>

            <label class="cs-settings-form__field">
              <span>Per-run cap</span>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="inherit $0.05"
                .value=${runCap}
                @input=${(e: Event) => setRunCap(inputValue(e))}
              />
            </label>
            <label class="cs-settings-form__field">
              <span>Monthly cap</span>
              <input
                type="number"
                min="0"
                step="0.01"
                placeholder="no cap"
                .value=${monthlyCap}
                @input=${(e: Event) => setMonthlyCap(inputValue(e))}
              />
            </label>
            <p class="cs-settings-form__hint">
              Blank means no cap. <strong>0 means spend nothing</strong>, which stops the state
              rather than leaving it unlimited.
            </p>


      ${estimate
        ? html`<p class="cs-settings-form__estimate">
            About ${formatUsd(estimate.monthly_usd)} a month — ${estimate.passes_per_month}
            ${estimate.passes_per_month === 1 ? "pass" : "passes"} over
            ${panel.candidates_due} due, at ${formatUsd(estimate.per_run_usd)} each.
            ${estimate.over_cap
              ? html`<strong>Over the ${formatUsd(panel.monthly_cap_usd ?? "0")} cap</strong> —
                  the state will stop partway through a pass.`
              : ""}
          </p>`
        : ""}
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
      .title=${`${panel.state.toUpperCase()} scrape settings`}
      .content=${fields}
      .footer=${footer}
      .modalProps=${{ open: true, onClose: handleCancel }}
    ></civ-modal>
  `;
}

customElements.define(
  "civ-scrape-settings-modal",
  component(ScrapeSettingsModal as any, { useShadowDOM: false }),
);
