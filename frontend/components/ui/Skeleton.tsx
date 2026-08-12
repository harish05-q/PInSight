import React from 'react';
import styles from './Skeleton.module.css';

interface SkeletonProps {
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: React.CSSProperties;
}

export function Skeleton({ width, height, className = '', style }: SkeletonProps) {
  return (
    <div
      className={`${styles.skeleton} ${className}`.trim()}
      style={{ width, height, ...style }}
    />
  );
}
