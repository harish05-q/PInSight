"use client";

import React, { useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';
import styles from './Modal.module.css';

interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: React.ReactNode;
  children: React.ReactNode;
  type?: 'center' | 'slide-over';
}

export function Modal({ isOpen, onClose, title, children, type = 'center' }: ModalProps) {
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isOpen]);

  const isSlide = type === 'slide-over';

  return (
    <AnimatePresence>
      {isOpen && (
        <div className={`${styles.overlay} ${isSlide ? styles.slideOver : styles.center}`}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={styles.overlay}
            onClick={onClose}
            style={{ position: 'absolute', zIndex: -1 }}
          />
          <motion.div
            initial={isSlide ? { x: '100%' } : { opacity: 0, scale: 0.95, y: 20 }}
            animate={isSlide ? { x: 0 } : { opacity: 1, scale: 1, y: 0 }}
            exit={isSlide ? { x: '100%' } : { opacity: 0, scale: 0.95, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className={`${styles.modal} ${isSlide ? styles.modalSlide : styles.modalCenter}`}
            role="dialog"
            aria-modal="true"
          >
            <div className={styles.header}>
              <h2 className={styles.title}>{title}</h2>
              <button onClick={onClose} className={styles.closeButton} aria-label="Close">
                <X size={20} />
              </button>
            </div>
            <div className={styles.content}>
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
