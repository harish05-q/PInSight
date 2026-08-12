import React, { InputHTMLAttributes } from 'react';
import styles from './Input.module.css';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export function Input({ label, className = '', id, ...props }: InputProps) {
  return (
    <div className={`${styles.inputWrapper} ${className}`.trim()}>
      {label && <label htmlFor={id} className={styles.label}>{label}</label>}
      <input id={id} className={styles.input} {...props} />
    </div>
  );
}
