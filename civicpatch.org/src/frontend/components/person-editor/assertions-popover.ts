import { html, nothing } from "lit-html";
import { component, useEffect, useState } from "haunted";
import "./person-editor.css";
import { type FieldAssertionSummary, type FieldLock } from "./field-provenance.js";

const VISIBLE_MS = 4000;
const FADE_MS = 400;

interface AssertionsPopoverProps {
  lock: FieldLock;
  summary: FieldAssertionSummary | null;
}

function renderChip(kind: "accept" | "reject", value: string | null) {
  if (!value) return nothing;
  return html`<div>
    <span class="person-editor__assertions-chip person-editor__assertions-chip--${kind}">
      <i class="fa-solid fa-${kind === "accept" ? "check" : "xmark"}" aria-hidden="true"></i>
      ${value}
    </span>
  </div>`;
}

// The lock is the trigger for the full accept/reject breakdown; the popover shows briefly
// then fades on its own, unless something reopens it first. State (not a stashed timer id on
// a DOM node) is what a haunted component actually has to work with.
function AssertionsPopover({ lock, summary }: AssertionsPopoverProps) {
  const [open, setOpen] = useState(false);
  const [fading, setFading] = useState(false);

  useEffect(() => {
    if (!open) return;
    const timer = window.setTimeout(() => setFading(true), VISIBLE_MS);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!fading) return;
    const timer = window.setTimeout(() => {
      setOpen(false);
      setFading(false);
    }, FADE_MS);
    return () => window.clearTimeout(timer);
  }, [fading]);

  const toggle = () => {
    setFading(false);
    setOpen((wasOpen) => !wasOpen);
  };

  const title = [
    summary?.accept ? `Accepted: ${summary.accept}` : null,
    summary?.reject ? `Rejected: ${summary.reject}` : null,
    lock.label,
  ]
    .filter(Boolean)
    .join(". ");

  return html`
    <div class="person-editor__assertions">
      <button
        type="button"
        class="person-editor__assertions-toggle"
        title=${title}
        @click=${toggle}
      >
        <i
          class="fa-solid fa-lock person-editor__lock person-editor__lock--${lock.state}"
          aria-hidden="true"
        ></i>
      </button>
      ${open
        ? html`
            <div
              class="person-editor__assertions-list ${fading
                ? "person-editor__assertions-list--fading"
                : ""}"
            >
              ${renderChip("accept", summary?.accept ?? null)}
              ${renderChip("reject", summary?.reject ?? null)}
              <div class="person-editor__assertions-who">${lock.label}</div>
            </div>
          `
        : nothing}
    </div>
  `;
}

customElements.define(
  "civ-assertions-popover",
  component(AssertionsPopover as unknown as () => unknown, { useShadowDOM: false }),
);
