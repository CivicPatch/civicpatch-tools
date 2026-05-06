import { html, render } from 'lit';

class ZoomImage extends HTMLElement {
  static observedAttributes = ['src', 'alt'];

  connectedCallback() { this._render(); }
  attributeChangedCallback() { if (this.isConnected) this._render(); }

  private _open = () => {
    document.body.style.overflow = 'hidden';
    this.querySelector<HTMLDialogElement>('dialog')!.showModal();
  };

  private _onDialogClick = (e: MouseEvent) => {
    if (e.target === e.currentTarget) (e.currentTarget as HTMLDialogElement).close();
  };

  private _onClose = () => {
    document.body.style.overflow = '';
  };

  private _render() {
    const src = this.getAttribute('src') ?? '';
    const alt = this.getAttribute('alt') ?? '';
    render(html`
      <img class="zoom-image" src=${src} alt=${alt} @click=${this._open}>
      <dialog class="zoom-image-lightbox" aria-label=${alt || 'Image'}
        @click=${this._onDialogClick} @close=${this._onClose}>
        <img src=${src} alt=${alt}>
      </dialog>
    `, this);
  }
}

customElements.define('zoom-image', ZoomImage);
