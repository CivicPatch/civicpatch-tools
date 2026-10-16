import { component, useState, useEffect, useRef } from "haunted";
import { html } from "lit-html";
import { ref } from "lit-html/directives/ref.js";

// `modalProps.size`. Unset: content height, for a confirm or a short form. Wide: a fixed size
// whose body scrolls, for a list or a long form.
export const MODAL_SIZE_WIDE = "wide";

// Opened via showModal(), not the `open` attribute: the attribute form is not
// modal — no ::backdrop, no focus trap, no Escape, and nothing "outside" to click.
function Modal({ title = "", content = null, footer = null, modalProps = {} }) {
  const [open, setOpen] = useState(Boolean(modalProps.open));
  useEffect(() => {
    setOpen(Boolean(modalProps.open));
  }, [modalProps.open]);

  // A ref, not a local: a plain `let` is re-created every render, so an effect can
  // close over a different binding than the one the ref callback wrote to. When the
  // caller opens the modal as part of a re-render (adding a person, say), the effect
  // then sees null, bails, and never fires again because `open` did not change.
  const dialogRef = useRef(null);
  const setDialogRef = (el) => {
    dialogRef.current = el;
    if (!modalProps.modalRef) return;
    if (typeof modalProps.modalRef === "function") modalProps.modalRef(el);
    else if (typeof modalProps.modalRef === "object") modalProps.modalRef.value = el;
  };

  // The parent owns `open`; closing tells the parent and the effect does the DOM.
  function handleClose(e) {
    modalProps.onClose && modalProps.onClose(e);
    const dialogEl = dialogRef.current;
    if (dialogEl) {
      dialogEl.dispatchEvent(new CustomEvent("close", { bubbles: true, composed: true }));
    }
  }

  useEffect(() => {
    const dialogEl = dialogRef.current;
    if (!dialogEl) return;
    // showModal() throws if already open.
    if (open && !dialogEl.open) dialogEl.showModal();
    else if (!open && dialogEl.open) dialogEl.close();
  }, [open]);

  // Escape arrives as `cancel`; prevent the default close so the parent stays the
  // single source of truth for `open`.
  // Escape only: the browser's cancel targets the dialog, while a form inside that emits its
  // own `cancel` event bubbles here too and must not close the modal.
  const onCancel = (e) => {
    if (e.target !== e.currentTarget) return;
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
    <!-- autofocus: opening focuses the dialog, not the body, which drew a keyboard focus ring
         on every mouse-opened modal. Tab still reaches the body and its ring. -->
    <dialog
      autofocus
      class=${modalProps.size === MODAL_SIZE_WIDE ? "modal--wide" : ""}
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

        <!-- tabindex so the scrolling region is keyboard-reachable: arrow keys only
             scroll a focused element, and a bare <section> cannot take focus. -->
        <section tabindex="0">${content}</section>

        ${footer
          ? html` <footer>${footer}</footer> `
          : html`
              <footer>
                <button @click=${handleClose} class="btn btn-sm secondary">Close</button>
              </footer>
            `}
      </article>
    </dialog>
  `;
}

customElements.define("civ-modal", component(Modal, { useShadowDOM: false }));
