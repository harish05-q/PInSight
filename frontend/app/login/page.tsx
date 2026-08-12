"use client";

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastContext';
import { fetchApi, setToken } from '@/lib/api';
import styles from './Login.module.css';

export default function LoginPage() {
  const [clientId, setClientId] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const { toast } = useToast();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const data = await fetchApi('/auth/token', {
        method: 'POST',
        body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
      });
      setToken(data.access_token);
      toast({ title: 'Logged in successfully', type: 'success' });
      router.push('/');
    } catch (err: any) {
      toast({ title: 'Login failed', message: err.message, type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.card}>
        <h1 className={`${styles.title} title-serif`}>PInSight</h1>
        <p className={styles.subtitle}>Sign in to your account</p>
        
        <form onSubmit={handleLogin} className={styles.form}>
          <Input 
            label="Client ID (Admin Username)" 
            value={clientId}
            onChange={(e) => setClientId(e.target.value)}
            required
            disabled={loading}
          />
          <Input 
            label="Client Secret (Admin Password)" 
            type="password"
            value={clientSecret}
            onChange={(e) => setClientSecret(e.target.value)}
            required
            disabled={loading}
          />
          <Button 
            type="submit" 
            className={styles.button}
            disabled={loading}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </Button>
        </form>
      </div>
    </div>
  );
}
