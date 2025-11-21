import { useState, useEffect } from "haunted";
import { createRef } from "lit-html/directives/ref.js";

export function useModal(initialOpen = false) {
  const [isOpen, setIsOpen] = useState(initialOpen);
  const modalRef = createRef();

  const openModal = () => setIsOpen(true);
  const closeModal = () => setIsOpen(false);

  useEffect(() => {
    if (isOpen && modalRef.value) {
      // Focus the modal when it opens
      modalRef.value.focus();
    }
  }, [isOpen]);

  // Handle escape key with document listener
  useEffect(() => {
    const handleKeyDown = (event) => {
      if (event.key === 'Escape' && isOpen) {
        closeModal();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      
      // Cleanup function - runs when isOpen changes to false or component unmounts
      return () => {
        document.removeEventListener('keydown', handleKeyDown);
      };
    }
  }, [isOpen, closeModal]);

  // Handle click outside modal
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (modalRef.value && !modalRef.value.contains(event.target) && isOpen) {
        closeModal();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
      
      return () => {
        document.removeEventListener('mousedown', handleClickOutside);
      };
    }
  }, [isOpen, closeModal]);

  return {
    isOpen,
    openModal,
    closeModal,
    modalProps: {
      open: isOpen,
      onClose: closeModal,
      modalRef: modalRef
    }
  };
}