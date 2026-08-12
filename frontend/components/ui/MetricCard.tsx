"use client";

import React, { useEffect, useState } from "react";
import { animate } from "framer-motion";
import styles from "./MetricCard.module.css";

interface MetricCardProps {
  label: string;
  value: number;
  prefix?: string;
  suffix?: string;
  trend?: number; // positive or negative percentage
}

export function MetricCard({ label, value, prefix = "", suffix = "", trend }: MetricCardProps) {
  const [displayValue, setDisplayValue] = useState(0);

  useEffect(() => {
    const controls = animate(0, value, {
      duration: 0.6,
      ease: "easeOut",
      onUpdate: (v) => {
        setDisplayValue(Math.round(v));
      },
    });
    return controls.stop;
  }, [value]);

  return (
    <div className={styles.metricCard}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>
        {prefix}
        {displayValue}
        {suffix}
      </span>
      {trend !== undefined && (
        <span
          className={`${styles.trend} ${
            trend >= 0 ? styles.trendUp : styles.trendDown
          }`}
        >
          {trend >= 0 ? "↑" : "↓"} {Math.abs(trend)}%
        </span>
      )}
    </div>
  );
}
