/** Emit a component's own event, from its own element.
 *
 * `host` rather than the DOM event's target, because a parent listens on the component element
 * — an event fired from the button inside it is a different origin that happens to bubble past.
 *
 * `composed` so it crosses a shadow boundary if one is ever added; these components render
 * light DOM today, and a listener that stops working on that change would be hard to place.
 */
export function hostDispatch(
  host: HTMLElement,
  name: string,
  detail?: unknown,
): void {
  host.dispatchEvent(
    new CustomEvent(name, { detail, bubbles: true, composed: true }),
  );
}
