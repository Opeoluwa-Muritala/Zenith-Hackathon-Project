import { useCallback, useEffect, useState } from 'react';
import {
  ActivityIndicator, Alert, Linking, Pressable, RefreshControl, SafeAreaView,
  ScrollView, StatusBar, StyleSheet, Text, TextInput, View,
} from 'react-native';
import { api, type Account, type Consent, type Insight, type Overview, type Recurring, type Transaction, hasSession, persistSession } from './src/api';

const COLORS = { ink: '#1E3028', muted: '#708078', canvas: '#F4F6F2', paper: '#FFFFFF', green: '#1E6B4A', pale: '#E4F0E9', line: '#E4EAE5', amber: '#8A5C00', danger: '#B53A32' };
const tabs = ['Home', 'Insights', 'Activity', 'Bills', 'Accounts'] as const;
type Tab = typeof tabs[number];
type ScreenData = { overview: Overview | null; forecast: Record<string, unknown> | null; insights: Insight[]; transactions: Transaction[]; recurring: Recurring[]; accounts: Account[]; consents: Consent[] };
const emptyData: ScreenData = { overview: null, forecast: null, insights: [], transactions: [], recurring: [], accounts: [], consents: [] };
const moduleLabels: Record<string, string> = { cashflow: 'Cashflow', leaks: 'Subscriptions & bills', behaviour: 'Spending behaviour', wealth: 'Building wealth' };

function naira(minor: number | unknown): string {
  if (typeof minor !== 'number' || !Number.isFinite(minor)) return '—';
  return `₦${(minor / 100).toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function App() {
  const [phone, setPhone] = useState('+234');
  const [otp, setOtp] = useState('');
  const [otpRequested, setOtpRequested] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);
  const [tab, setTab] = useState<Tab>('Home');
  const [data, setData] = useState<ScreenData>(emptyData);
  const [forecast, setForecast] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [identityVerified, setIdentityVerified] = useState(false);
  const [bvn, setBvn] = useState('');
  const [email, setEmail] = useState('');
  const [customerName, setCustomerName] = useState('Demo Customer');
  const [institution, setInstitution] = useState('DEMO-A');
  const [consentInstitution, setConsentInstitution] = useState('DEMO-A');
  const [pendingMonoRef, setPendingMonoRef] = useState('');
  const [monoStatus, setMonoStatus] = useState('');

  const refresh = useCallback(async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    setError('');
    try {
      const [overview, safe, insights, transactions, recurring, accounts, consents] = await Promise.all([
        api.overview(), api.forecast(), api.insights(), api.transactions(), api.recurring(), api.accounts(), api.consents(),
      ]);
      setData({ overview, forecast: safe, insights, transactions, recurring, accounts, consents });
      setForecast(safe);
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Could not refresh data.';
      setError(message);
      if (message.includes('Session expired')) {
        setAuthenticated(false);
      }
    } finally { setRefreshing(false); }
  }, []);

  useEffect(() => {
    hasSession().then((active) => { if (active) setAuthenticated(true); });
  }, []);
  useEffect(() => { if (authenticated) void refresh(true); }, [authenticated, refresh]);

  async function run(action: () => Promise<unknown>, success?: string) {
    setBusy(true); setError('');
    try {
      await action();
      if (success) Alert.alert('Done', success);
      await refresh(true);
    } catch (e) { setError(e instanceof Error ? e.message : 'That action could not be completed.'); }
    finally { setBusy(false); }
  }

  async function requestOtp() {
    setBusy(true); setError('');
    try { await api.requestOtp(phone.trim()); setOtpRequested(true); }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not request code.'); }
    finally { setBusy(false); }
  }

  async function signIn() {
    setBusy(true); setError('');
    try { const tokens = await api.verifyOtp(phone.trim(), otp.trim()); await persistSession(tokens); setAuthenticated(true); }
    catch (e) { setError(e instanceof Error ? e.message : 'Sign in failed.'); }
    finally { setBusy(false); }
  }

  async function createDemoConsentAndLink(institutionCode: string) {
    setBusy(true); setError('');
    try {
      const code = institutionCode.trim();
      const consent = await api.createConsent(code);
      await api.linkDemo(consent.id, code);
      await api.sync();
      await refresh(true);
      Alert.alert('Demo account connected', 'Its transactions are now included in your overview.');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not link demo account.'); }
    finally { setBusy(false); }
  }

  async function connectMono() {
    setBusy(true); setError(''); setMonoStatus('Starting secure bank connection…');
    try {
      const consent = await api.createConsent(consentInstitution.trim());
      const link = await api.initiateMonoLink(consent.id, customerName.trim(), email.trim());
      const hosted = new URL(link.url);
      if (hosted.protocol !== 'https:' || hosted.hostname !== 'link.mono.co') {
        throw new Error('The backend returned an unexpected bank-link URL. It was not opened.');
      }
      setPendingMonoRef(link.ref);
      setMonoStatus('Waiting for bank authorisation. Return here and check status after connecting.');
      await Linking.openURL(hosted.toString());
    } catch (e) { setMonoStatus(''); setError(e instanceof Error ? e.message : 'Could not start bank connection.'); }
    finally { setBusy(false); }
  }

  async function checkMonoStatus() {
    if (!pendingMonoRef) return;
    setBusy(true); setError('');
    try {
      const result = await api.monoLinkStatus(pendingMonoRef);
      setMonoStatus(`Bank connection: ${result.status}${result.data_status ? ` · ${result.data_status}` : ''}`);
      if (result.status === 'connected') { await api.sync(); await refresh(true); setPendingMonoRef(''); }
      else if (result.status === 'failed' || result.status === 'unlinked') setPendingMonoRef('');
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not check connection status.'); }
    finally { setBusy(false); }
  }

  async function revoke(consent: Consent) {
    Alert.alert('Revoke consent?', `Data from ${consent.institution} will stop appearing after refresh.`, [
      { text: 'Keep', style: 'cancel' },
      { text: 'Revoke', style: 'destructive', onPress: () => void run(() => api.revoke(consent.id), 'Consent revoked.') },
    ]);
  }

  if (!authenticated) {
    return <SafeAreaView style={styles.safe}>
      <StatusBar barStyle="dark-content" backgroundColor={COLORS.canvas} />
      <ScrollView contentContainerStyle={styles.login} keyboardShouldPersistTaps="handled">
        <Brand />
        <Text style={styles.title}>One clear view of your money.</Text>
        <Text style={styles.muted}>Sign in with the phone number used for your demo data.</Text>
        <Field label="Phone number" value={phone} onChangeText={setPhone} placeholder="+2348012345678" keyboardType="phone-pad" />
        {otpRequested && <>
          <Field label="One-time code" value={otp} onChangeText={setOtp} placeholder="6-digit code" keyboardType="number-pad" maxLength={6} />
          <Text style={styles.hint}>Local development has no SMS sender. Use the backend's configured DEV_OTP (default: 123456).</Text>
        </>}
        <Button title={otpRequested ? 'Verify and continue' : 'Request code'} onPress={() => void (otpRequested ? signIn() : requestOtp())} disabled={busy || phone.length < 9 || (otpRequested && otp.length !== 6)} />
        {busy && <ActivityIndicator color={COLORS.green} style={styles.spinner} />}
        {!!error && <ErrorBox text={error} />}
        <Text style={styles.footnote}>Your Mono secret key stays on the backend. Session tokens are stored in the device's secure storage.</Text>
      </ScrollView>
    </SafeAreaView>;
  }

  return <SafeAreaView style={styles.safe}>
    <StatusBar barStyle="dark-content" backgroundColor={COLORS.canvas} />
    <View style={styles.topbar}><Brand /><Pressable accessibilityRole="button" accessibilityLabel="Refresh data" onPress={() => void refresh()} style={styles.refresh}><Text style={styles.refreshText}>Refresh</Text></Pressable></View>
    {!!error && <ErrorBox text={error} />}
    <ScrollView contentContainerStyle={styles.content} refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void refresh()} tintColor={COLORS.green} />}>
      {tab === 'Home' && <>
        <Text style={styles.greeting}>Your money, in one place.</Text>
        {data.overview ? <>
          <View style={styles.hero}><Text style={styles.heroLabel}>Safe to spend daily</Text><Text style={styles.heroValue}>{naira(forecast?.daily_allowance_minor)}</Text><Text style={styles.heroCaption}>{String(forecast?.status ?? 'Refresh after connecting an account')}</Text></View>
          <View style={styles.metrics}><Metric label="Income · 30 days" value={naira(data.overview.income_minor)} /><Metric label="Spend · 30 days" value={naira(data.overview.spend_minor)} /></View>
          <Metric label="Total balance" value={naira(data.overview.total_balance_minor)} detail="Across active, consented accounts" />
        </> : <Empty title="No finance data yet" message="Connect a demo account below, then sync to see your overview." />}
        <Section title="Top insights" action="See all" onAction={() => setTab('Insights')} />
        {data.insights.slice(0, 2).map((item) => <InsightCard key={item.id} item={item} />)}
        {!data.insights.length && <Empty title="No active insights" message="Insights appear after transactions have been synced." />}
        {!identityVerified && <Card><Text style={styles.cardTitle}>Verify demo identity</Text><Text style={styles.muted}>BVN is used for identity verification only; do not enter a real person's BVN in a demo.</Text><Field label="Synthetic test BVN" value={bvn} onChangeText={setBvn} keyboardType="number-pad" maxLength={11} placeholder="11 digits" /><Button title="Verify identity" onPress={() => void run(async () => { await api.verifyIdentity(bvn); setIdentityVerified(true); }, 'Demo identity verified.')} disabled={busy || bvn.length !== 11} /></Card>}
        <Card><Text style={styles.cardTitle}>Connect a bank with Mono</Text><Text style={styles.muted}>Your consent is recorded by cashlens. Mono handles the bank authorisation in its hosted flow; return here to check the webhook status.</Text><Field label="Name for bank authorisation" value={customerName} onChangeText={setCustomerName} /><Field label="Email for bank authorisation" value={email} onChangeText={setEmail} keyboardType="email-address" placeholder="demo@example.test" /><Field label="Consent institution label" value={consentInstitution} onChangeText={setConsentInstitution} placeholder="Your bank name" /><Button title="Connect your bank" onPress={() => void connectMono()} disabled={busy || !customerName.trim() || !email.includes('@') || !consentInstitution.trim()} />{!!pendingMonoRef && <Button title="Check connection status" onPress={() => void checkMonoStatus()} disabled={busy} />}{!!monoStatus && <Text accessibilityLiveRegion="polite" style={styles.hint}>{monoStatus}</Text>}</Card>
        <Card><Text style={styles.cardTitle}>Use demo accounts</Text><Text style={styles.muted}>Creates consent, links a mock institution and syncs sample ledger data.</Text><Field label="Demo institution code" value={institution} onChangeText={setInstitution} placeholder="DEMO-A" /><Button title="Use demo account" onPress={() => void createDemoConsentAndLink(institution)} disabled={busy || !institution.trim()} /></Card>
      </>}
      {tab === 'Insights' && <><Text style={styles.title}>Insights</Text>{['cashflow', 'leaks', 'behaviour', 'wealth'].map((module) => <View key={module}><Section title={moduleLabels[module]} />{data.insights.filter((i) => i.module === module).map((item) => <InsightCard key={item.id} item={item} onDismiss={() => void run(() => api.dismissInsight(item.id))} />)}</View>)}{!data.insights.length && <Empty title="Nothing to show yet" message="Sync an account to run the insight checks." />}</>}
      {tab === 'Activity' && <><Text style={styles.title}>Transactions</Text>{data.transactions.map((tx) => <Card key={tx.id}><View style={styles.row}><View style={{ flex: 1 }}><Text style={styles.cardTitle}>{tx.narration || tx.category}</Text><Text style={styles.muted}>{tx.category} · {new Date(tx.posted_at).toLocaleDateString()}</Text></View><Text style={[styles.amount, tx.direction === 'credit' && styles.credit]}>{tx.direction === 'credit' ? '+' : '−'}{naira(tx.amount_minor)}</Text></View></Card>)}{!data.transactions.length && <Empty title="No transactions" message="Connect and sync an account to load recent activity." />}</>}
      {tab === 'Bills' && <><Text style={styles.title}>Subscriptions & bills</Text>{data.recurring.map((item) => <Card key={item.id}><Text style={styles.cardTitle}>{item.status === 'active' ? 'Active recurring payment' : item.status}</Text><View style={styles.row}><Text style={styles.muted}>Next expected</Text><Text>{new Date(item.next_expected_at).toLocaleDateString()}</Text></View><View style={styles.row}><Text style={styles.muted}>Amount</Text><Text>{naira(item.amount_minor)}</Text></View><View style={styles.row}><Text style={styles.muted}>Annualised</Text><Text>{naira(item.annualised_minor)}</Text></View></Card>)}{!data.recurring.length && <Empty title="No recurring charges yet" message="Recurring bills are detected after enough transaction history is available." />}</>}
      {tab === 'Accounts' && <><Text style={styles.title}>Accounts & consent</Text>{data.accounts.map((account) => <Card key={account.id}><Text style={styles.cardTitle}>{account.type} account</Text><Text style={styles.muted}>{account.account_number_masked} · {account.currency}</Text><Text style={styles.amount}>{naira(account.balance_minor)}</Text></Card>)}{data.consents.map((consent) => <Card key={consent.id}><View style={styles.row}><View style={{ flex: 1 }}><Text style={styles.cardTitle}>{consent.institution}</Text><Text style={styles.muted}>{consent.revoked_at ? 'Revoked' : consent.scope}</Text></View>{!consent.revoked_at && <Pressable accessibilityRole="button" onPress={() => revoke(consent)} style={styles.revoke}><Text style={styles.revokeText}>Revoke</Text></Pressable>}</View></Card>)}{!data.accounts.length && !data.consents.length && <Empty title="No linked accounts" message="Use the demo account action on Home to add sample data." />}</>}
    </ScrollView>
    <View style={styles.nav}>{tabs.map((item) => <Pressable key={item} accessibilityRole="tab" accessibilityState={{ selected: tab === item }} onPress={() => setTab(item)} style={[styles.navItem, tab === item && styles.navActive]}><Text style={[styles.navLabel, tab === item && styles.navLabelActive]}>{item}</Text></Pressable>)}<Pressable accessibilityRole="button" accessibilityLabel="Sign out" onPress={() => { void api.logout().finally(() => { setAuthenticated(false); setData(emptyData); }); }} style={styles.signout}><Text style={styles.signoutText}>Sign out</Text></Pressable></View>
  </SafeAreaView>;
}

function Brand() { return <View style={styles.brand}><View style={styles.brandMark}><Text style={styles.brandMarkText}>c</Text></View><Text style={styles.brandName}>cashlens</Text></View>; }
function Field(props: { label: string; value: string; onChangeText: (value: string) => void; placeholder?: string; keyboardType?: 'default' | 'number-pad' | 'phone-pad' | 'email-address'; maxLength?: number }) { return <View style={styles.fieldWrap}><Text style={styles.fieldLabel}>{props.label}</Text><TextInput accessibilityLabel={props.label} style={styles.input} value={props.value} onChangeText={props.onChangeText} placeholder={props.placeholder} placeholderTextColor="#89958E" keyboardType={props.keyboardType ?? 'default'} maxLength={props.maxLength} autoCapitalize="none" /></View>; }
function Button({ title, onPress, disabled = false }: { title: string; onPress: () => void; disabled?: boolean }) { return <Pressable accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.button, disabled && styles.disabled]}><Text style={styles.buttonText}>{title}</Text></Pressable>; }
function Card({ children }: { children: React.ReactNode }) { return <View style={styles.card}>{children}</View>; }
function Metric({ label, value, detail }: { label: string; value: string; detail?: string }) { return <Card><Text style={styles.metricLabel}>{label}</Text><Text style={styles.metricValue}>{value}</Text>{detail && <Text style={styles.muted}>{detail}</Text>}</Card>; }
function Section({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) { return <View style={styles.section}><Text style={styles.sectionTitle}>{title}</Text>{action && <Pressable accessibilityRole="button" onPress={onAction} style={styles.touch}><Text style={styles.link}>{action}</Text></Pressable>}</View>; }
function InsightCard({ item, onDismiss }: { item: Insight; onDismiss?: () => void }) { return <Card><Text style={styles.badge}>{moduleLabels[item.module] ?? item.module} · {item.severity}</Text><Text style={styles.cardTitle}>{item.title}</Text><Text style={styles.body}>{item.body}</Text>{item.wording_source === 'ai' && <Text style={styles.aiLabel}>AI-worded</Text>}{item.footer && <Text style={styles.footer}>{item.footer}</Text>}{onDismiss && <Pressable accessibilityRole="button" onPress={onDismiss} style={styles.touch}><Text style={styles.link}>Dismiss insight</Text></Pressable>}</Card>; }
function Empty({ title, message }: { title: string; message: string }) { return <View style={styles.empty}><Text style={styles.cardTitle}>{title}</Text><Text style={styles.muted}>{message}</Text></View>; }
function ErrorBox({ text }: { text: string }) { return <View accessibilityRole="alert" style={styles.error}><Text style={styles.errorText}>{text}</Text></View>; }

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: COLORS.canvas },
  topbar: { minHeight: 60, paddingHorizontal: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { flexDirection: 'row', alignItems: 'center', gap: 9 }, brandMark: { width: 32, height: 32, borderRadius: 10, backgroundColor: COLORS.green, alignItems: 'center', justifyContent: 'center' }, brandMarkText: { color: '#fff', fontSize: 22, fontWeight: '800' }, brandName: { color: COLORS.ink, fontSize: 19, fontWeight: '800', letterSpacing: -0.5 },
  refresh: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 }, refreshText: { color: COLORS.green, fontWeight: '700' },
  content: { padding: 18, paddingBottom: 30, gap: 13 }, login: { flexGrow: 1, justifyContent: 'center', padding: 24, gap: 14 },
  title: { marginTop: 8, color: COLORS.ink, fontSize: 27, fontWeight: '800', letterSpacing: -0.7 }, greeting: { color: COLORS.ink, fontSize: 24, lineHeight: 31, fontWeight: '800', marginVertical: 8 },
  muted: { color: COLORS.muted, fontSize: 14, lineHeight: 21 }, hint: { color: COLORS.green, fontSize: 13, lineHeight: 19 }, footnote: { marginTop: 22, color: COLORS.muted, fontSize: 12, lineHeight: 18 },
  fieldWrap: { gap: 7, marginTop: 4 }, fieldLabel: { color: COLORS.ink, fontSize: 13, fontWeight: '700' }, input: { minHeight: 48, borderWidth: 1, borderColor: '#CBD7D0', borderRadius: 12, paddingHorizontal: 13, backgroundColor: COLORS.paper, color: COLORS.ink, fontSize: 16 },
  button: { minHeight: 50, borderRadius: 13, backgroundColor: COLORS.green, alignItems: 'center', justifyContent: 'center', marginTop: 5 }, buttonText: { color: '#fff', fontSize: 15, fontWeight: '750' }, disabled: { opacity: 0.5 }, spinner: { margin: 8 },
  hero: { backgroundColor: COLORS.green, borderRadius: 20, padding: 20, minHeight: 158, justifyContent: 'center' }, heroLabel: { color: '#D5EADF', fontWeight: '650', fontSize: 14 }, heroValue: { color: '#fff', fontWeight: '850', fontSize: 34, marginTop: 7 }, heroCaption: { color: '#D5EADF', fontSize: 13, marginTop: 3, textTransform: 'capitalize' },
  metrics: { flexDirection: 'row', gap: 10 }, card: { backgroundColor: COLORS.paper, borderRadius: 16, borderWidth: 1, borderColor: COLORS.line, padding: 16, gap: 9 }, metricLabel: { color: COLORS.muted, fontSize: 13, fontWeight: '650' }, metricValue: { color: COLORS.ink, fontSize: 23, fontWeight: '800' }, amount: { color: COLORS.ink, fontSize: 16, fontWeight: '750' }, credit: { color: COLORS.green },
  section: { marginTop: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }, sectionTitle: { color: COLORS.ink, fontSize: 18, fontWeight: '750' }, touch: { minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8 }, link: { color: COLORS.green, fontWeight: '700', fontSize: 13 }, cardTitle: { color: COLORS.ink, fontSize: 16, fontWeight: '750' }, body: { color: '#43554C', fontSize: 14, lineHeight: 21 }, badge: { color: COLORS.green, fontSize: 11, fontWeight: '750', textTransform: 'uppercase', letterSpacing: 0.4 }, aiLabel: { color: COLORS.green, fontWeight: '700', fontSize: 12 }, footer: { color: COLORS.muted, fontSize: 12, lineHeight: 17 },
  row: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 }, empty: { borderWidth: 1, borderColor: COLORS.line, borderStyle: 'dashed', borderRadius: 14, padding: 18, gap: 6 }, error: { marginHorizontal: 16, marginTop: 5, padding: 12, backgroundColor: '#FCEBE8', borderRadius: 10 }, errorText: { color: COLORS.danger, fontSize: 13, lineHeight: 18 },
  nav: { flexDirection: 'row', alignItems: 'center', borderTopWidth: 1, borderTopColor: COLORS.line, backgroundColor: COLORS.paper, paddingHorizontal: 4, minHeight: 58 }, navItem: { minHeight: 48, flex: 1, alignItems: 'center', justifyContent: 'center', borderRadius: 10 }, navActive: { backgroundColor: COLORS.pale }, navLabel: { color: COLORS.muted, fontSize: 10, fontWeight: '650' }, navLabelActive: { color: COLORS.green }, signout: { minHeight: 48, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 }, signoutText: { fontSize: 10, color: COLORS.danger, fontWeight: '650' }, revoke: { minHeight: 44, justifyContent: 'center', paddingHorizontal: 8 }, revokeText: { color: COLORS.danger, fontSize: 13, fontWeight: '700' },
});
