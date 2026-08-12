"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { MetricCard } from '@/components/ui/MetricCard';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';

export default function EvalsPage() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/eval/runs')
      .then(data => {
        setRuns(data);
        setLoading(false);
      })
      .catch((e) => {
        console.error(e);
        setLoading(false);
      });
  }, []);

  const latestRun = runs.length > 0 ? runs[0] : null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <h1 className="title-serif">Eval Reports</h1>
      
      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '24px' }}>
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '24px' }}>
          <MetricCard 
            label="Latest Precision" 
            value={latestRun ? latestRun.metrics.precision * 100 : 0} 
            suffix="%"
          />
          <MetricCard 
            label="Latest Recall" 
            value={latestRun ? latestRun.metrics.recall * 100 : 0} 
            suffix="%"
          />
          <MetricCard 
            label="Cost per Run" 
            value={latestRun ? latestRun.cost_usd : 0} 
            prefix="$"
          />
        </div>
      )}

      <h2 style={{ fontSize: 'var(--text-lg)', fontWeight: 500, marginTop: '24px' }}>Historical Runs</h2>
      <Card>
        <CardContent style={{ padding: 0 }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Dataset Size</TableHead>
                <TableHead>Precision</TableHead>
                <TableHead>Recall</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Date</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell colSpan={6}><Skeleton height={20} /></TableCell>
                </TableRow>
              )}
              {!loading && runs.map((run) => (
                <TableRow key={run.id}>
                  <TableCell><code style={{ fontSize: 'var(--text-xs)' }}>{run.id.slice(0, 8)}</code></TableCell>
                  <TableCell>{run.sample_size}</TableCell>
                  <TableCell>{Math.round(run.metrics.precision * 100)}%</TableCell>
                  <TableCell>{Math.round(run.metrics.recall * 100)}%</TableCell>
                  <TableCell>
                    <Badge variant={run.status === 'completed' ? 'sage' : 'amber'}>
                      {run.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{new Date(run.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
              {!loading && runs.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No eval runs found.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
