import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

// The shared modal shell.
//
// Openness is driven imperatively through showModal()/close() rather than by the
// `open` attribute. That distinction is the whole behaviour of this component: a
// dialog with the attribute set is NOT modal — it stays in normal flow, gets no
// ::backdrop, does not trap focus, does not make the page behind inert, and the
// browser gives it no Escape handling. Every one of those was reported
// separately as a bug before this was switched over.
//
// It also makes click-outside-to-close cheap: a modal dialog fills the viewport,
// so a click that lands on the dialog itself (rather than the <article> inside
// it) is by definition outside the panel. No document-level listener, no
// bounding-box maths.
function Modal({ title = "", content = null, footer = null, modalProps = {} }) {
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

  // The parent owns `open`, so closing means telling the parent; the effect below
  // then does the DOM work.
  function handleClose(e) {
    modalProps.onClose && modalProps.onClose(e);
    if (dialogEl) {
      dialogEl.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
    }
  }

  useEffect(() => {
    if (!dialogEl) return;
    // showModal() throws if the dialog is already open, and close() on a closed
    // dialog is a no-op that still fires an event — so both are guarded.
    if (open && !dialogEl.open) dialogEl.showModal();
    else if (!open && dialogEl.open) dialogEl.close();
  }, [open]);

  // Escape reaches us as `cancel`. Prevent the default close so the parent stays
  // the single source of truth for `open` — otherwise the DOM closes while the
  // parent still thinks the modal is up, and the next open() is a no-op.
  const onCancel = (e) => {
    e.preventDefault();
    handleClose(e);
  };

  const backdropClick = (e) => {
    if (!modalProps.closeOnBackdropClick && modalProps.closeOnBackdropClick !== undefined) return;
    if (e.target && e.target.tagName && e.target.tagName.toLowerCase() === "dialog") {
      handleClose(e);
    }
  };

  return html`
    <dialog
      aria-label=${modalProps.ariaLabel || title || "Modal"}
      @click=${backdropClick}
      @cancel=${onCancel}
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

        <section>${content}</section>

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

customElements.define("civ-modal", component(Modal, { useShadowDOM: false }));
