import { useState, useEffect } from 'haunted';
import { createRef } from 'lit-html/directives/ref.js';

export function useRovingFocusList(length) {
  const [focusedIdx, setFocusedIdx] = useState(0);
  const refs = Array.from({ length }, () => createRef());

  useEffect(() => {
    refs[focusedIdx]?.value?.focus();
  }, [focusedIdx, length]);

  function handleKeyDown(e, idx) {
    let nextIdx = idx;
    if (['ArrowRight', 'ArrowDown'].includes(e.key)) {
      nextIdx = Math.min(length - 1, idx + 1);
    } else if (['ArrowLeft', 'ArrowUp'].includes(e.key)) {
      nextIdx = Math.max(0, idx - 1);
    } else {
      return;
    }
    e.preventDefault();
    setFocusedIdx(nextIdx);
  }

  return {
    refs,
    focusedIdx,
    setFocusedIdx,
    handleKeyDown,
  };
}