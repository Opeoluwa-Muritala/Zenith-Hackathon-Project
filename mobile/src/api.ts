import * as SecureStore from 'expo-secure-store';

const API_BASE_URL = (process.env.EXPO_PUBLIC_API_BASE_URL ?? 'http://10.0.2.2:8080').replace(/\/$/, '');
const ACCESS_KEY = 'cashlens.access-token';
const REFRESH_KEY = 'cashlens.refresh-token';
const REQUEST_TIMEOUT_MS = 15_000;

type Tokens = { access_token: string; refresh_token: string };

export class ApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

async function saveTokens(tokens: Tokens): Promise<void> {
  await SecureStore.setItemAsync(ACCESS_KEY, tokens.access_token);
  await SecureStore.setItemAsync(REFRESH_KEY, tokens.refresh_token);
}

export async function clearTokens(): Promise<void> {
  await SecureStore.deleteItemAsync(ACCESS_KEY);
  await SecureStore.deleteItemAsync(REFRESH_KEY);
}

async function rotateTokens(): Promise<string | null> {
  const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
  if (!refreshToken) return null;
  try {
    const result = await request<Tokens>('/auth/refresh', {
      method: 'POST',
      body: JSON.stringify({ refresh_token: refreshToken }),
    }, false);
    await saveTokens(result);
    return result.access_token;
  } catch {
    await clearTokens();
    return null;
  }
}

async function request<T>(path: string, init: RequestInit = {}, authenticated = true, retried = false): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const accessToken = authenticated ? await SecureStore.getItemAsync(ACCESS_KEY) : null;
    const response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(init.body ? { 'Content-Type': 'application/json' } : {}),
        'Cache-Control': 'no-store',
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
        ...init.headers,
      },
    });
    if (response.status === 401 && authenticated && !retried) {
      const refreshed = await rotateTokens();
      if (refreshed) return request<T>(path, init, authenticated, true);
      throw new ApiError('Session expired. Please sign in again.', 401);
    }
    if (!response.ok) {
      let message = `Request failed (${response.status})`;
      try {
        const body = await response.json() as { detail?: unknown; message?: unknown };
        if (typeof body.detail === 'string') message = body.detail;
        else if (typeof body.message === 'string') message = body.message;
      } catch { /* Keep the non-sensitive status message. */ }
      throw new ApiError(message, response.status);
    }
    if (response.status === 204) return undefined as T;
    return await response.json() as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof Error && error.name === 'AbortError') throw new ApiError('The server took too long to respond.');
    throw new ApiError('Could not reach the backend. Check that it is running and the API address is correct.');
  } finally {
    clearTimeout(timeout);
  }
}

export type Overview = {
  income_minor: number;
  spend_minor: number;
  savings_rate_bps: number;
  total_balance_minor: number;
};
export type Insight = {
  id: string;
  module: string;
  kind: string;
  severity: string;
  title: string;
  body: string;
  footer?: string | null;
  wording_source?: string;
  template_title?: string;
  template_body?: string;
};
export type Account = { id: string; type: string; currency: string; balance_minor: number; account_number_masked: string };
export type Consent = { id: string; institution: string; scope: string; revoked_at: string | null };
export type Recurring = { id: string; amount_minor: number; next_expected_at: string; status: string; annualised_minor: number };
export type Transaction = { id: string; posted_at: string; amount_minor: number; direction: string; narration: string; category: string };

export const api = {
  requestOtp: (phone: string) => request<{ status: string }>('/auth/otp/request', { method: 'POST', body: JSON.stringify({ phone }) }, false),
  verifyOtp: (phone: string, otp: string) => request<Tokens>('/auth/otp/verify', { method: 'POST', body: JSON.stringify({ phone, otp }) }, false),
  verifyIdentity: (bvn: string) => request<{ verified: boolean }>('/identity/bvn/verify', { method: 'POST', body: JSON.stringify({ bvn }) }),
  overview: () => request<Overview>('/summary/overview'),
  forecast: () => request<Record<string, unknown>>('/forecast/safe-to-spend'),
  insights: () => request<Insight[]>('/insights'),
  transactions: () => request<Transaction[]>('/transactions?limit=50&offset=0'),
  recurring: () => request<Recurring[]>('/recurring'),
  accounts: () => request<Account[]>('/accounts'),
  consents: () => request<Consent[]>('/consents'),
  createConsent: (institution: string) => request<Consent>('/consents', { method: 'POST', body: JSON.stringify({ institution, scope: 'transactions,balances', expires_in_days: 30 }) }),
  linkDemo: (consentId: string, institutionCode: string) => request<{ id: string; status: string }>('/accounts/link', { method: 'POST', body: JSON.stringify({ consent_id: consentId, institution_code: institutionCode }) }),
  initiateMonoLink: (consentId: string, name: string, email: string) => request<{ ref: string; url: string; status: string }>('/accounts/link/initiate', { method: 'POST', body: JSON.stringify({ consent_id: consentId, name, email }) }),
  monoLinkStatus: (ref: string) => request<{ ref: string; status: string; data_status?: string }>(`/accounts/link/status?ref=${encodeURIComponent(ref)}`),
  sync: () => request<{ transactions_imported: number }>('/sync', { method: 'POST' }),
  revoke: (id: string) => request<void>(`/consents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  dismissInsight: (id: string) => request<void>(`/insights/${encodeURIComponent(id)}/dismiss`, { method: 'POST' }),
  logout: async () => {
    const refreshToken = await SecureStore.getItemAsync(REFRESH_KEY);
    if (refreshToken) await request<void>('/auth/logout', { method: 'POST', body: JSON.stringify({ refresh_token: refreshToken }) }).catch(() => undefined);
    await clearTokens();
  },
};

export async function persistSession(tokens: Tokens): Promise<void> {
  await saveTokens(tokens);
}

export async function hasSession(): Promise<boolean> {
  return Boolean(await SecureStore.getItemAsync(ACCESS_KEY));
}
