"use client";

import React from 'react';
import { Card, CardHeader, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';

export default function SettingsPage() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      <h1 className="title-serif">Settings</h1>
      
      <Card elevation={1}>
        <CardHeader title="API Connection" />
        <CardContent>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>Backend URL</div>
              <div style={{ fontSize: 'var(--text-base)' }}>http://localhost:8000/v1</div>
            </div>
            <div>
              <div style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>Status</div>
              <div style={{ color: 'var(--sage-700)', fontWeight: 500 }}>Connected</div>
            </div>
            <div>
              <Button variant="secondary">Test Connection</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
