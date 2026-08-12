"use client";

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { 
  LayoutDashboard, 
  AlertTriangle, 
  Activity, 
  Search, 
  BookOpen, 
  BarChart2, 
  Settings,
  Menu,
  LogOut
} from 'lucide-react';
import styles from './Shell.module.css';
import { getToken, removeToken } from '@/lib/api';

const NAV_ITEMS = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { href: '/transactions', label: 'Transactions', icon: Activity },
  { href: '/investigations', label: 'Investigations', icon: Search },
  { href: '/runbooks', label: 'Runbooks', icon: BookOpen },
  { href: '/evals', label: 'Eval Reports', icon: BarChart2 },
  { href: '/settings', label: 'Settings', icon: Settings },
];

import { CommandPalette } from './CommandPalette';

export function Shell({ children }: { children: React.ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  // Protect routes natively here in the shell since everything is Client Components right now.
  useEffect(() => {
    if (!getToken() && pathname !== '/login') {
      router.push('/login');
    }
  }, [pathname, router]);

  if (pathname === '/login') {
    return <>{children}</>;
  }

  const activeItem = NAV_ITEMS.find(item => 
    item.href === '/' ? pathname === '/' : pathname.startsWith(item.href)
  ) || NAV_ITEMS[0];

  const handleLogout = () => {
    removeToken();
    router.push('/login');
  };

  return (
    <div className={styles.shell}>
      <CommandPalette />
      <aside className={`${styles.sidebar} ${collapsed ? styles.sidebarCollapsed : ''}`}>
        <div className={`${styles.logo} ${collapsed ? styles.logoCollapsed : ''} title-serif`}>
          {collapsed ? 'PI' : 'PInSight'}
        </div>
        <nav className={styles.nav}>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
            return (
              <Link 
                key={item.href} 
                href={item.href}
                className={`${styles.navItem} ${isActive ? styles.navItemActive : ''}`}
                title={collapsed ? item.label : undefined}
              >
                <Icon size={20} />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>
        <div className={styles.nav} style={{ flex: 'none', borderTop: '1px solid var(--border-subtle)' }}>
          <button className={styles.navItem} onClick={handleLogout} style={{ background: 'none', border: 'none', width: '100%', cursor: 'pointer' }}>
            <LogOut size={20} />
            {!collapsed && <span>Logout</span>}
          </button>
        </div>
      </aside>

      <main className={styles.main}>
        <header className={styles.header}>
          <div className={styles.headerLeft}>
            <button 
              onClick={() => setCollapsed(!collapsed)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)' }}
            >
              <Menu size={20} />
            </button>
            <div className={styles.breadcrumb}>
              {activeItem.label}
            </div>
          </div>
          <div className={styles.headerRight}>
            <button className={styles.searchBtn} onClick={() => window.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', metaKey: true }))}>
              <Search size={14} />
              <span>Search...</span>
              <kbd style={{ marginLeft: 8, padding: '2px 4px', backgroundColor: 'var(--bg-surface-1)', borderRadius: 4, border: '1px solid var(--border-subtle)' }}>
                ⌘K
              </kbd>
            </button>
          </div>
        </header>
        
        <div className={styles.content}>
          {children}
        </div>
      </main>
    </div>
  );
}
