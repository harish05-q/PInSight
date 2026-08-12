/**
 * PInSight Load Test — k6
 * 
 * Tests non-agent endpoints against SRS §2.4.1 targets:
 *   - p99 latency < 300ms
 *   - ≥ 50 req/s sustained
 * 
 * Run against Docker Compose stack:
 *   docker compose up -d
 *   k6 run backend/tests/loadtest.js
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { uuidv4 } from 'https://jslib.k6.io/k6-utils/1.4.0/index.js';

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

// Custom metrics
const idempotencyCollisions = new Counter('idempotency_collisions');
const transactionCreateDuration = new Trend('transaction_create_duration');

// ---------- Scenario 1: Baseline Throughput ----------
export const options = {
  scenarios: {
    // Scenario 1: Sustained baseline throughput
    baseline: {
      executor: 'constant-arrival-rate',
      rate: 60,          // 60 req/s
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 20,
      maxVUs: 50,
      exec: 'baseline',
      tags: { scenario: 'baseline' },
    },

    // Scenario 2: Idempotency collision stress
    idempotency_stress: {
      executor: 'per-vu-iterations',
      vus: 20,
      iterations: 5,
      startTime: '35s',
      exec: 'idempotencyStress',
      tags: { scenario: 'idempotency_stress' },
    },

    // Scenario 3: Mixed realistic workload
    mixed_workload: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 15,
      maxVUs: 40,
      startTime: '70s',
      exec: 'mixedWorkload',
      tags: { scenario: 'mixed_workload' },
    },
  },

  thresholds: {
    // SRS §2.4.1 performance targets
    'http_req_duration{scenario:baseline}': ['p(99)<300'],
    'http_req_duration{scenario:mixed_workload}': ['p(99)<300'],
    'http_req_failed': ['rate<0.05'],  // < 5% error rate
  },
};

// Get auth token once per VU
let authToken = null;

function getToken() {
  if (authToken) return authToken;
  const loginRes = http.post(
    `${BASE_URL}/v1/auth/token`,
    JSON.stringify({
      client_id: __ENV.ADMIN_USER || 'admin',
      client_secret: __ENV.ADMIN_PASS || 'admin',
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  if (loginRes.status === 200) {
    authToken = JSON.parse(loginRes.body).access_token;
  }
  return authToken;
}

function authHeaders() {
  const token = getToken();
  return {
    'Content-Type': 'application/json',
    Authorization: token ? `Bearer ${token}` : '',
  };
}

// ---------- Scenario Handlers ----------

export function baseline() {
  // 70% health checks + 30% transaction listing
  const rand = Math.random();
  if (rand < 0.7) {
    const res = http.get(`${BASE_URL}/v1/health`);
    check(res, { 'health 200': (r) => r.status === 200 });
  } else {
    const res = http.get(`${BASE_URL}/v1/transactions`, {
      headers: authHeaders(),
    });
    check(res, { 'transactions list ok': (r) => r.status === 200 });
  }
}

export function idempotencyStress() {
  // All 20 VUs send the SAME idempotency key — only 1 should create
  const SHARED_KEY = 'loadtest-collision-key-' + (__ENV.RUN_ID || 'default');

  const res = http.post(
    `${BASE_URL}/v1/transactions`,
    JSON.stringify({
      idempotency_key: SHARED_KEY,
      amount: 100.0,
      currency: 'USD',
      merchant_id: '00000000-0000-0000-0000-000000000001',
    }),
    { headers: authHeaders() }
  );

  transactionCreateDuration.add(res.timings.duration);

  if (res.status === 409 || res.status === 200) {
    // Expected: one 200 (created), rest 409 (duplicate)
    if (res.status === 409) {
      idempotencyCollisions.add(1);
    }
    check(res, { 'idempotency handled': () => true });
  } else {
    check(res, { 'unexpected status': () => false });
  }
}

export function mixedWorkload() {
  const rand = Math.random();

  if (rand < 0.50) {
    // 50% reads — list transactions
    const res = http.get(`${BASE_URL}/v1/transactions`, {
      headers: authHeaders(),
    });
    check(res, { 'tx list ok': (r) => r.status === 200 });
  } else if (rand < 0.75) {
    // 25% reads — dashboard summary
    const res = http.get(`${BASE_URL}/v1/dashboard/summary`, {
      headers: authHeaders(),
    });
    check(res, { 'dashboard ok': (r) => r.status === 200 });
  } else if (rand < 0.90) {
    // 15% writes — create transaction with unique key
    const res = http.post(
      `${BASE_URL}/v1/transactions`,
      JSON.stringify({
        idempotency_key: `loadtest-${uuidv4()}`,
        amount: Math.random() * 500,
        currency: 'USD',
        merchant_id: '00000000-0000-0000-0000-000000000001',
      }),
      { headers: authHeaders() }
    );
    check(res, { 'tx create ok': (r) => r.status === 200 || r.status === 201 });
  } else {
    // 10% health
    const res = http.get(`${BASE_URL}/v1/health`);
    check(res, { 'health ok': (r) => r.status === 200 });
  }
}
