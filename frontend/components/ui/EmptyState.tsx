import React from 'react';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  icon: React.ReactNode;
  title: string;
  description: string;
  action?: React.ReactNode;
  className?: string;
}

export function EmptyState({ icon, title, description, action, className = '' }: EmptyStateProps) {
  return (
    <div className={`${styles.emptyState} ${className}`.trim()}>
      <div className={styles.iconWrapper}>
        {icon}
      </div>
      <div>
        <h3 className={styles.title}>{title}</h3>
        <p className={styles.description}>{description}</p>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
