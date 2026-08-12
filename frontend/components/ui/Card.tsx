import React from 'react';
import styles from './Card.module.css';

interface CardProps {
  children: React.ReactNode;
  elevation?: 1 | 2;
  className?: string;
}

export function Card({ children, elevation = 1, className = '' }: CardProps) {
  const rootClass = `${styles.card} ${styles[`elevation${elevation}`]} ${className}`;
  return <div className={rootClass.trim()}>{children}</div>;
}

export function CardHeader({ title, action }: { title: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className={styles.header}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 className={styles.title}>{title}</h3>
        {action && <div>{action}</div>}
      </div>
    </div>
  );
}

export function CardContent({ children, className = '', style }: { children: React.ReactNode; className?: string; style?: React.CSSProperties }) {
  return <div className={`${styles.content} ${className}`.trim()} style={style}>{children}</div>;
}
