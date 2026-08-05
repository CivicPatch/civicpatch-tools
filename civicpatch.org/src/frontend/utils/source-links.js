// Named browser targets, so repeat clicks reuse one window per kind rather than
// spawning a tab per surface. Sources and a person's own links stay separate.
// Links using these must not set rel="noopener"/"noreferrer" — either makes the
// browser ignore the name and open a fresh tab every click.
export const SOURCE_LINK_TARGET = "civicpatch-source";
export const PERSON_LINK_TARGET = "civicpatch-person-link";
