import { Activity, Clock3, Eye, Gauge, Route, TrendingUp, Waves, Music, Archive, Timer } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Lang = 'en' | 'ru';

const trajectory = [
  { cycle: 1, noObserver: 0.7436, observer: 0.7436, conductor: 0.7436, drift: 0.55, resonance: 0.25 },
  { cycle: 2, noObserver: 0.7515, observer: 0.7675, conductor: 0.7710, drift: 0.478, resonance: 0.349 },
  { cycle: 3, noObserver: 0.7595, observer: 0.7914, conductor: 0.7951, drift: 0.406, resonance: 0.448 },
  { cycle: 4, noObserver: 0.7675, observer: 0.8153, conductor: 0.8193, drift: 0.334, resonance: 0.547 },
  { cycle: 5, noObserver: 0.7755, observer: 0.8392, conductor: 0.8434, drift: 0.262, resonance: 0.646 },
  { cycle: 6, noObserver: 0.7834, observer: 0.8631, conductor: 0.8698, drift: 0.19, resonance: 0.745 }
] as const;

const staticMetrics = [
  { key: 'baseline', en: 'Single answer (baseline)', ru: 'Одиночный ответ (baseline)', value: '0.1423' },
  { key: 'cooperative', en: 'Cooperative route', ru: 'Кооперативный маршрут', value: '0.7436' },
  { key: 'fullStack', en: 'Full evidence stack', ru: 'Полный стек доказательств', value: '0.8764' },
  { key: 'gain', en: 'Network precision gain', ru: 'Прирост точности сети', value: '+0.7341' },
  { key: 'ratio', en: 'Score ratio vs baseline', ru: 'Отношение к baseline', value: '6.16x' },

] as const;

const copy = {
  en: {
    eyebrow: 'Network trajectory',
    title: 'The network does not freeze a good route. It watches whether the route gets more precise over time.',
    subtitle:
      'A single score says which route worked now. A trajectory shows whether repeated cycles, memory, and an external observer make the next route selection better.',
    staticTitle: 'Static precision (old approach)',
    staticBody: 'One cooperative pass over a single task already improves precision 6.16x over a lone answer.',
    temporalTitle: 'Temporal precision (new approach)',
    temporalBody: 'Repeated cycles with an observer accelerate precision 3x. Conductor v0.2 applies reason, magnitude, and freshness deltas, pushing the network to 99.25% of its theoretical maximum. Route Memory v0 persists successful multi-actor paths and recalls them on repeat tasks.',
    withoutObserver: 'without observer',
    withObserver: 'with observer',
    withConductor: '+ conductor',
    cycle: 'cycle',
    precision: 'precision',
    drift: 'drift',
    resonance: 'resonance',
    insightTitle: 'What the probe showed',
    insight:
      'Old approach: one cooperative pass gives +0.7341 gain (6.16x). New approach: repeated cycles + observer + conductor v0.2 give +0.1262 over the route start and +0.0067 over observer-only, reaching 99.25% of the theoretical maximum. The conductor uses causal reasons, reason strength, and freshness instead of trial and error. Successful routes are now persisted in Route Memory v0 — the same task recalls the best path without re-probing all actors.',
    command: 'python scripts/run_network_trajectory_demo.py',
    metrics: [
      { label: 'conductor delta', value: '+0.1262', icon: Music },
      { label: 'velocity multiplier', value: '3.15x', icon: Gauge },
      { label: 'drift reduction', value: '+0.3600', icon: Activity },
      { label: 'resonance gain', value: '+0.4950', icon: Waves },
      { label: 'route memory', value: 'v0', icon: Archive },
      { label: 'live pilot', value: 'v0.2', icon: Timer }
    ],
    footer:
      'This is still not model training. LS improves the map around the models: which route to repeat, when it drifts, and where a human should inspect the next step.'
  },
  ru: {
    eyebrow: 'Траектория сети',
    title: 'Сеть не просто хранит хороший маршрут. Она смотрит, становится ли маршрут точнее со временем.',
    subtitle:
      'Одна оценка показывает, какой путь сработал сейчас. Траектория показывает, помогают ли повторные циклы, память и наблюдатель выбирать следующий путь точнее.',
    staticTitle: 'Статическая точность (старый подход)',
    staticBody: 'Один кооперативный проход по одной задаче уже даёт прирост точности в 6.16x против одиночного ответа.',
    temporalTitle: 'Временна́я точность (новый подход)',
    temporalBody: 'Повторные циклы с наблюдателем ускоряют рост точности в 3x. Дирижёр v0.2 учитывает причину, силу сигнала и свежесть — сеть выходит на 99.25% от теоретического максимума. Route Memory v0 сохраняет успешные многo-акторные маршруты и восстанавливает их при повторных задачах.',
    withoutObserver: 'без наблюдателя',
    withObserver: 'с наблюдателем',
    withConductor: '+ дирижёр',
    cycle: 'цикл',
    precision: 'точность',
    drift: 'дрейф',
    resonance: 'резонанс',
    insightTitle: 'Что показал probe',
    insight:
      'Старый подход: один кооперативный проход даёт +0.7341 (6.16x). Новый подход: повторные циклы + наблюдатель + дирижёр v0.2 дают +0.1262 от старта маршрута и +0.0067 сверх observer-only, достигая 99.25% от теоретического максимума. Дирижёр использует причины, силу причины и свежесть, а не метод проб и ошибок. Успешные маршруты сохраняются в Route Memory v0 — при повторной задаче сеть вспоминает лучший путь без повторного опроса всех акторов.',
    command: 'python scripts/run_network_trajectory_demo.py',
    metrics: [
      { label: 'вклад дирижёра', value: '+0.1262', icon: Music },
      { label: 'скорость роста', value: '3.15x', icon: Gauge },
      { label: 'снижение дрейфа', value: '+0.3600', icon: Activity },
      { label: 'рост резонанса', value: '+0.4950', icon: Waves },
      { label: 'память маршрутов', value: 'v0', icon: Archive },
      { label: 'живой пилот', value: 'v0.2', icon: Timer }
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
            <div className="rounded-lg border border-amber-300/20 bg-amber-300/8 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="min-w-0 text-xs uppercase leading-tight tracking-[0.12em] text-amber-100/70">{text.staticTitle}</p>
                <Archive className="h-4 w-4 shrink-0 text-amber-200" />
              </div>
              <p className="mt-2 text-xs leading-5 text-amber-50/65">{text.staticBody}</p>
              <div className="mt-3 space-y-1.5">
                {staticMetrics.map((m) => (
                  <div key={m.key} className="flex items-center justify-between gap-2 rounded-md bg-amber-950/40 px-2.5 py-1.5">
                    <span className="text-[11px] uppercase tracking-[0.10em] text-amber-100/60">{lang === 'ru' ? m.ru : m.en}</span>
                    <span className="font-mono text-sm font-semibold text-amber-100">{m.value}</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-emerald-300/20 bg-emerald-300/8 p-4">
              <div className="flex items-center justify-between gap-3">
                <p className="min-w-0 text-xs uppercase leading-tight tracking-[0.12em] text-emerald-100/70">{text.temporalTitle}</p>
                <Timer className="h-4 w-4 shrink-0 text-emerald-200" />
              </div>
              <p className="mt-2 text-xs leading-5 text-emerald-50/65">{text.temporalBody}</p>
              <div className="mt-3 grid grid-cols-2 gap-1.5">
                {text.metrics.map(({ label, value, icon: Icon }) => (
                  <div key={label} className="flex items-center gap-2 rounded-md bg-emerald-950/40 px-2.5 py-1.5">
                    <Icon className="h-3 w-3 shrink-0 text-emerald-200" />
                    <div className="min-w-0">
                      <p className="text-[10px] uppercase leading-tight tracking-[0.10em] text-emerald-100/55">{label}</p>
                      <p className="font-mono text-sm font-semibold text-emerald-50">{value}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
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
                v0.2
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
