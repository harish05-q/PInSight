import React from 'react';
import styles from './Badge.module.css';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'neutral' | 'sage' | 'terracotta' | 'amber';
  className?: string;
}

export function Badge({ children, variant = 'neutral', className = '' }: BadgeProps) {
  const rootClass = `${styles.badge} ${styles[variant]} ${className}`;
  return <span className={rootClass.trim()}>{children}</span>;
}
