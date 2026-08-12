"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // In a real app we'd fetch /investigations, but for now we fetch incidents and get investigations
    fetchApi('/investigations')
      .then(data => {
        setInvestigations(data);
        setLoading(false);
      })
      .catch((e) => {
        console.error(e);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <h1 className="title-serif">Investigations</h1>
      
      <Card>
        <CardContent style={{ padding: 0 }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Incident ID</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Confidence</TableHead>
                <TableHead>Root Cause</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                </TableRow>
              )}
              {!loading && investigations.map((inv) => (
                <TableRow key={inv.id}>
                  <TableCell><code style={{ fontSize: 'var(--text-xs)' }}>{inv.id.slice(0, 8)}</code></TableCell>
                  <TableCell><code style={{ fontSize: 'var(--text-xs)' }}>{inv.incident_id.slice(0, 8)}</code></TableCell>
                  <TableCell>
                    <Badge variant={inv.status === 'completed' ? 'sage' : 'amber'}>
                      {inv.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{inv.rca_result?.confidence ? `${Math.round(inv.rca_result.confidence * 100)}%` : '-'}</TableCell>
                  <TableCell>{inv.rca_result?.root_cause_category || '-'}</TableCell>
                </TableRow>
              ))}
              {!loading && investigations.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No investigations found.
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
