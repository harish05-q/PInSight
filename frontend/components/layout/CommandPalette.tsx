"use client";

import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Search } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { fetchApi } from '@/lib/api';
import styles from './CommandPalette.module.css';
import { Badge } from '../ui/Badge';

interface SearchResult {
  type: 'incident' | 'runbook';
  id: string;
  title: string;
  description: string;
  status?: string;
}

export function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    if (isOpen) {
      inputRef.current?.focus();
    } else {
      setQuery('');
      setResults([]);
    }
  }, [isOpen]);

  useEffect(() => {
    if (query.trim().length < 2) {
      setResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const data = await fetchApi(`/search?q=${encodeURIComponent(query)}`);
        setResults(data.results || []);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const handleSelect = (result: SearchResult) => {
    setIsOpen(false);
    if (result.type === 'incident') {
      router.push(`/incidents/${result.id}`);
    } else {
      router.push(`/runbooks?id=${result.id}`);
    }
  };

  return (
    <AnimatePresence>
      {isOpen && (
        <div className={styles.overlay}>
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className={styles.overlay}
            onClick={() => setIsOpen(false)}
            style={{ position: 'absolute', paddingTop: 0 }}
          />
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className={styles.palette}
          >
            <div className={styles.searchHeader}>
              <Search size={20} color="var(--text-muted)" />
              <input
                ref={inputRef}
                className={styles.searchInput}
                placeholder="Search incidents or runbooks..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            
            <div className={styles.results}>
              {loading && <div className={styles.emptyState}>Searching...</div>}
              {!loading && query.length > 0 && results.length === 0 && (
                <div className={styles.emptyState}>No results found.</div>
              )}
              {!loading && results.map((result) => (
                <div 
                  key={`${result.type}-${result.id}`} 
                  className={styles.resultItem}
                  onClick={() => handleSelect(result)}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span className={styles.resultTitle}>{result.title}</span>
                    <Badge variant={result.type === 'incident' ? 'terracotta' : 'sage'}>
                      {result.type}
                    </Badge>
                  </div>
                  <span className={styles.resultDesc}>{result.description}</span>
                </div>
              ))}
            </div>
            
            <div className={styles.keyboardHints}>
              <span><kbd>esc</kbd> to close</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
