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

type PanelMode = 'loading' | 'live' | 'demo';

const API_BASE = import.meta.env.VITE_REFLECTION_API_BASE || 'http://127.0.0.1:8780';
const FETCH_TIMEOUT_MS = 8_000;
const FALLBACK_SNAPSHOT: Snapshot = {
  metrics: {
    confidence_score: 0.91,
    contradiction_count: 1,
    canonical_count: 12
  },
  heatmap: Array.from({ length: 20 }).map((_, index) => ({
    hour: `${String((index + 8) % 24).padStart(2, '0')}:00`,
    count: (index % 5) + 1
  })),
  proposals: [
    { proposal_id: 'proposal-operator-1', change_type: 'policy_tune', target: 'approval_queue', confidence: 0.94 },
    { proposal_id: 'proposal-operator-2', change_type: 'triage_hint', target: 'risk_lane', confidence: 0.88 },
    { proposal_id: 'proposal-operator-3', change_type: 'drift_flag', target: 'ltp_review', confidence: 0.83 }
  ],
  action_timeline: [
    { timestamp: '2026-04-06T14:08:25Z', type: 'batch_ltp_review' },
    { timestamp: '2026-04-06T14:08:19Z', type: 'queue_snapshot' },
    { timestamp: '2026-04-06T14:08:10Z', type: 'approval_wait' }
  ]
};

function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const id = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  return fetch(url, { ...init, signal: controller.signal }).finally(() => window.clearTimeout(id));
}

function parseEditValue(raw: string): unknown {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  try {
    return JSON.parse(trimmed) as unknown;
  } catch {
    return trimmed;
  }
}

export default function RuntimeLivePanel() {
  const { t } = useTranslation();
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [mode, setMode] = useState<PanelMode>('loading');
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState('');

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
      setMode('live');
      setError(null);
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return;
      setSnapshot((current) => current ?? FALLBACK_SNAPSHOT);
      setMode((current) => (current === 'live' ? 'live' : 'demo'));
      setError(null);
    }
  };

  useEffect(() => {
    loadSnapshot();
    const timer = window.setInterval(loadSnapshot, 5000);
    return () => window.clearInterval(timer);
  }, []);

  const applyAction = async (
    action: 'approve' | 'reject' | 'edit',
    proposal: Proposal,
    idx: number,
    edit?: { proposedValue: unknown; note?: string }
  ) => {
    const busyKey = proposal.proposal_id ?? `__idx_${idx}`;
    if (mode === 'demo') {
      setSnapshot((current) => {
        if (!current) return current;
        const proposals = (current.proposals || []).filter((_, proposalIndex) => proposalIndex !== idx);
        const actionTimeline = [
          {
            timestamp: new Date().toISOString(),
            type:
              action === 'approve' ? 'demo_approve' : action === 'reject' ? 'demo_reject' : 'demo_edit'
          },
          ...(current.action_timeline || [])
        ].slice(0, 4);
        return {
          ...current,
          proposals,
          action_timeline: actionTimeline
        };
      });
      setEditingKey(null);
      return;
    }

    setBusyId(busyKey);
    try {
      const body: Record<string, unknown> = { action, proposal };
      if (action === 'edit') {
        if (edit?.proposedValue === undefined) {
          throw new Error('edit requires proposed_value');
        }
        body.proposed_value = edit.proposedValue;
        if (edit.note !== undefined) {
          body.note = edit.note;
        }
      }
      const response = await fetchWithTimeout(`${API_BASE}/api/reflection/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      await loadSnapshot();
      setEditingKey(null);
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="section" id="runtime-live">
      <div className="glass p-6 md:p-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold md:text-3xl">{t('runtimeLive.title')}</h2>
          <span className="rounded-full border border-white/20 bg-black/20 px-3 py-1 text-xs text-white/80">
            {mode === 'loading' ? t('runtimeLive.loading') : mode === 'live' ? t('runtimeLive.live') : t('runtimeLive.demo')}
          </span>
        </div>

        {error && (
          <p className="mb-4 text-sm text-rose-300">
            {t('runtimeLive.error')}: {error}
          </p>
        )}
        {mode === 'demo' && <p className="mb-4 text-sm text-cyan-200">{t('runtimeLive.offlineNote')}</p>}

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
                <li key={`${item.timestamp || 't'}-${idx}`}>
                  {item.type || 'unknown'} • {item.timestamp || '-'}
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-white/15 bg-black/20 p-4">
          <div className="mb-3 text-xs uppercase tracking-wider text-white/60">{t('runtimeLive.proposals')}</div>
          <div className="space-y-2">
            {topProposals.map((proposal, idx) => {
              const busyKey = proposal.proposal_id ?? `__idx_${idx}`;
              const isEditing = editingKey === busyKey;
              return (
                <div
                  key={proposal.proposal_id || `proposal-${idx}`}
                  className="flex flex-col gap-2 rounded-lg border border-white/10 px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-sm">
                      <span className="font-semibold">{proposal.proposal_id}</span>
                      <span className="text-white/70"> • {proposal.change_type} • {proposal.target}</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-white/70">conf {(proposal.confidence ?? 0).toFixed(2)}</span>
                      <button
                        type="button"
                        onClick={() => applyAction('approve', proposal, idx)}
                        disabled={busyId === busyKey}
                        className="rounded border border-emerald-300/40 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-300 disabled:opacity-50"
                      >
                        {t('runtimeLive.approve')}
                      </button>
                      <button
                        type="button"
                        onClick={() => applyAction('reject', proposal, idx)}
                        disabled={busyId === busyKey}
                        className="rounded border border-rose-300/40 bg-rose-400/10 px-2 py-1 text-xs text-rose-300 disabled:opacity-50"
                      >
                        {t('runtimeLive.reject')}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingKey(isEditing ? null : busyKey);
                          setEditDraft(
                            proposal.proposed_value !== undefined && proposal.proposed_value !== null
                              ? JSON.stringify(proposal.proposed_value)
                              : ''
                          );
                        }}
                        disabled={busyId === busyKey}
                        className="rounded border border-cyan-300/40 bg-cyan-400/10 px-2 py-1 text-xs text-cyan-200 disabled:opacity-50"
                      >
                        {t('runtimeLive.edit')}
                      </button>
                    </div>
                  </div>
                  {isEditing && (
                    <div className="flex flex-col gap-2 border-t border-white/10 pt-2 sm:flex-row sm:items-center">
                      <input
                        type="text"
                        value={editDraft}
                        onChange={(e) => setEditDraft(e.target.value)}
                        className="min-w-0 flex-1 rounded border border-white/20 bg-black/30 px-2 py-1 font-mono text-xs text-white"
                        placeholder={t('runtimeLive.editPlaceholder')}
                        aria-label={t('runtimeLive.editValueLabel')}
                      />
                      <button
                        type="button"
                        onClick={() => {
                          const parsed = parseEditValue(editDraft);
                          void applyAction('edit', proposal, idx, { proposedValue: parsed ?? null });
                        }}
                        disabled={busyId === busyKey}
                        className="rounded border border-cyan-300/50 bg-cyan-500/20 px-3 py-1 text-xs text-cyan-100 disabled:opacity-50"
                      >
                        {t('runtimeLive.saveEdit')}
                      </button>
                      <button
                        type="button"
                        onClick={() => setEditingKey(null)}
                        className="rounded border border-white/20 px-3 py-1 text-xs text-white/80"
                      >
                        {t('runtimeLive.cancelEdit')}
                      </button>
                    </div>
                  )}
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
