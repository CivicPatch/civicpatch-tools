// Focus fires after commit, since lit-html parts land while the fragment is still detached.
export const focusOnMount = (el?: Element) => {
  if (el instanceof HTMLElement) queueMicrotask(() => el.focus());
};
