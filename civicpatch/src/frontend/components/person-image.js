import { component, useState } from "haunted";
import { html } from "lit-html";

function PersonImage({ person, onClick }) {
  const [imgError, setImgError] = useState(false);

  let initials = "?";
  if (person?.name) {
    const parts = person.name.trim().split(/\s+/);
    initials = parts
      .slice(0, 2)
      .map((p) => p[0].toUpperCase())
      .join("");
  }

  const value = person?.cdn_image;
  const showInitials = !value || imgError;

  const avatar = showInitials
    ? html`<div
        style="
        width: 2rem; height: 2rem; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 0.7rem; font-weight: 600;
        background: var(--pico-muted-background);
        color: var(--pico-muted-color);
      "
      >
        ${initials}
      </div>`
    : html`<img
        src="${value}"
        alt="Profile image"
        style="
        width: 2rem; height: 2rem; border-radius: 50%;
        object-fit: cover; object-position: center;
        display: block; flex-shrink: 0;
      "
        @error=${() => setImgError(true)}
      />`;

  if (!onClick) {
    return avatar;
  }

  return html`
    <button
      type="button"
      style="all: unset; cursor: pointer; display: flex; align-items: center; justify-content: center;"
      @click=${() => onClick(person)}
      title="Edit profile"
    >
      ${avatar}
    </button>
  `;
}

customElements.define(
  "person-image",
  component(PersonImage, { useShadowDOM: false }),
);
