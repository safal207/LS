import { Activity, Clock3, Eye, Gauge, Route, TrendingUp, Waves, Music } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Lang = 'en' | 'ru';

const trajectory = [
  { cycle: 1, noObserver: 0.7436, observer: 0.7436, conductor: 0.7436, drift: 0.55, resonance: 0.25 },
  { cycle: 2, noObserver: 0.7515, observer: 0.7675, conductor: 0.7718, drift: 0.478, resonance: 0.349 },
  { cycle: 3, noObserver: 0.7595, observer: 0.7914, conductor: 0.8001, drift: 0.406, resonance: 0.448 },
  { cycle: 4, noObserver: 0.7675, observer: 0.8153, conductor: 0.8283, drift: 0.334, resonance: 0.547 },
  { cycle: 5, noObserver: 0.7755, observer: 0.8392, conductor: 0.8566, drift: 0.262, resonance: 0.646 },
  { cycle: 6, noObserver: 0.7834, observer: 0.8631, conductor: 0.8703, drift: 0.19, resonance: 0.745 }
] as const;

const copy = {
  en: {
    eyebrow: 'Network trajectory',
    title: 'The network does not freeze a good route. It watches whether the route gets more precise over time.',
    subtitle:
      'A single score says which route worked now. A trajectory shows whether repeated cycles, memory, and an external observer make the next route selection better.',
    withoutObserver: 'without observer',
    withObserver: 'with observer',
    withConductor: '+ conductor',
    cycle: 'cycle',
    precision: 'precision',
    drift: 'drift',
    resonance: 'resonance',
    insightTitle: 'What the probe showed',
    insight:
      'With an observer, route precision grew 3x faster (+0.0797). With a conductor applying reason-based weight deltas each cycle, precision reached +0.1267 — drift fell, resonance rose, and the network approached 99.3% of its theoretical maximum.',
    command: 'python scripts/run_network_trajectory_demo.py',
    metrics: [
      { label: 'conductor delta', value: '+0.1267', icon: Music },
      { label: 'velocity multiplier', value: '3.16x', icon: Gauge },
      { label: 'drift reduction', value: '+0.3600', icon: Activity },
      { label: 'resonance gain', value: '+0.4950', icon: Waves }
    ],
    footer:
      'This is still not model training. LS improves the map around the models: which route to repeat, when it drifts, and where a human should inspect the next step.'
  },
  ru: {
    eyebrow: 'Траектория сети',
    title: 'Сеть не просто хранит хороший маршрут. Она смотрит, становится ли маршрут точнее со временем.',
    subtitle:
      'Одна оценка показывает, какой путь сработал сейчас. Траектория показывает, помогают ли повторные циклы, память и наблюдатель выбирать следующий путь точнее.',
    withoutObserver: 'без наблюдателя',
    withObserver: 'с наблюдателем',
    withConductor: '+ дирижёр',
    cycle: 'цикл',
    precision: 'точность',
    drift: 'дрейф',
    resonance: 'резонанс',
    insightTitle: 'Что показал probe',
    insight:
      'С наблюдателем точность росла в 3 раза быстрее (+0.0797). Дирижёр применяет коррекции весов на основе причин каждый цикл — точность достигла +0.1267, дрейф снизился, резонанс вырос, сеть вышла на 99.3% от теоретического максимума.',
    command: 'python scripts/run_network_trajectory_demo.py',
    metrics: [
      { label: 'вклад дирижёра', value: '+0.1267', icon: Music },
      { label: 'скорость роста', value: '3.16x', icon: Gauge },
      { label: 'снижение дрейфа', value: '+0.3600', icon: Activity },
      { label: 'рост резонанса', value: '+0.4950', icon: Waves }
    ],
    footer:
      'Это не обучение весов модели. LS улучшает карту вокруг моделей: какой маршрут повторять, где он начал плыть и где человеку стоит проверить следующий шаг.'
  }
} as const;

function scoreWidth(value: number) {
  return `${Math.max(8, Math.min(100, value * 100))}%`;
}

export default function NetworkTrajectory() {
  const { i18n } = useTranslation();
  const lang: Lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = copy[lang];

  return (
    <section className="section" id="network-trajectory">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div className="min-w-0">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-emerald-300/30 bg-emerald-300/10 px-4 py-1 text-xs uppercase tracking-widest text-emerald-100">
            <TrendingUp className="h-3.5 w-3.5" />
            {text.eyebrow}
          </div>
          <h2 className="max-w-4xl text-3xl font-semibold leading-tight md:text-5xl">{text.title}</h2>
          <p className="mt-5 max-w-3xl text-base leading-7 text-white/75 md:text-lg">{text.subtitle}</p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {text.metrics.map(({ label, value, icon: Icon }) => (
              <div key={label} className="rounded-lg border border-white/10 bg-white/5 p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="min-w-0 text-xs uppercase leading-tight tracking-[0.12em] text-white/55">{label}</p>
                  <Icon className="h-4 w-4 shrink-0 text-emerald-200" />
                </div>
                <p className="mt-3 font-mono text-2xl font-semibold text-emerald-50">{value}</p>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-4">
            <div className="flex items-center gap-2 text-cyan-100">
              <Eye className="h-5 w-5" />
              <h3 className="text-lg font-semibold">{text.insightTitle}</h3>
            </div>
            <p className="mt-3 text-sm leading-6 text-cyan-50/80">{text.insight}</p>
          </div>
        </div>

        <div className="glass min-w-0 p-4 md:p-5">
          <div className="rounded-lg border border-white/10 bg-slate-950/65 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-emerald-100">
                  <Route className="h-5 w-5" />
                  <h3 className="text-xl font-semibold">customer_i → approver</h3>
                </div>
                <p className="mt-2 break-all font-mono text-xs leading-5 text-white/55">
                  customer_i&gt;customer_a&gt;customer_e&gt;planner&gt;executor&gt;consumer_i&gt;consumer_a&gt;consumer_e&gt;verifier&gt;approver
                </p>
              </div>
              <span className="rounded-full border border-emerald-300/35 bg-emerald-300/12 px-3 py-1 text-xs uppercase tracking-[0.14em] text-emerald-100">
                v0.1
              </span>
            </div>

            <div className="mt-5 grid gap-3">
              {trajectory.map((row) => (
                <div key={row.cycle} className="rounded-lg border border-white/10 bg-white/5 p-3">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <span className="text-xs uppercase tracking-[0.12em] text-white/50">
                      {text.cycle} {row.cycle}
                    </span>
                    <span className="font-mono text-xs text-amber-100">
                      obs +{(row.observer - row.noObserver).toFixed(4)}
                    </span>
                    <span className="font-mono text-xs text-emerald-100">
                      cond +{(row.conductor - row.noObserver).toFixed(4)}
                    </span>
                  </div>

                  <div className="grid gap-2">
                    <div className="grid min-w-0 grid-cols-[7.5rem_1fr_4.5rem] items-center gap-2">
                      <span className="truncate text-xs text-white/55">{text.withoutObserver}</span>
                      <div className="h-2 overflow-hidden rounded-full bg-white/10">
                        <div className="h-full rounded-full bg-white/45" style={{ width: scoreWidth(row.noObserver) }} />
                      </div>
                      <span className="text-right font-mono text-xs text-white/70">{row.noObserver.toFixed(4)}</span>
                    </div>

                    <div className="grid min-w-0 grid-cols-[7.5rem_1fr_4.5rem] items-center gap-2">
                      <span className="truncate text-xs text-emerald-100/75">{text.withObserver}</span>
                      <div className="h-2 overflow-hidden rounded-full bg-emerald-300/10">
                        <div className="h-full rounded-full bg-emerald-300" style={{ width: scoreWidth(row.observer) }} />
                      </div>
                      <span className="text-right font-mono text-xs text-emerald-100">{row.observer.toFixed(4)}</span>
                    </div>

                    <div className="grid min-w-0 grid-cols-[7.5rem_1fr_4.5rem] items-center gap-2">
                      <span className="truncate text-xs text-amber-100/75">{text.withConductor}</span>
                      <div className="h-2 overflow-hidden rounded-full bg-amber-300/10">
                        <div className="h-full rounded-full bg-amber-300" style={{ width: scoreWidth(row.conductor) }} />
                      </div>
                      <span className="text-right font-mono text-xs text-amber-100">{row.conductor.toFixed(4)}</span>
                    </div>
                  </div>

                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <div className="flex items-center justify-between rounded-md bg-slate-950/55 px-3 py-2">
                      <span className="flex items-center gap-2 text-xs text-white/55">
                        <Clock3 className="h-3.5 w-3.5 text-cyan-200" />
                        {text.drift}
                      </span>
                      <span className="font-mono text-xs text-white/75">{row.drift.toFixed(3)}</span>
                    </div>
                    <div className="flex items-center justify-between rounded-md bg-slate-950/55 px-3 py-2">
                      <span className="flex items-center gap-2 text-xs text-white/55">
                        <Waves className="h-3.5 w-3.5 text-emerald-200" />
                        {text.resonance}
                      </span>
                      <span className="font-mono text-xs text-white/75">{row.resonance.toFixed(3)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-white/10 bg-black/25 p-4">
            <p className="break-all font-mono text-xs leading-6 text-cyan-100">{text.command}</p>
            <p className="mt-3 text-sm leading-6 text-white/60">{text.footer}</p>
          </div>
        </div>
      </div>
    </section>
  );
}
