import { useEffect, useRef } from 'haunted';

/**
 * useRovingFocus - Keyboard navigation for a list/grid of focusable cards.
 * @param {Object} options
 * @param {Function} options.onArrow - Called with direction ('left'|'right'|'up'|'down') when arrow key pressed.
 * @returns {Object} { ref }
 */
export function useRovingFocus({ onArrow } = {}) {
  const ref = useRef(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    const handleKeyDown = (e) => {
      if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(e.key)) {
        e.preventDefault();
        if (onArrow) {
          onArrow(e.key.replace('Arrow', '').toLowerCase());
        }
      }
    };
    node.addEventListener('keydown', handleKeyDown);
    return () => node.removeEventListener('keydown', handleKeyDown);
  }, [onArrow]);

  return { ref };
}