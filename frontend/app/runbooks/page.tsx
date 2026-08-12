"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/Card';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';

export default function RunbooksPage() {
  const [runbooks, setRunbooks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Assuming GET /v1/runbooks exists, else we mock or fail gracefully
    fetchApi('/runbooks')
      .then(data => {
        setRunbooks(data);
        setLoading(false);
      })
      .catch((e) => {
        console.error(e);
        setLoading(false);
      });
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <h1 className="title-serif">Runbooks</h1>
      
      <Card>
        <CardContent style={{ padding: 0 }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Title</TableHead>
                <TableHead>Condition</TableHead>
                <TableHead>Last Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading && (
                <TableRow>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                  <TableCell><Skeleton height={20} /></TableCell>
                </TableRow>
              )}
              {!loading && runbooks.map((rb) => (
                <TableRow key={rb.id}>
                  <TableCell><code style={{ fontSize: 'var(--text-xs)' }}>{rb.id.slice(0, 8)}</code></TableCell>
                  <TableCell>{rb.title}</TableCell>
                  <TableCell>{rb.trigger_condition || 'Manual'}</TableCell>
                  <TableCell>{new Date(rb.updated_at).toLocaleDateString()}</TableCell>
                </TableRow>
              ))}
              {!loading && runbooks.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No runbooks found.
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
