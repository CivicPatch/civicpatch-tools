import { useState, useRef } from 'haunted';

export function useSortableList(data, identifier, onReorder) {
  const [draggedIndex, setDraggedIndex] = useState(null);
  const [dragOverIndex, setDragOverIndex] = useState(null);

  // Keep a ref to always have fresh values in handlers
  const dataRef = useRef(data);
  dataRef.current = data;

  const onReorderRef = useRef(onReorder);
  onReorderRef.current = onReorder;

  function throttle(fn, ms) {
    let last = 0;
    return (...args) => {
      const now = Date.now();
      if (now - last < ms) return;
      last = now;
      fn(...args);
    };
  }

  function handleDragStart(index, e) {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = "move";
  }

  const throttledDragOver = useRef(throttle((index, e) => {
    e.preventDefault();
    setDragOverIndex(index);
  }, 50));

  function handleDragOver(index, e) {
    e.preventDefault(); // must call immediately, can't throttle this
    throttledDragOver.current(index, e);
  }

  function handleDrop(dropIndex, e) {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === dropIndex) {
      setDraggedIndex(null);
      setDragOverIndex(null);
      return;
    }

    const currentData = dataRef.current; // always fresh
    const newOrder = [...currentData];
    const [moved] = newOrder.splice(draggedIndex, 1);

    let insertIndex = draggedIndex < dropIndex ? dropIndex - 1 : dropIndex;
    newOrder.splice(Math.min(insertIndex, newOrder.length), 0, moved);

    onReorderRef.current(newOrder.map(r => r[identifier])); // always fresh
    setDraggedIndex(null);
    setDragOverIndex(null);
  }

  function handleDragEnd() {
    setDraggedIndex(null);
    setDragOverIndex(null);
  }

  return {
    draggedIndex,
    dragOverIndex,
    handleDragStart,
    handleDragOver,
    handleDrop,
    handleDragEnd,
  };
}