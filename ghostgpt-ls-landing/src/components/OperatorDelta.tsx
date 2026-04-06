import { FileClock, Gavel, Scale, ShieldCheck, TimerReset, Waypoints } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import benchmark from '../data/operatorDeltaBenchmark.json';

type CopyBlock = {
  eyebrow: string;
  title: string;
  subtitle: string;
  withTitle: string;
  withPoints: string[];
  withoutTitle: string;
  withoutPoints: string[];
  benchmarkTitle: string;
  benchmarkNote: string;
  legalTitle: string;
  legalNote: string;
  legalPoints: string[];
  metrics: {
    queue: string;
    manualQueue: string;
    manualLtp: string;
    batchLtp: string;
    speedup: string;
    commandCut: string;
  };
};

const COPY: Record<'ru' | 'en', CopyBlock> = {
  ru: {
    eyebrow: 'С нами / без нас',
    title: 'Почему LS Agent Shell + LTP выглядит сильнее, чем ручной review-процесс',
    subtitle:
      'Это не обещание магии. Это более короткий путь от очереди задач к replayable evidence, batch triage и понятному approval-решению.',
    withTitle: 'С LS + LTP',
    withPoints: [
      'Очередь waiting_approval проверяется одним batch-проходом.',
      'Каждая задача имеет replayable trace и привязанную approval-историю.',
      'Инвестору, risk- и legal-команде проще увидеть не только итог, но и ход решения.',
    ],
    withoutTitle: 'Без этого слоя',
    withoutPoints: [
      'Оператор ходит по задачам по одной и держит контекст в голове.',
      'Review чаще превращается в смесь логов, скриншотов и ad-hoc handoff.',
      'Batch-картина по очереди и единый replay path отсутствуют.',
    ],
    benchmarkTitle: 'Локальный benchmark snapshot',
    benchmarkNote:
      'Это measured snapshot на одной dev-машине Windows. Он показывает разницу в операторском контуре, а не глобальный market-wide benchmark.',
    legalTitle: 'Юридическая и audit-польза',
    legalNote:
      'Это не юридическое заключение и не legal advice. Но это полезный evidence layer для counsel, compliance и internal review.',
    legalPoints: [
      'Replayable traces можно показать повторно вне исходной agent-сессии.',
      'Approval-события остаются привязанными к task и step, а не теряются в чате.',
      'Batch queue scan ускоряет первичный legal/risk triage перед approve.',
    ],
    metrics: {
      queue: 'Задач в очереди',
      manualQueue: 'Ручной CLI review',
      manualLtp: 'LTP по одной задаче',
      batchLtp: 'Batch LTP review',
      speedup: 'Экономия vs поштучный LTP',
      commandCut: 'Снижение числа команд',
    },
  },
  en: {
    eyebrow: 'With us / without us',
    title: 'Why LS Agent Shell + LTP is stronger than a manual review loop',
    subtitle:
      'This is not a magic claim. It is a shorter path from a waiting queue to replayable evidence, batch triage, and a clearer approval decision.',
    withTitle: 'With LS + LTP',
    withPoints: [
      'The waiting_approval queue can be scanned in one batch pass.',
      'Each task has a replayable trace and attached approval history.',
      'Investors, risk, and legal stakeholders can review both outcome and decision path.',
    ],
    withoutTitle: 'Without this layer',
    withoutPoints: [
      'The operator hops through tasks one by one and holds context manually.',
      'Review tends to degrade into logs, screenshots, and ad-hoc handoff.',
      'There is no queue-wide picture or one replay path for the approval set.',
    ],
    benchmarkTitle: 'Local benchmark snapshot',
    benchmarkNote:
      'This is a measured snapshot on one Windows development machine. It shows operator-loop delta, not a universal market benchmark.',
    legalTitle: 'Legal and audit value',
    legalNote:
      'This is not a legal opinion. It is an evidence layer that helps counsel, compliance, and internal reviewers move faster.',
    legalPoints: [
      'Replayable traces can be reviewed again outside the original agent session.',
      'Approval events stay attached to the task and step instead of disappearing into chat.',
      'Batch queue scan shortens first-pass legal/risk triage before approval.',
    ],
    metrics: {
      queue: 'Queue size',
      manualQueue: 'Manual CLI review',
      manualLtp: 'Per-task LTP review',
      batchLtp: 'Batch LTP review',
      speedup: 'Saved vs per-task LTP',
      commandCut: 'Command reduction',
    },
  },
};

function formatSeconds(value: number) {
  return `${value.toFixed(2)}s`;
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

export default function OperatorDelta() {
  const { i18n } = useTranslation();
  const lang = i18n.language.startsWith('ru') ? 'ru' : 'en';
  const copy = COPY[lang];
  const scenarioMap = Object.fromEntries(
    benchmark.scenarios.map((scenario) => [scenario.name, scenario])
  ) as Record<string, { seconds: number }>;

  return (
    <section className="section">
      <div className="glass overflow-hidden border-white/15 bg-slate-950/60 p-6 md:p-8">
        <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-400/10 px-4 py-1 text-xs uppercase tracking-[0.28em] text-cyan-100">
              <Scale className="h-3.5 w-3.5" />
              {copy.eyebrow}
            </div>
            <h2 className="max-w-4xl text-3xl font-semibold leading-tight text-white md:text-5xl">
              {copy.title}
            </h2>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300 md:text-base">
              {copy.subtitle}
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-200">
            <div className="text-xs uppercase tracking-[0.2em] text-slate-400">{copy.metrics.queue}</div>
            <div className="mt-1 text-3xl font-semibold text-cyan-200">
              {benchmark.summary.tasks_reviewed}
            </div>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="grid gap-5 md:grid-cols-2">
            <div className="rounded-3xl border border-emerald-300/20 bg-emerald-400/10 p-5">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-emerald-300/10 px-3 py-1 text-xs uppercase tracking-[0.22em] text-emerald-100">
                <ShieldCheck className="h-3.5 w-3.5" />
                {copy.withTitle}
              </div>
              <div className="space-y-3 text-sm leading-7 text-emerald-50/90">
                {copy.withPoints.map((point) => (
                  <p key={point}>{point}</p>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-rose-300/20 bg-rose-400/10 p-5">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-rose-300/10 px-3 py-1 text-xs uppercase tracking-[0.22em] text-rose-100">
                <TimerReset className="h-3.5 w-3.5" />
                {copy.withoutTitle}
              </div>
              <div className="space-y-3 text-sm leading-7 text-rose-50/90">
                {copy.withoutPoints.map((point) => (
                  <p key={point}>{point}</p>
                ))}
              </div>
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-5 md:col-span-2">
              <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-black/20 px-3 py-1 text-xs uppercase tracking-[0.22em] text-slate-200">
                <Waypoints className="h-3.5 w-3.5" />
                {copy.benchmarkTitle}
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard label={copy.metrics.manualQueue} value={formatSeconds(scenarioMap.manual_cli_review.seconds)} accent="slate" />
                <MetricCard label={copy.metrics.manualLtp} value={formatSeconds(scenarioMap.manual_ltp_review.seconds)} accent="amber" />
                <MetricCard label={copy.metrics.batchLtp} value={formatSeconds(scenarioMap.batch_ltp_review.seconds)} accent="cyan" />
                <MetricCard label={copy.metrics.speedup} value={`${formatSeconds(benchmark.summary.seconds_saved_vs_manual_ltp)} / ${formatPercent(benchmark.summary.batch_speedup_vs_manual_ltp_pct)}`} accent="emerald" />
                <MetricCard label={copy.metrics.commandCut} value={`${benchmark.summary.manual_review_commands} → ${benchmark.summary.batch_review_commands} (${formatPercent(benchmark.summary.command_reduction_pct)})`} accent="violet" />
                <MetricCard label="Generated" value={benchmark.generated_at.slice(0, 10)} accent="slate" />
              </div>
              <p className="mt-4 text-xs leading-6 text-slate-400">{copy.benchmarkNote}</p>
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-gradient-to-br from-slate-900 via-slate-950 to-cyan-950/70 p-5">
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs uppercase tracking-[0.22em] text-amber-100">
              <Gavel className="h-3.5 w-3.5" />
              {copy.legalTitle}
            </div>
            <p className="max-w-lg text-sm leading-7 text-slate-200">{copy.legalNote}</p>

            <div className="mt-5 space-y-3">
              {copy.legalPoints.map((point) => (
                <div
                  key={point}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-sm leading-7 text-slate-100"
                >
                  {point}
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-3xl border border-cyan-300/15 bg-cyan-400/10 p-5">
              <div className="mb-2 flex items-center gap-2 text-sm font-medium text-cyan-100">
                <FileClock className="h-4 w-4" />
                {benchmark.investor_takeaway.with_ls}
              </div>
              <div className="text-xs leading-6 text-cyan-50/80">
                {benchmark.investor_takeaway.disclaimer}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent: 'slate' | 'amber' | 'cyan' | 'emerald' | 'violet';
}) {
  const accentClass = {
    slate: 'from-slate-700/40 to-slate-900/40 text-slate-100',
    amber: 'from-amber-500/20 to-slate-900/40 text-amber-50',
    cyan: 'from-cyan-400/20 to-slate-900/40 text-cyan-50',
    emerald: 'from-emerald-400/20 to-slate-900/40 text-emerald-50',
    violet: 'from-violet-400/20 to-slate-900/40 text-violet-50',
  }[accent];

  return (
    <div className={`rounded-2xl border border-white/10 bg-gradient-to-br p-4 ${accentClass}`}>
      <div className="text-xs uppercase tracking-[0.18em] text-white/55">{label}</div>
      <div className="mt-3 text-xl font-semibold leading-tight">{value}</div>
    </div>
  );
}
