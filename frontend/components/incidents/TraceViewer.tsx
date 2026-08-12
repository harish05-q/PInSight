"use client";

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Bot, ChevronDown, ChevronUp, CheckCircle2 } from 'lucide-react';
import styles from './TraceViewer.module.css';
import { Badge } from '../ui/Badge';

interface TraceStep {
  id: string;
  tool_name: string;
  latency_ms: number;
  timestamp: string;
  input: any;
  output: any;
  status: 'running' | 'completed' | 'failed';
}

interface RCA {
  summary: string;
  confidence: number;
  root_cause_category: string;
}

interface TraceViewerProps {
  steps: TraceStep[];
  rca?: RCA;
}

export function TraceViewer({ steps, rca }: TraceViewerProps) {
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());

  const toggleStep = (id: string) => {
    setExpandedSteps((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className={styles.traceContainer}>
      {steps.map((step, index) => (
        <motion.div
          key={step.id}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            type: 'spring',
            stiffness: 300,
            damping: 30,
            delay: index * 0.08, // Staggered spring reveal (80ms)
          }}
          className={styles.step}
        >
          <div className={`${styles.stepIcon} ${step.status === 'running' ? styles.stepIconActive : ''}`}>
            <Bot size={20} />
          </div>
          <div className={styles.stepContent}>
            <div className={styles.stepHeader} onClick={() => toggleStep(step.id)}>
              <div className={styles.stepTool}>
                {step.tool_name}()
              </div>
              <div className={styles.stepMeta}>
                <Badge variant={step.status === 'running' ? 'amber' : step.status === 'failed' ? 'terracotta' : 'sage'}>
                  {step.status}
                </Badge>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{step.latency_ms}ms</span>
                {expandedSteps.has(step.id) ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </div>
            </div>
            <AnimatePresence>
              {expandedSteps.has(step.id) && (
                <motion.div
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  className={styles.stepDetails}
                >
                  <div style={{ marginBottom: 8, fontWeight: 500, fontSize: '12px' }}>Input:</div>
                  <pre className={styles.jsonBlock}>{JSON.stringify(step.input, null, 2)}</pre>
                  <div style={{ margin: '16px 0 8px', fontWeight: 500, fontSize: '12px' }}>Output:</div>
                  <pre className={styles.jsonBlock}>{JSON.stringify(step.output, null, 2)}</pre>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      ))}

      {rca && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30, delay: steps.length * 0.08 }}
          className={styles.rcaCard}
          style={{ zIndex: 1 }}
        >
          <div className={styles.rcaContent}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <CheckCircle2 color="var(--sage-700)" size={24} />
              <h3 className={styles.rcaTitle}>Root Cause Analysis</h3>
            </div>
            <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: '16px' }}>
              {rca.summary}
            </p>
            <Badge variant="sage">{rca.root_cause_category}</Badge>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
            <div 
              className={styles.radialProgress} 
              style={{ '--confidence': Math.round(rca.confidence * 100) } as React.CSSProperties}
            >
              <span className={styles.radialInner}>{Math.round(rca.confidence * 100)}%</span>
            </div>
            <span style={{ fontSize: '10px', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Confidence</span>
          </div>
        </motion.div>
      )}
    </div>
  );
}
