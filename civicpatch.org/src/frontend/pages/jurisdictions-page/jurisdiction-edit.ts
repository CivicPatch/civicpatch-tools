// What the Jurisdiction details editor can change, and which of those an edit changed. Pure.

export interface JurisdictionFields {
  url: string;
  // A government form's value, or "" when none is known.
  government_form: string;
}

// Only the fields whose value differs, as the pull request body sends them. An emptied url is
// sent (it clears the website); an emptied government form is not, since "Not known" only hands
// it back to the config files and there is nothing to write.
export function changedFields(
  saved: JurisdictionFields,
  draft: JurisdictionFields,
): Partial<JurisdictionFields> {
  const changes: Partial<JurisdictionFields> = {};
  if (draft.url !== saved.url) changes.url = draft.url;
  if (draft.government_form !== saved.government_form && draft.government_form) {
    changes.government_form = draft.government_form;
  }
  return changes;
}
