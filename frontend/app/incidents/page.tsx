"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { TraceViewer } from '@/components/incidents/TraceViewer';
import { EmptyState } from '@/components/ui/EmptyState';
import { AlertTriangle, Info } from 'lucide-react';
import styles from './Incidents.module.css';

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);
  
  const [details, setDetails] = useState<any>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  useEffect(() => {
    fetchApi('/incidents')
      .then(data => {
        setIncidents(data);
        setLoadingList(false);
        if (data.length > 0) {
          setSelectedId(data[0].id);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    setLoadingDetails(true);
    // Fetch incident details, then fetch investigation trace
    fetchApi(`/incidents/${selectedId}`)
      .then(async (data) => {
        let investigations = [];
        try {
          investigations = await fetchApi(`/incidents/${selectedId}/investigations`);
        } catch (e) {
          // ignore
        }
        setDetails({ ...data, investigations });
        setLoadingDetails(false);
      })
      .catch(console.error);
  }, [selectedId]);

  return (
    <div className={styles.container}>
      <aside className={styles.master}>
        <div className={styles.masterHeader}>
          <h2 style={{ fontSize: 'var(--text-md)', fontWeight: 500 }}>Incidents</h2>
        </div>
        <div className={styles.masterList}>
          {loadingList && <div style={{ padding: 16 }}><Skeleton height={40} className="mb-2" /><Skeleton height={40} /></div>}
          {!loadingList && incidents.length === 0 && (
            <div style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)' }}>No incidents</div>
          )}
          {incidents.map((inc) => (
            <div 
              key={inc.id}
              className={`${styles.incidentItem} ${selectedId === inc.id ? styles.incidentItemActive : ''}`}
              onClick={() => setSelectedId(inc.id)}
            >
              <div className={styles.itemHeader}>
                <span className={styles.itemId}>{inc.id.slice(0, 8)}</span>
                <Badge variant={inc.status === 'active' ? 'terracotta' : 'sage'}>{inc.status}</Badge>
              </div>
              <div className={styles.itemTitle}>{inc.title}</div>
            </div>
          ))}
        </div>
      </aside>

      <main className={styles.detail}>
        {loadingDetails && (
          <div style={{ padding: 32 }}>
            <Skeleton height={32} width="50%" className="mb-4" />
            <Skeleton height={20} width="30%" className="mb-8" />
            <Skeleton height={200} />
          </div>
        )}
        
        {!loadingDetails && !details && (
          <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <EmptyState 
              icon={<Info size={48} />}
              title="Select an Incident"
              description="Choose an incident from the list to view its details and agent traces."
            />
          </div>
        )}

        {!loadingDetails && details && (
          <>
            <div className={styles.detailHeader}>
              <h1 className={`${styles.detailTitle} title-serif`}>{details.title}</h1>
              <div className={styles.detailMeta}>
                <span>Created: {new Date(details.created_at).toLocaleString()}</span>
                <span>Severity: {details.severity}</span>
              </div>
            </div>
            
            <div className={styles.detailContent}>
              <h3 className={styles.sectionTitle}>Agent Investigation Trace</h3>
              
              {(!details.investigations || details.investigations.length === 0) ? (
                <EmptyState 
                  icon={<AlertTriangle size={32} />}
                  title="No Investigation Yet"
                  description="An agent has not yet investigated this incident."
                />
              ) : (
                <TraceViewer 
                  steps={details.investigations[0].trace || []}
                  rca={details.investigations[0].rca_result}
                />
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
