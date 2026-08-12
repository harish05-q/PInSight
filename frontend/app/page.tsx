"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { MetricCard } from '@/components/ui/MetricCard';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import styles from './Dashboard.module.css';

export default function Dashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/dashboard/summary')
      .then(data => {
        setStats(data);
        setLoading(false);
      })
      .catch(console.error);
  }, []);

  if (loading) {
    return (
      <div>
        <h1 className="title-serif" style={{ marginBottom: '24px' }}>Dashboard</h1>
        <div className={styles.grid}>
          <Skeleton height={100} />
          <Skeleton height={100} />
          <Skeleton height={100} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="title-serif" style={{ marginBottom: '24px' }}>Dashboard</h1>
      
      <div className={styles.grid}>
        <MetricCard 
          label="Active Incidents" 
          value={stats?.incidents_by_status?.active || 0} 
        />
        <MetricCard 
          label="Transactions Processed" 
          value={stats?.transactions_by_status?.completed || 0} 
        />
        <MetricCard 
          label="Pending Triage" 
          value={stats?.incidents_by_status?.pending_triage || 0} 
        />
      </div>

      <div className={styles.section}>
        <h2 className={styles.title}>Recent Activity</h2>
        <Card>
          <CardContent style={{ padding: 0 }}>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Status</TableHead>
                  <TableHead>Count</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {Object.entries(stats?.incidents_by_status || {}).map(([status, count]) => (
                  <TableRow key={status}>
                    <TableCell>
                      <Badge variant={status === 'active' ? 'terracotta' : status === 'resolved' ? 'sage' : 'neutral'}>
                        {status.replace('_', ' ')}
                      </Badge>
                    </TableCell>
                    <TableCell>{count as number}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
