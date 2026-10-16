// What the Jurisdiction details editor sends as a pull request, and which of it an edit changed.
// Pure. The government form is not here: it saves on its own, at once.

export interface JurisdictionFields {
  url: string;
}

// Only the fields whose value differs, as the pull request body sends them. An emptied url is
// sent: it clears the website.
export function changedFields(
  saved: JurisdictionFields,
  draft: JurisdictionFields,
): Partial<JurisdictionFields> {
  const changes: Partial<JurisdictionFields> = {};
  if (draft.url !== saved.url) changes.url = draft.url;
  return changes;
}
