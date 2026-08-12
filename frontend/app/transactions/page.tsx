"use client";

import React, { useEffect, useState } from 'react';
import { fetchApi } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Table, TableHeader, TableHead, TableBody, TableRow, TableCell } from '@/components/ui/Table';
import { Skeleton } from '@/components/ui/Skeleton';
import styles from './Transactions.module.css';
import { Button } from '@/components/ui/Button';

export default function TransactionsPage() {
  const [transactions, setTransactions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchApi('/transactions')
      .then(data => {
        setTransactions(data);
        setLoading(false);
      })
      .catch(console.error);
  }, []);

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className="title-serif">Transactions</h1>
        <Button variant="secondary">Filter</Button>
      </div>

      <Card>
        <CardContent style={{ padding: 0 }}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>ID</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Merchant</TableHead>
                <TableHead>Date</TableHead>
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
              {!loading && transactions.map((t) => (
                <TableRow key={t.id}>
                  <TableCell><code style={{ fontSize: 'var(--text-xs)' }}>{t.id.slice(0, 8)}</code></TableCell>
                  <TableCell>${t.amount?.toFixed(2)}</TableCell>
                  <TableCell>
                    <Badge variant={t.status === 'failed' ? 'terracotta' : t.status === 'completed' ? 'sage' : 'neutral'}>
                      {t.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{t.merchant_id}</TableCell>
                  <TableCell>{new Date(t.created_at).toLocaleString()}</TableCell>
                </TableRow>
              ))}
              {!loading && transactions.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} style={{ textAlign: 'center', padding: 'var(--space-8)' }}>
                    No transactions found.
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
