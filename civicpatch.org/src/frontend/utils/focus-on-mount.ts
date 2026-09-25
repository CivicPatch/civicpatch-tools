export const focusOnMount = (el?: Element) => {
  if (el instanceof HTMLElement) {
    queueMicrotask(() => el.focus());
  }
};
