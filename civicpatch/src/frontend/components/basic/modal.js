import { component, useState, useEffect } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

function Modal({
  title = "",
  content = null, // a lit-html TemplateResult or null
  footer = null, // a lit-html TemplateResult or null
  modalProps = {}, // { open, onClose, modalRef, closeOnBackdropClick = true, ariaLabel }
}) {
  const [open, setOpen] = useState(Boolean(modalProps.open));
  useEffect(() => {
    setOpen(Boolean(modalProps.open));
  }, [modalProps.open]);

  let dialogEl = null;
  const setDialogRef = (el) => {
    dialogEl = el;
    // propagate to any ref passed in modalProps (supports callback or object ref)
    if (!modalProps.modalRef) return;
    if (typeof modalProps.modalRef === "function") modalProps.modalRef(el);
    else if (typeof modalProps.modalRef === "object") modalProps.modalRef.value = el;
  };

  const onKey = (e) => {
    if (e.key === "Escape") {
      modalProps.onClose && modalProps.onClose();
    }
  };

  useEffect(() => {
    // focus the dialog so it receives key events when opened
    if (open && dialogEl && typeof dialogEl.focus === "function") {
      dialogEl.focus();
    }
  }, [open]);

  const backdropClick = (e) => {
    if (!modalProps.closeOnBackdropClick && modalProps.closeOnBackdropClick !== undefined) return;
    // click on dialog (child) shouldn't close; click on backdrop (dialog element) should
    if (e.target && e.target.tagName && e.target.tagName.toLowerCase() === "dialog") {
      modalProps.onClose && modalProps.onClose();
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
                <button @click=${modalProps.onClose} class="secondary">Close</button>
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
