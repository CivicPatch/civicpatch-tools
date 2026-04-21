import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

function Modal({
  title = "",
  content = null,
  footer = null,
  modalProps = {},
}) {
  const [open, setOpen] = useState(Boolean(modalProps.open));
  useEffect(() => {
    setOpen(Boolean(modalProps.open));
  }, [modalProps.open]);

  let dialogEl = null;
  const setDialogRef = (el) => {
    dialogEl = el;
    if (!modalProps.modalRef) return;
    if (typeof modalProps.modalRef === "function") modalProps.modalRef(el);
    else if (typeof modalProps.modalRef === "object") modalProps.modalRef.value = el;
  };

  // Helper to close and emit event
  function handleClose(e) {
    modalProps.onClose && modalProps.onClose(e);
    // Emit a DOM event for parent listeners
    if (dialogEl) {
      dialogEl.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
    }
  }

  const onKey = (e) => {
    if (e.key === "Escape") {
      handleClose(e);
    }
  };

  useEffect(() => {
    if (open && dialogEl && typeof dialogEl.focus === "function") {
      dialogEl.focus();
    }
  }, [open]);

  const backdropClick = (e) => {
    if (!modalProps.closeOnBackdropClick && modalProps.closeOnBackdropClick !== undefined) return;
    if (e.target && e.target.tagName && e.target.tagName.toLowerCase() === "dialog") {
      handleClose(e);
    }
  };

  return html`
    <dialog
      ?open=${open}
      tabindex="-1"
      aria-label=${modalProps.ariaLabel || title || "Modal"}
      @click=${backdropClick}
      @keydown=${onKey}
      ${ref(setDialogRef)}
    >
      <article @click=${(e) => e.stopPropagation()}>
        ${title
          ? html`
              <header>
                <h2>${title}</h2>
              </header>
            `
          : null}

        <section>
          ${content}
        </section>

        ${footer
          ? html` <footer>${footer}</footer> `
          : html`
              <footer>
                <button @click=${handleClose} class="secondary">Close</button>
              </footer>
            `}
      </article>
    </dialog>
  `;
}

customElements.define(
  "civ-modal",
  component(Modal, { useShadowDOM: false }),
);
