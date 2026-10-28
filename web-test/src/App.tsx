import { FormEvent, useMemo, useState } from 'react';
import { Route, Routes, useNavigate } from 'react-router-dom';
import { ApiClient, DiscoveredAccount, EnvironmentName, LogEntry, TokenPair } from './api';

const steps = ['Environment', 'Sign in', 'BVN discovery', 'Link accounts', 'Accounts inspector', 'Event log', 'Net position', 'Statements', 'Wipe'];
const urls: Record<EnvironmentName, string> = {
  local: import.meta.env.VITE_LOCAL_API_URL ?? 'http://127.0.0.1:8000',
  staging: import.meta.env.VITE_STAGING_API_URL ?? 'https://zenith-hackathon-project.vercel.app',
};

function Callback() {
  const navigate = useNavigate();
  return <main className="callback"><p className="eyebrow">Mono returned control</p><h1>Link received.</h1><p>The redirect is not proof that data is ready. Return to the console and keep polling the account status.</p><button onClick={() => navigate('/')}>Return to console</button></main>;
}

export function App() {
  return <Routes><Route path="/link/callback" element={<Callback />} /><Route path="*" element={<Console />} /></Routes>;
}

function Console() {
  const [environment, setEnvironment] = useState<EnvironmentName>('local');
  const [step, setStep] = useState(0);
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [drawer, setDrawer] = useState(false);
  const [notice, setNotice] = useState('Ready for a sandbox-only test run.');
  const baseUrl = urls[environment].replace(/\/$/, '');
  const client = useMemo(() => new ApiClient(baseUrl, () => accessToken, (entry) => setLogs((old) => [entry, ...old].slice(0, 80))), [baseUrl, accessToken]);
  const mock = import.meta.env.VITE_MOCK_MODE === 'true';
  const enabled = import.meta.env.VITE_CONSOLE_ENABLED === 'true';
  const denied = (import.meta.env.VITE_DENIED_HOSTS ?? '').split(',').map((x: string) => x.trim()).filter(Boolean);
  const host = new URL(baseUrl).host;
  const blocked = environment === 'staging' && (!baseUrl.startsWith('https://') || denied.includes(host));

  if (!enabled) return <main className="callback"><p className="eyebrow">Console disabled</p><h1>Access is closed.</h1><p>Set <code>VITE_CONSOLE_ENABLED=true</code> only on a Vercel deployment protected by authentication.</p></main>;

  return <div className="shell">
    <header className={`envbar ${environment}`}><div><span className="pulse" />{mock ? 'MOCK · ' : ''}{environment.toUpperCase()} <strong>{host}</strong></div><div>Sandbox test console. Do not use real accounts or real BVNs.</div></header>
    <aside className="rail"><div className="brand"><span>F</span><div>Fetch<small>integration lab</small></div></div><nav>{steps.map((name, index) => <button key={name} className={step === index ? 'active' : ''} onClick={() => setStep(index)}><b>{String(index + 1).padStart(2, '0')}</b><span>{name}</span></button>)}</nav><button className="tools" onClick={() => setDrawer(true)}>Open dev tools <kbd>⌘ K</kbd></button></aside>
    <main className="workspace"><div className="workspace-head"><div><p className="eyebrow">Journey {String(step + 1).padStart(2, '0')} / {steps.length}</p><h1>{steps[step]}</h1></div><div className="status"><span />{notice}</div></div>
      {blocked ? <Panel title="Environment blocked"><p>This staging target is not HTTPS or appears on the configured denylist.</p></Panel> : <Step step={step} environment={environment} setEnvironment={setEnvironment} client={client} setToken={setAccessToken} setNotice={setNotice} logs={logs} />}
    </main>
    {drawer && <DevDrawer environment={environment} baseUrl={baseUrl} logs={logs} token={accessToken} close={() => setDrawer(false)} reset={() => { sessionStorage.clear(); setAccessToken(null); setLogs([]); }} />}
  </div>;
}

type StepProps = { step: number; environment: EnvironmentName; setEnvironment: (v: EnvironmentName) => void; client: ApiClient; setToken: (v: string | null) => void; setNotice: (v: string) => void; logs: LogEntry[] };
function Step(props: StepProps) {
  if (props.step === 0) return <EnvironmentStep {...props} />;
  if (props.step === 1) return <SignInStep {...props} />;
  if (props.step === 2) return <DiscoveryStep {...props} />;
  if (props.step === 3) return <LinkStep {...props} />;
  if (props.step === 4) return <InspectorStep {...props} />;
  if (props.step === 5) return <EventStep logs={props.logs} />;
  if (props.step === 6) return <NetStep {...props} />;
  if (props.step === 7) return <StatementStep {...props} />;
  return <WipeStep {...props} />;
}

function Panel({ title, children, aside }: { title: string; children: React.ReactNode; aside?: React.ReactNode }) { return <section className="panel"><div className="panel-title"><h2>{title}</h2>{aside}</div>{children}</section>; }
function EnvironmentStep({ environment, setEnvironment, client, setNotice }: StepProps) {
  const [result, setResult] = useState<string>('Not checked');
  async function check() { try { const health = await client.request<{status: string; product: string}>('/health'); setResult(`${health.product} · ${health.status}`); setNotice('Backend reachable. Developer capability status is still unconfirmed.'); } catch (e) { setResult(e instanceof Error ? e.message : 'Failed'); } }
  return <><div className="split"><Panel title="Target"><div className="segmented"><button className={environment === 'local' ? 'selected' : ''} onClick={() => setEnvironment('local')}>Local</button><button className={environment === 'staging' ? 'selected' : ''} onClick={() => setEnvironment('staging')}>Staging</button></div><div className="metric"><span>Reachability</span><strong>{result}</strong></div><button onClick={() => void check()}>Run preflight</button></Panel><Panel title="Safety gate"><ul className="checks"><li>Production environment must be rejected</li><li>Mono keys remain server-side</li><li>Webhook registration is checked separately</li><li>Migration status awaits `/dev/status`</li></ul></Panel></div><p className="note">Unconfirmed: this backend does not yet expose APP_ENV, migration revision, Mono sandbox-key state, or webhook registration.</p></>;
}

function SignInStep({ client, setToken, setNotice }: StepProps) {
  const [identifier, setIdentifier] = useState(''); const [otp, setOtp] = useState(''); const [message, setMessage] = useState('');
  async function request(e: FormEvent) { e.preventDefault(); await client.request('/auth/otp/request', { method: 'POST', body: JSON.stringify(identifier.includes('@') ? { email: identifier } : { phone: identifier }) }); setMessage('Code requested. Use only the protected demo inbox configured for this environment.'); }
  async function verify() { const body = identifier.includes('@') ? { email: identifier, otp } : { phone: identifier, otp }; const pair = await client.request<TokenPair>('/auth/otp/verify', { method: 'POST', body: JSON.stringify(body) }); setToken(pair.access_token); sessionStorage.setItem('fetch.refresh-token', pair.refresh_token); setOtp(''); setNotice('Signed in. Access token is held in memory.'); }
  return <Panel title="Passwordless sign-in" aside={<span className="badge">6 digits · 5 min</span>}><form onSubmit={(e) => void request(e)} className="form"><label>Email or E.164 phone<input value={identifier} onChange={(e) => setIdentifier(e.target.value)} autoComplete="username" required /></label><button>Request code</button><label>One-time code<input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" /></label><button type="button" className="primary" disabled={otp.length !== 6} onClick={() => void verify()}>Verify and continue</button></form><p className="note">{message || 'Codes and tokens are redacted from the request inspector and never written to logs.'}</p></Panel>;
}

function DiscoveryStep({ client, setNotice }: StepProps) {
  const [bvn, setBvn] = useState(''); const [session, setSession] = useState(''); const [methods, setMethods] = useState<{method: string; hint: string}[]>([]); const [method, setMethod] = useState(''); const [otp, setOtp] = useState(''); const [accounts, setAccounts] = useState<DiscoveredAccount[]>([]);
  async function start() { const r = await client.request<{session_id: string; methods: {method: string; hint: string}[]}>('/onboarding/bvn/start', { method: 'POST', body: JSON.stringify({ bvn }) }); setSession(r.session_id); setMethods(r.methods); setBvn(''); setNotice('Lookup session started. It expires after 10 minutes.'); }
  async function send() { await client.request('/onboarding/bvn/send-otp', { method: 'POST', body: JSON.stringify({ session_id: session, method }) }); }
  async function confirm() { const r = await client.request<DiscoveredAccount[]>('/onboarding/bvn/confirm', { method: 'POST', body: JSON.stringify({ session_id: session, otp }) }); setAccounts(r); setOtp(''); }
  return <><Panel title="BVN Lookup" aside={<span className="badge warning">Billable outside sandbox</span>}><div className="form"><label>Test BVN<input value={bvn} onChange={(e) => setBvn(e.target.value.replace(/\D/g, '').slice(0, 11))} inputMode="numeric" /></label><button disabled={bvn.length !== 11} onClick={() => void start()}>Start discovery</button>{methods.length > 0 && <><label>OTP delivery channel<select value={method} onChange={(e) => setMethod(e.target.value)}><option value="">Choose one</option>{methods.map((m) => <option key={m.method} value={m.method}>{m.hint}</option>)}</select></label><button disabled={!method} onClick={() => void send()}>Send Lookup OTP</button><label>Lookup OTP<input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} /></label><button disabled={otp.length !== 6} onClick={() => void confirm()}>Confirm discovery</button></>}</div></Panel>{accounts.length > 0 && <Panel title="Discovered accounts"><div className="rows">{accounts.map((a) => <div className="row" key={a.id}><input type="checkbox" aria-label={`Select ${a.institution_name}`} /><div><strong>{a.institution_name}</strong><span>{a.account_name} · {a.account_type}</span></div><code>•••• {a.account_number_last4}</code></div>)}</div></Panel>}</>;
}

function LinkStep({ client, setNotice }: StepProps) { const [id, setId] = useState(''); const [state, setState] = useState('To link'); async function link() { setState('Linking'); const r = await client.request<{mono_url: string}>(`/accounts/discovered/${encodeURIComponent(id)}/link`, { method: 'POST' }); window.open(r.mono_url, '_blank', 'noopener,noreferrer'); setState('Processing'); setNotice('Mono opened in a new tab. Polling—not redirect—is authoritative.'); } return <Panel title="Hosted Mono Connect" aside={<span className="state">{state}</span>}><p>Paste a discovered account ID. Fetch opens Mono’s hosted page and never collects bank credentials.</p><div className="inline"><input value={id} onChange={(e) => setId(e.target.value)} placeholder="Discovered account UUID" /><button disabled={!id} onClick={() => void link()}>Open secure link ↗</button></div><div className="timeline"><span className="done">To link</span><span className={state !== 'To link' ? 'done' : ''}>Linking</span><span className={state === 'Processing' ? 'done' : ''}>Processing</span><span>Ready</span></div></Panel>; }
function InspectorStep({ client }: StepProps) { const [data, setData] = useState<unknown>(null); return <Panel title="Linked accounts" aside={<button onClick={() => void client.request('/accounts').then(setData)}>Refresh list</button>}><pre className="json">{data ? JSON.stringify(data, null, 2) : 'Load the authenticated account inventory.'}</pre><p className="note">Data calls must remain disabled until the account reports AVAILABLE or the requested resource is present under PARTIAL.</p></Panel>; }
function EventStep({ logs }: { logs: LogEntry[] }) { return <Panel title="Local request and transition log"><div className="events">{logs.length ? logs.map((x) => <div key={x.id}><time>{new Date(x.at).toLocaleTimeString()}</time><b>{x.method}</b><code>{x.path}</code><span>{x.status ?? '—'}</span></div>) : <p>No events in this browser session.</p>}</div><p className="note">Provider webhook history requires the proposed authenticated non-production backend endpoint.</p></Panel>; }
function NetStep({ client }: StepProps) { const [data, setData] = useState<unknown>(null); return <div className="split"><Panel title="Net position"><button onClick={() => void client.request('/net-position').then(setData)}>Load position</button><pre className="json">{data ? JSON.stringify(data, null, 2) : 'No data loaded.'}</pre></Panel><Panel title="Manual asset"><p>Asset creation will use the exact OpenAPI enum values in the generated client phase.</p><button disabled>Add asset</button></Panel></div>; }
function StatementStep({ client }: StepProps) { const [file, setFile] = useState<File | null>(null); const [result, setResult] = useState<unknown>(null); async function upload() { if (!file) return; const form = new FormData(); form.set('file', file); setResult(await client.request('/statements/upload', { method: 'POST', body: form })); } return <Panel title="Statement ingestion"><label className="drop"><input type="file" accept=".pdf,.csv,.xlsx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />{file ? file.name : 'Choose a PDF, CSV, or XLSX test statement'}</label><button disabled={!file} onClick={() => void upload()}>Upload to unified ledger</button><pre className="json">{result ? JSON.stringify(result, null, 2) : ''}</pre></Panel>; }
function WipeStep({ client, setToken }: StepProps) { const [otp, setOtp] = useState(''); return <Panel title="Irreversible test-data wipe" aside={<span className="badge danger">Destructive</span>}><p>Request a fresh login OTP, then delete all Fetch data and queue remote unlink retries.</p><label>Fresh OTP<input value={otp} onChange={(e) => setOtp(e.target.value.replace(/\D/g, '').slice(0, 6))} /></label><button className="danger-button" disabled={otp.length !== 6} onClick={() => void client.request('/privacy/wipe', { method: 'POST', body: JSON.stringify({ otp }) }).then(() => { setToken(null); sessionStorage.clear(); })}>Wipe this test user</button></Panel>; }

function DevDrawer({ environment, baseUrl, logs, token, close, reset }: { environment: string; baseUrl: string; logs: LogEntry[]; token: string | null; close: () => void; reset: () => void }) { return <div className="scrim" onMouseDown={close}><aside className="drawer" onMouseDown={(e) => e.stopPropagation()}><div className="panel-title"><div><p className="eyebrow">Developer tools</p><h2>Request inspector</h2></div><button onClick={close}>Close</button></div><dl><dt>Environment</dt><dd>{environment}</dd><dt>API</dt><dd>{baseUrl}</dd><dt>Access token</dt><dd>{token ? 'In memory · active' : 'None'}</dd></dl><div className="logbody">{logs.map((x) => <details key={x.id}><summary>{x.method} {x.path} <b>{x.status ?? 'ERR'}</b></summary><pre>{JSON.stringify(x.body, null, 2)}</pre></details>)}</div><button className="danger-button" onClick={reset}>Reset local state</button></aside></div>; }
