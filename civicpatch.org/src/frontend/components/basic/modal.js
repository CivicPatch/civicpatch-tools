import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

// Opened via showModal(), not the `open` attribute: the attribute form is not
// modal — no ::backdrop, no focus trap, no Escape, and nothing "outside" to click.
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

  // The parent owns `open`; closing tells the parent and the effect does the DOM.
  function handleClose(e) {
    modalProps.onClose && modalProps.onClose(e);
    if (dialogEl) {
      dialogEl.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
    }
  }

  useEffect(() => {
    if (!dialogEl) return;
    // showModal() throws if already open.
    if (open && !dialogEl.open) dialogEl.showModal();
    else if (!open && dialogEl.open) dialogEl.close();
  }, [open]);

  // Escape arrives as `cancel`; prevent the default close so the parent stays the
  // single source of truth for `open`.
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
