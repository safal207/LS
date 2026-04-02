import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type Proposal = {
  proposal_id?: string;
  change_type?: string;
  target?: string;
  confidence?: number;
  proposed_value?: unknown;
};

type Snapshot = {
  metrics?: { confidence_score?: number; contradiction_count?: number; canonical_count?: number };
  heatmap?: Array<{ hour: string; count: number }>;
  proposals?: Proposal[];
  action_timeline?: Array<{ timestamp?: string; type?: string }>;
};

// BUG-RT-01: Fall back to localhost dev server when env var is missing to avoid
// fetch('/api/...') hitting the landing-page origin instead of the API server.
const API_BASE = import.meta.env.VITE_REFLECTION_API_BASE || 'http://127.0.0.1:8780';

const FETCH_TIMEOUT_MS = 8_000;

/** Wrapper that aborts a fetch after FETCH_TIMEOUT_MS. */
function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
  // BUG-RT-02: All fetch calls now have an AbortController so stale requests
  // don't keep running after the component unmounts or a new poll fires.
  const controller = new AbortController();
  const id = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  return fetch(url, { ...init, signal: controller.signal }).finally(() =>
    window.clearTimeout(id)
  );
}

export default function RuntimeLivePanel() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // BUG-RT-03: busyId was set to empty string '' for proposals without an id,
  // which collided: ALL id-less proposals were disabled at once. Use a unique
  // per-render index string so each button is independently guarded.
  const [busyId, setBusyId] = useState<string | null>(null);

  const topProposals = useMemo(() => (snapshot?.proposals || []).slice(0, 3), [snapshot]);

  const loadSnapshot = async () => {
    try {
      const response = await fetchWithTimeout(
        `${API_BASE}/api/reflection/snapshot?recent_limit=5&timeline_limit=5`
      );
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = (await response.json()) as Snapshot;
      setSnapshot(data);
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return; // timeout — skip UI update
      setError(err instanceof Error ? err.message : 'snapshot_fetch_failed');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSnapshot();
    const timer = window.setInterval(loadSnapshot, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const applyAction = async (action: 'approve' | 'reject', proposal: Proposal, idx: number) => {
    // BUG-RT-03: Use proposal_id when present, else a stable index-based key.
    const busyKey = proposal.proposal_id ?? `__idx_${idx}`;
    setBusyId(busyKey);
    try {
      const response = await fetchWithTimeout(`${API_BASE}/api/reflection/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, proposal })
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await loadSnapshot();
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="section">
      <div className="glass p-6 md:p-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold md:text-3xl">{t('runtimeLive.title')}</h2>
          <span className="rounded-full border border-white/20 bg-black/20 px-3 py-1 text-xs text-white/80">
            {loading ? t('runtimeLive.loading') : t('runtimeLive.live')}
          </span>
        </div>

        {error && <p className="mb-4 text-sm text-rose-300">{t('runtimeLive.error')}: {error}</p>}

        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-white/15 bg-black/20 p-4">
            <div className="text-xs uppercase tracking-wider text-white/60">{t('runtimeLive.metrics')}</div>
            <p className="mt-3 text-sm">confidence: {(snapshot?.metrics?.confidence_score ?? 0).toFixed(2)}</p>
            <p className="mt-1 text-sm">canonical: {snapshot?.metrics?.canonical_count ?? 0}</p>
            <p className="mt-1 text-sm">contradictions: {snapshot?.metrics?.contradiction_count ?? 0}</p>
          </div>

          <div className="rounded-xl border border-white/15 bg-black/20 p-4">
            <div className="text-xs uppercase tracking-wider text-white/60">{t('runtimeLive.heatmap')}</div>
            <div className="mt-3 grid grid-cols-10 gap-1">
              {(snapshot?.heatmap || []).slice(-20).map((cell) => (
                <span
                  key={cell.hour}
                  className="h-2 rounded-sm"
                  style={{ background: `rgba(116,247,255,${Math.min(0.15 + cell.count * 0.1, 0.95)})` }}
                  title={`${cell.hour}: ${cell.count}`}
                />
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-white/15 bg-black/20 p-4">
            <div className="text-xs uppercase tracking-wider text-white/60">{t('runtimeLive.timeline')}</div>
            <ul className="mt-3 space-y-1 text-xs text-white/80">
              {(snapshot?.action_timeline || []).slice(0, 4).map((item, idx) => (
                <li key={`${item.timestamp || 't'}-${idx}`}>{item.type || 'unknown'} · {item.timestamp || '-'}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-white/15 bg-black/20 p-4">
          <div className="mb-3 text-xs uppercase tracking-wider text-white/60">{t('runtimeLive.proposals')}</div>
          <div className="space-y-2">
            {topProposals.map((proposal, idx) => {
              const busyKey = proposal.proposal_id ?? `__idx_${idx}`;
              return (
              <div key={proposal.proposal_id || `proposal-${idx}`} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 px-3 py-2">
                <div className="text-sm">
                  <span className="font-semibold">{proposal.proposal_id}</span>
                  <span className="text-white/70"> · {proposal.change_type} · {proposal.target}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-white/70">conf {(proposal.confidence ?? 0).toFixed(2)}</span>
                  <button
                    onClick={() => applyAction('approve', proposal, idx)}
                    disabled={busyId === busyKey}
                    className="rounded border border-emerald-300/40 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-300 disabled:opacity-50"
                  >
                    {t('runtimeLive.approve')}
                  </button>
                  <button
                    onClick={() => applyAction('reject', proposal, idx)}
                    disabled={busyId === busyKey}
                    className="rounded border border-rose-300/40 bg-rose-400/10 px-2 py-1 text-xs text-rose-300 disabled:opacity-50"
                  >
                    {t('runtimeLive.reject')}
                  </button>
                </div>
              </div>
              );
            })}
            {topProposals.length === 0 && <p className="text-sm text-white/70">{t('runtimeLive.noProposals')}</p>}
          </div>
        </div>
      </div>
    </section>
  );
}
