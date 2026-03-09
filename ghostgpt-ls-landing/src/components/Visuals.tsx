import { Check, Sparkles, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function Visuals() {
  const { t } = useTranslation();

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('visuals.title')}</h2>

      <div className="grid gap-4 md:grid-cols-3">
        {[t('visuals.web4'), t('visuals.temporal'), t('visuals.growth')].map((title, idx) => (
          <div key={title} className="glass h-36 p-4 transition hover:-translate-y-1 hover:bg-white/15">
            <p className="mb-3 text-sm text-ghost-300">{title}</p>
            <div className="h-20 rounded-lg bg-gradient-to-r from-ghost-700 to-ghost-500/70">
              <div className="h-full w-full animate-pulse bg-[radial-gradient(circle_at_30%_40%,rgba(116,247,255,.5),transparent_45%)]" />
            </div>
            <div className="mt-2 text-xs text-white/70">Signal flow {idx + 1}</div>
          </div>
        ))}
      </div>

      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {[1, 2].map((id) => (
          <div key={id} className="glass p-4 transition hover:bg-white/15">
            <p className="mb-2 text-sm text-ghost-300">
              {t('visuals.mockupTitle')} #{id}
            </p>

            <div className="overflow-hidden rounded-lg border border-white/20 bg-slate-950/70">
              <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
                <div className="text-xs text-white/70">Reflection Dashboard</div>
                <Sparkles className="h-4 w-4 text-ghost-300" />
              </div>

              <div className="space-y-3 p-3">
                <div className="grid grid-cols-2 gap-2">
                  <button className="flex items-center justify-center gap-1 rounded-md border border-emerald-300/30 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-300 transition hover:bg-emerald-400/20">
                    <Check className="h-3.5 w-3.5" /> approve
                  </button>
                  <button className="flex items-center justify-center gap-1 rounded-md border border-rose-300/30 bg-rose-400/10 px-2 py-1 text-xs text-rose-300 transition hover:bg-rose-400/20">
                    <X className="h-3.5 w-3.5" /> reject
                  </button>
                </div>

                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-widest text-white/50">heatmap</p>
                  <div className="grid grid-cols-8 gap-1">
                    {Array.from({ length: 24 }).map((_, i) => (
                      <span
                        key={i}
                        className="h-2 rounded-sm"
                        style={{
                          background: `rgba(116,247,255,${0.2 + ((i * 7) % 10) / 12})`
                        }}
                      />
                    ))}
                  </div>
                </div>

                <div>
                  <p className="mb-1 text-[10px] uppercase tracking-widest text-white/50">trends</p>
                  <div className="h-12 w-full rounded bg-[linear-gradient(120deg,rgba(54,124,255,.2),rgba(116,247,255,.35),rgba(54,124,255,.2))] [background-size:200%_200%] animate-[pulse_2.4s_ease-in-out_infinite]" />
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
