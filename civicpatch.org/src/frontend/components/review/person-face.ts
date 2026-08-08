// One person as a chip: their photo and their name, nothing else.
//
// Overview uses it for the unchanged roster — present so the list reads complete
// without spending a card each — and the merge picker uses it to offer the other
// people on the card. Both want "a person, compactly, that you can click", so it
// takes a callback rather than either caller's props.

import { html } from "lit-html";
import "./person-face.css";
import "../person-image.js";
import { personOf, type PersonCard } from "../people/person-cards.js";
import { withDisplayImage } from "../fields/field-controls.js";

export function renderPersonFace(
  card: PersonCard,
  onPick: (personId: string) => void,
  size = "1.75rem",
) {
  const record = personOf(card);
  return html`<button class="review-face" @click=${() => onPick(card.personId)}>
    <person-image .person=${withDisplayImage(record)} .size=${size}></person-image>
    <span>${record?.name || "(unnamed)"}</span>
  </button>`;
}
