import React from 'react';
import styles from './Table.module.css';

interface TableProps {
  children: React.ReactNode;
  className?: string;
}

export function Table({ children, className = '' }: TableProps) {
  return (
    <div className={`${styles.tableWrapper} ${className}`.trim()}>
      <table className={styles.table}>{children}</table>
    </div>
  );
}

export function TableHeader({ children }: { children: React.ReactNode }) {
  return <thead>{children}</thead>;
}

export function TableBody({ children }: { children: React.ReactNode }) {
  return <tbody>{children}</tbody>;
}

export function TableRow({ children, className = '', onClick }: { children: React.ReactNode; className?: string; onClick?: () => void }) {
  return <tr className={`${styles.tr} ${className}`.trim()} onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default' }}>{children}</tr>;
}

export function TableHead({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <th className={`${styles.th} ${className}`.trim()}>{children}</th>;
}

export function TableCell({ children, className = '', colSpan, style }: { children: React.ReactNode; className?: string; colSpan?: number; style?: React.CSSProperties }) {
  return <td className={`${styles.td} ${className}`.trim()} colSpan={colSpan} style={style}>{children}</td>;
}
