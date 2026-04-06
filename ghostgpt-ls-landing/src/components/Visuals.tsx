import { Check, Sparkles, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';

export default function Visuals() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'ru' ? 'ru' : 'en';

  const signalLabels = {
    en: ['Signal flow 1', 'Signal flow 2', 'Signal flow 3'],
    ru: ['Поток сигнала 1', 'Поток сигнала 2', 'Поток сигнала 3']
  } as const;

  const signalNotes = {
    en: [
      'Mesh topology for distributed operator memory.',
      'Temporal structures keep sequence and causality visible.',
      'Growth layers show how the system becomes more stable over time.'
    ],
    ru: [
      'Mesh-топология для распределенной операторской памяти.',
      'Временные структуры сохраняют последовательность и причинность.',
      'Слои роста показывают, как система становится устойчивее со временем.'
    ]
  } as const;

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('visuals.title')}</h2>

      <div className="grid gap-5 md:grid-cols-3">
        {[t('visuals.web4'), t('visuals.temporal'), t('visuals.growth')].map((title, idx) => (
          <article
            key={title}
            className="glass group flex min-h-[18rem] flex-col p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-base font-semibold text-ghost-200">{title}</p>
              <div className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-cyan-200">
                {signalLabels[lang][idx]}
              </div>
            </div>

            <div className="mt-5 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-gradient-to-br from-ghost-700 via-slate-900 to-ghost-500/60 p-4">
              <div className="grid h-full place-items-center rounded-[1.1rem] border border-white/10 bg-[radial-gradient(circle_at_30%_40%,rgba(116,247,255,.35),transparent_28%),radial-gradient(circle_at_70%_60%,rgba(54,124,255,.24),transparent_34%),linear-gradient(145deg,rgba(255,255,255,.04),rgba(255,255,255,.01))]">
                <div className="h-28 w-full animate-pulse bg-[radial-gradient(circle_at_20%_40%,rgba(116,247,255,.45),transparent_18%),radial-gradient(circle_at_60%_55%,rgba(255,255,255,.22),transparent_14%),radial-gradient(circle_at_80%_30%,rgba(54,124,255,.38),transparent_16%)]" />
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-white/70">
              {signalNotes[lang][idx]}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-8 grid gap-5 md:grid-cols-2">
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
                <div className="rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-white/50">
                  Preview only
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div className="flex items-center justify-center gap-1 rounded-md border border-emerald-300/30 bg-emerald-400/10 px-2 py-1 text-xs text-emerald-300">
                    <Check className="h-3.5 w-3.5" /> approve
                  </div>
                  <div className="flex items-center justify-center gap-1 rounded-md border border-rose-300/30 bg-rose-400/10 px-2 py-1 text-xs text-rose-300">
                    <X className="h-3.5 w-3.5" /> reject
                  </div>
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
