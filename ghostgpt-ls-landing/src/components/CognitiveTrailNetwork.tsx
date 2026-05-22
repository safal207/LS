import { ArrowRight, BadgeCheck, GitPullRequestArrow, Network, Route, ShieldCheck, TrendingUp } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Lang = 'en' | 'ru';

const copy = {
  en: {
    eyebrow: 'Cognitive Trail Network',
    title: 'Models do not just answer. They leave verified trails.',
    subtitle:
      'LS records which cooperative route made a concrete task more precise, then lets the next similar task start from the best known path instead of starting from zero.',
    routeTitle: 'PR-review route',
    routeSubtitle: 'A real git diff becomes a reusable cooperation artifact.',
    benchmarkTitle: 'Measured local snapshot',
    benchmarkBody:
      'On the current small PR-review sample, the cooperative route beat the direct baseline on every checked diff.',
    topRole: 'Top role',
    topActor: 'Top actor',
    baseline: 'Baseline',
    cooperative: 'Cooperative',
    lift: 'Reward lift',
    proofTitle: 'What this proves',
    proofBody:
      'LS can measure which role route improved a concrete task. It is not a global model ranking and not a claim that models become generally smarter.',
    cta: 'Open reviewer quickstart',
    ctaHref:
      'https://github.com/safal207/LS/blob/main/docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md',
    steps: ['Diff', 'Draft', 'Risk critic', 'Evidence', 'Final review', 'Trail memory'],
    facts: [
      'route artifact',
      'contribution ledger',
      'schema validation',
      'CI report artifact'
    ]
  },
  ru: {
    eyebrow: 'Когнитивная сеть маршрутов',
    title: 'Модели не просто отвечают. Они оставляют проверенные тропы.',
    subtitle:
      'LS запоминает, какой маршрут кооперации сделал конкретную задачу точнее, и следующая похожая задача начинает не с нуля, а с лучшего известного пути.',
    routeTitle: 'Маршрут проверки PR',
    routeSubtitle: 'Реальный git diff превращается в повторяемый артефакт кооперации.',
    benchmarkTitle: 'Локальный измеримый снимок',
    benchmarkBody:
      'На текущем малом примере PR-review кооперативный маршрут обошел прямой одиночный проход на каждом проверенном diff.',
    topRole: 'Лучшая роль',
    topActor: 'Лучший участник',
    baseline: 'Одиночный проход',
    cooperative: 'Кооперация',
    lift: 'Прирост точности',
    proofTitle: 'Что это доказывает',
    proofBody:
      'LS уже может измерять, какой маршрут ролей улучшил конкретную задачу. Это не глобальный рейтинг моделей и не заявление, что модели вообще стали умнее.',
    cta: 'Открыть quickstart для reviewer',
    ctaHref:
      'https://github.com/safal207/LS/blob/main/docs/COGNITIVE_TRAIL_REVIEWER_QUICKSTART.md',
    steps: ['Diff', 'Черновик', 'Критик риска', 'Доказательства', 'Финал', 'Память тропы'],
    facts: [
      'артефакт маршрута',
      'журнал вклада',
      'проверка схемы',
      'CI-отчет'
    ]
  }
} as const;

const metrics = [
  { key: 'baseline', value: '0.5943' },
  { key: 'cooperative', value: '0.7233' },
  { key: 'lift', value: '+0.1290' }
] as const;

export default function CognitiveTrailNetwork() {
  const { i18n } = useTranslation();
  const lang: Lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = copy[lang];

  return (
    <section className="section" id="cognitive-trail-network">
      <div className="grid gap-8 lg:grid-cols-[0.95fr_1.05fr] lg:items-start">
        <div className="min-w-0">
          <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
            <Network className="h-3.5 w-3.5" />
            {text.eyebrow}
          </div>
          <h2 className="max-w-3xl text-3xl font-semibold leading-tight md:text-5xl">{text.title}</h2>
          <p className="mt-5 max-w-3xl text-base leading-7 text-white/75 md:text-lg">{text.subtitle}</p>

          <div className="mt-6 grid gap-3 sm:grid-cols-2">
            {text.facts.map((fact) => (
              <div key={fact} className="flex min-w-0 items-center gap-3 rounded-lg border border-white/10 bg-white/5 px-4 py-3">
                <BadgeCheck className="h-4 w-4 shrink-0 text-emerald-200" />
                <span className="min-w-0 text-sm font-medium text-white/78">{fact}</span>
              </div>
            ))}
          </div>

          <a
            className="mt-6 inline-flex items-center gap-2 rounded-lg border border-cyan-300/50 bg-cyan-300/12 px-5 py-3 text-sm font-semibold text-cyan-50 transition hover:bg-cyan-200 hover:text-slate-950"
            href={text.ctaHref}
            rel="noreferrer"
            target="_blank"
          >
            {text.cta}
            <ArrowRight className="h-4 w-4" />
          </a>
        </div>

        <div className="glass min-w-0 p-4 md:p-5">
          <div className="rounded-lg border border-white/10 bg-slate-950/65 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex items-center gap-2 text-cyan-100">
                  <GitPullRequestArrow className="h-5 w-5" />
                  <h3 className="text-xl font-semibold">{text.routeTitle}</h3>
                </div>
                <p className="mt-2 text-sm leading-6 text-white/65">{text.routeSubtitle}</p>
              </div>
              <span className="rounded-full border border-emerald-300/35 bg-emerald-300/12 px-3 py-1 text-xs uppercase tracking-[0.14em] text-emerald-100">
                schema + CI
              </span>
            </div>

            <div className="mt-5 grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
              {text.steps.map((step, index) => (
                <div key={step} className="min-w-0 rounded-lg border border-cyan-300/15 bg-cyan-300/8 p-3 text-center">
                  <div className="mx-auto mb-2 flex h-8 w-8 items-center justify-center rounded-full border border-cyan-200/35 bg-cyan-200/10 text-xs font-semibold text-cyan-100">
                    {index + 1}
                  </div>
                  <p className="text-xs font-medium leading-tight text-white/78">{step}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-4 grid min-w-0 gap-4 md:grid-cols-[0.9fr_1.1fr]">
            <div className="min-w-0 rounded-lg border border-white/10 bg-black/25 p-4">
              <div className="flex items-center gap-2 text-cyan-100">
                <TrendingUp className="h-5 w-5" />
                <h3 className="text-lg font-semibold">{text.benchmarkTitle}</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-white/68">{text.benchmarkBody}</p>

              <div className="mt-4 grid gap-2">
                {metrics.map((metric) => (
                  <div
                    key={metric.key}
                    className="flex min-w-0 items-center justify-between gap-3 rounded-lg border border-white/10 bg-white/5 px-3 py-2"
                  >
                    <span className="min-w-0 break-words text-xs uppercase leading-tight tracking-[0.12em] text-white/50">
                      {text[metric.key]}
                    </span>
                    <span className="font-mono text-sm font-semibold text-cyan-100">{metric.value}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="min-w-0 rounded-lg border border-white/10 bg-black/25 p-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-amber-300/25 bg-amber-300/10 p-3">
                  <p className="text-xs uppercase tracking-[0.12em] text-amber-100/75">{text.topRole}</p>
                  <p className="mt-2 font-mono text-sm font-semibold text-amber-50">risk_critic</p>
                </div>
                <div className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 p-3">
                  <p className="text-xs uppercase tracking-[0.12em] text-emerald-100/75">{text.topActor}</p>
                  <p className="mt-2 font-mono text-sm font-semibold text-emerald-50">gonka</p>
                </div>
              </div>

              <div className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/10 p-4">
                <div className="flex items-center gap-2 text-cyan-100">
                  <ShieldCheck className="h-5 w-5" />
                  <h3 className="text-base font-semibold">{text.proofTitle}</h3>
                </div>
                <p className="mt-3 text-sm leading-6 text-cyan-50/80">{text.proofBody}</p>
              </div>

              <div className="mt-4 flex min-w-0 items-center gap-2 rounded-lg border border-white/10 bg-slate-950/60 px-3 py-2 text-xs text-white/55">
                <Route className="h-4 w-4 shrink-0 text-cyan-200" />
                <span className="min-w-0 break-all">pr_review&gt;draft_reviewer&gt;risk_critic&gt;evidence_verifier&gt;final_reviewer</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
