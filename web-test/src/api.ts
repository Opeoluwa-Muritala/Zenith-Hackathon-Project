export type EnvironmentName = 'local' | 'staging';
export type LogEntry = { id: string; at: string; method: string; path: string; status?: number; body?: unknown };
export type TokenPair = { access_token: string; refresh_token: string; token_type: 'bearer' };
export type DiscoveredAccount = { id: string; account_name: string; account_type: string; account_number_last4: string; institution_name: string; status: string };

const sensitive = /token|authorization|otp|bvn|account_number|secret|password/i;
export function redact(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(redact);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, sensitive.test(k) ? '[REDACTED]' : redact(v)]));
  return value;
}

export class ApiClient {
  constructor(private baseUrl: string, private token: () => string | null, private onLog: (entry: LogEntry) => void) {}
  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = init.method ?? 'GET';
    const headers = new Headers(init.headers);
    headers.set('Accept', 'application/json');
    if (init.body && !(init.body instanceof FormData)) headers.set('Content-Type', 'application/json');
    const token = this.token();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const id = crypto.randomUUID();
    const started = new Date().toISOString();
    try {
      const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
      const text = await response.text();
      const data = text ? (JSON.parse(text) as unknown) : null;
      this.onLog({ id, at: started, method, path, status: response.status, body: redact(data) });
      if (!response.ok) throw new Error(typeof data === 'object' && data && 'detail' in data ? String(data.detail) : `HTTP ${response.status}`);
      return data as T;
    } catch (error) {
      this.onLog({ id, at: started, method, path, body: { error: error instanceof Error ? error.message : 'Request failed' } });
      throw error;
    }
  }
}
