// Pure letter-assignment for the keyboard-shortcut nav: each item gets the first
// unused letter that actually appears in its own label, so the binding stays
// mnemonic without hand-picking one per item; falls back to any free letter once
// every letter in the label is already taken.
const ALPHABET = "abcdefghijklmnopqrstuvwxyz".split("");

export function assignLetters(items) {
  const used = new Set();
  return items.map((item) => {
    const inLabel = item.label.toLowerCase().split("").filter((c) => /[a-z]/.test(c));
    const letter = inLabel.find((c) => !used.has(c)) || ALPHABET.find((c) => !used.has(c));
    used.add(letter);
    return { ...item, letter };
  });
}
