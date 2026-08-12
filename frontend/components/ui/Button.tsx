import React, { ButtonHTMLAttributes } from 'react';
import styles from './Button.module.css';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost';
  children: React.ReactNode;
}

export function Button({ variant = 'primary', className = '', children, ...props }: ButtonProps) {
  const rootClass = `${styles.button} ${styles[variant]} ${className}`;
  return (
    <button className={rootClass.trim()} {...props}>
      {children}
    </button>
  );
}
