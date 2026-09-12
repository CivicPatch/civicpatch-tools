// Pagination changes the list under the reader without moving them — call this alongside
// setPage so Next/Previous re-orients to the top of the new page instead of leaving them
// wherever they clicked from (the bottom pager, most often).
export const scrollListTop = (el?: Element | null) => {
  if (el instanceof HTMLElement) el.scrollIntoView({ block: "start", behavior: "smooth" });
};
