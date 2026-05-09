import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

type HcpItemRow = {
  item_id: string;
  title: string;
  description?: string;
  price_credits: number;
  plugin_id?: string;
};

type PanelMode = 'loading' | 'live' | 'demo';

const API_BASE = import.meta.env.VITE_HCP_API_BASE || 'http://127.0.0.1:8781';
const FETCH_TIMEOUT_MS = 2_500;
const INSTANCE_STORAGE_KEY = 'hcp-instance-id';

const FALLBACK_ITEMS: HcpItemRow[] = [
  {
    item_id: 'hcp-runtime-echo',
    title: 'Проверочный модуль ответа',
    description: 'Демо-модуль для проверки установки.',
    price_credits: 5
  },
  {
    item_id: 'hcp-safety-pack',
    title: 'Набор для проверки безопасности',
    price_credits: 50
  }
];

function fetchWithTimeout(url: string, init?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const id = window.setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  return fetch(url, { ...init, signal: controller.signal }).finally(() => window.clearTimeout(id));
}

export default function HcpMarketplacePanel() {
  const { t } = useTranslation();
  const [items, setItems] = useState<HcpItemRow[]>([]);
  const [credits, setCredits] = useState<number | null>(null);
  const [mode, setMode] = useState<PanelMode>('loading');
  const [error, setError] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<'attached' | 'detached' | 'unknown'>('unknown');
  const [busy, setBusy] = useState<string | null>(null);
  const [instanceId, setInstanceId] = useState(() => {
    try {
      return localStorage.getItem(INSTANCE_STORAGE_KEY) || 'landing-demo';
    } catch {
      return 'landing-demo';
    }
  });

  const displayItems = useMemo(() => items.slice(0, 6), [items]);

  const persistInstance = (v: string) => {
    const next = v.trim() || 'landing-demo';
    setInstanceId(next);
    try {
      localStorage.setItem(INSTANCE_STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  };

  const loadData = useCallback(async () => {
    try {
      const [itemsRes, credRes, rtRes] = await Promise.all([
        fetchWithTimeout(`${API_BASE}/api/hcp/items`),
        fetchWithTimeout(`${API_BASE}/api/hcp/credits?instance=${encodeURIComponent(instanceId)}`),
        fetchWithTimeout(`${API_BASE}/api/hcp/runtime`)
      ]);
      if (!itemsRes.ok) throw new Error(`items ${itemsRes.status}`);
      const itemsJson = (await itemsRes.json()) as { items?: HcpItemRow[] };
      const list = itemsJson.items || [];
      setItems(list.length ? list : FALLBACK_ITEMS);
      if (credRes.ok) {
        const c = (await credRes.json()) as { credits?: number };
        setCredits(typeof c.credits === 'number' ? c.credits : null);
      } else {
        setCredits(null);
      }
      if (rtRes.ok) {
        const r = (await rtRes.json()) as { runtime?: string };
        setRuntime(r.runtime === 'attached' ? 'attached' : 'detached');
      } else {
        setRuntime('unknown');
      }
      setMode('live');
      setError(null);
    } catch (e) {
      setItems(FALLBACK_ITEMS);
      setCredits(1000);
      setRuntime('unknown');
      setMode('demo');
      setError(null);
    }
  }, [instanceId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const post = async (action: 'purchase' | 'install' | 'load', body: Record<string, string>) => {
    const path = `/api/hcp/${action === 'purchase' ? 'purchase' : action === 'install' ? 'install' : 'load'}`;
    setBusy(`${action}-${body.item_id}`);
    try {
      const res = await fetchWithTimeout(`${API_BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ item_id: body.item_id, instance_id: body.instance_id })
      });
      const data = (await res.json()) as { status?: string; error?: string; credits?: number; hint?: string };
      if (!res.ok) {
        setError(data.error || `HTTP ${res.status}`);
        return;
      }
      if (data.credits != null) setCredits(data.credits);
      if (data.status === 'error' && data.error) {
        setError(data.hint ? `${data.error} (${data.hint})` : data.error);
      } else {
        setError(null);
      }
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        setError(err.message);
      }
    } finally {
      setBusy(null);
      void loadData();
    }
  };

  return (
    <section className="section" id="hcp-marketplace">
      <div className="glass p-6 md:p-8">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold md:text-3xl">{t('hcpMarketplace.title')}</h2>
          <span className="rounded-full border border-white/20 bg-black/20 px-3 py-1 text-xs text-white/80">
            {mode === 'loading' ? t('hcpMarketplace.loading') : mode === 'live' ? t('hcpMarketplace.live') : t('hcpMarketplace.demo')}
          </span>
        </div>

        {mode === 'demo' && (
          <p className="mb-4 text-sm text-cyan-200/90">{t('hcpMarketplace.offlineNote')}</p>
        )}

        {error && (
          <p className="mb-4 text-sm text-rose-300">
            {t('hcpMarketplace.error')}: {error}
          </p>
        )}

        <div className="mb-4 flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-white/70">
            {t('hcpMarketplace.instanceId')}
            <input
              className="rounded border border-white/20 bg-black/30 px-2 py-1 font-mono text-sm text-white"
              value={instanceId}
              onChange={(e) => persistInstance(e.target.value)}
            />
          </label>
          <button
            type="button"
            onClick={() => void loadData()}
            className="rounded border border-white/25 px-3 py-1 text-sm text-white/90"
          >
            {t('hcpMarketplace.refresh')}
          </button>
        </div>

        <div className="mb-4 flex flex-wrap gap-4 text-sm">
          <div>
            <span className="text-white/60">{t('hcpMarketplace.credits')}: </span>
            <span className="font-semibold text-cyan-100">{credits != null ? credits.toFixed(0) : '—'}</span>
          </div>
          <div>
            <span className="text-white/60">{t('hcpMarketplace.runtime')}: </span>
            <span className="text-white/90">
              {runtime === 'attached' ? t('hcpMarketplace.runtimeAttached') : t('hcpMarketplace.runtimeDetached')}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          {displayItems.map((it) => {
            const b = busy === `purchase-${it.item_id}` || busy === `install-${it.item_id}` || busy === `load-${it.item_id}`;
            return (
              <div
                key={it.item_id}
                className="flex flex-col gap-2 rounded-lg border border-white/10 px-3 py-2 sm:flex-row sm:items-center sm:justify-between"
              >
                <div>
                  <div className="font-semibold text-white">{it.title}</div>
                  <div className="text-xs text-white/60">
                    {it.item_id} · {t('hcpMarketplace.price')}: {it.price_credits}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {mode === 'live' && (
                    <>
                      <button
                        type="button"
                        disabled={b}
                        onClick={() => void post('purchase', { item_id: it.item_id, instance_id: instanceId })}
                        aria-label={`${t('hcpMarketplace.buy')} ${it.title}`}
                        className="rounded border border-cyan-300/40 bg-cyan-500/15 px-2 py-1 text-xs text-cyan-100 disabled:opacity-50"
                      >
                        {t('hcpMarketplace.buy')}
                      </button>
                      <button
                        type="button"
                        disabled={b}
                        onClick={() => void post('install', { item_id: it.item_id, instance_id: instanceId })}
                        aria-label={`${t('hcpMarketplace.install')} ${it.title}`}
                        className="rounded border border-violet-300/40 bg-violet-500/15 px-2 py-1 text-xs text-violet-100 disabled:opacity-50"
                      >
                        {t('hcpMarketplace.install')}
                      </button>
                      {runtime === 'attached' && (
                        <button
                          type="button"
                          disabled={b}
                          onClick={() => void post('load', { item_id: it.item_id, instance_id: instanceId })}
                          aria-label={`${t('hcpMarketplace.loadRuntime')} ${it.title}`}
                          className="rounded border border-emerald-300/40 bg-emerald-500/15 px-2 py-1 text-xs text-emerald-100 disabled:opacity-50"
                        >
                          {t('hcpMarketplace.loadRuntime')}
                        </button>
                      )}
                    </>
                  )}
                  {mode === 'demo' && (
                    <span className="text-xs text-white/50">{t('hcpMarketplace.demoActions')}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
