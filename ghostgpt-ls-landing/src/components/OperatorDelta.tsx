import { FileText, Gauge, Scale, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import councilScorecard from '../data/councilScorecard.json';
import benchmark from '../data/operatorDeltaBenchmark.json';

type Scenario = {
  name: string;
  seconds: number;
  commands: number;
  tasks_reviewed: number;
  notes: string;
};

type BenchmarkPayload = {
  scenarios: Scenario[];
  summary: {
    tasks_reviewed: number;
    seconds_saved_vs_manual_ltp: number;
    batch_speedup_vs_manual_ltp_pct: number;
    manual_review_commands: number;
    batch_review_commands: number;
    command_reduction_pct: number;
  };
  investor_takeaway: {
    with_ls: string;
    without_ls: string;
    legal_and_audit: string[];
    disclaimer: string;
  };
};

type ScorePoint = {
  label: string;
  value: number;
};

type CouncilScorecardPayload = {
  summary: {
    ledgers: number;
    top_contributor: string;
    success_rate: number;
    avg_resonance: number;
    avg_merit: number;
    avg_quality?: number;
    avg_relation_safety?: number;
    risky_cycle_count?: number;
    incident_count?: number;
    reviewed_cycle_count?: number;
    approval_conversion_rate?: number;
    escalation_rate?: number;
  };
  bars: {
    best_contributor_frequency: ScorePoint[];
    model_type_lift: ScorePoint[];
    route_wins: ScorePoint[];
  };
  lines: {
    resonance_trend: ScorePoint[];
    merit_trend: ScorePoint[];
    incident_trend?: ScorePoint[];
  };
  takeaways: {
    with_ls: string[];
    disclaimer: string;
  };
};

const payload = benchmark as BenchmarkPayload;
const scorecard = councilScorecard as CouncilScorecardPayload;

const copy = {
  en: {
    eyebrow: 'Operator delta',
    title: 'With LS + LTP versus without it',
    subtitle:
      'A queue-wide inspection path beats ad-hoc per-task review when approvals stack up. The point is fewer blind spots before an operator clicks approve.',
    withUs: 'With us',
    withoutUs: 'Without us',
    withUsBody:
      'One queue view, one replay path, one place where approvals, artifacts, and LTP inspection line up.',
    withoutUsBody:
      'Operators bounce across task IDs, raw traces, and ad-hoc judgment calls that are hard to replay later.',
    benchmark: 'Measured local snapshot',
    legal: 'Legal and audit value',
    disclaimerLabel: 'Disclosure',
    demoWith: 'With LS + LTP',
    demoWithout: 'Without LS + LTP',
    walkthrough: 'Operator walkthrough',
    statSaved: 'Seconds saved',
    statSpeed: 'Batch speedup',
    statCommands: 'Command reduction',
    statQueue: 'Tasks reviewed',
    tasks: 'tasks',
    seconds: 'seconds',
    commands: 'commands',
    terminalLabel: 'Review flow preview',
    councilEyebrow: 'Council scorecard',
    councilTitle: 'Which models actually improve the network',
    councilSubtitle:
      'A public-facing readout for the coordination council: contribution, route wins, receiver resonance, and merit trend in one investor-safe snapshot.',
    ledgers: 'Ledgers',
    topContributor: 'Top contributor',
    successRate: 'Success rate',
    avgResonance: 'Avg resonance',
    avgMerit: 'Avg merit',
    avgQuality: 'Avg quality',
    avgRelationSafety: 'Relation safety',
    riskyCycles: 'Risky cycles',
    incidents: 'Incidents',
    reviewed: 'Reviewed',
    approvalConv: 'Approval conv',
    escalationRate: 'Escalation rate',
    contribFreq: 'Best contributor frequency',
    modelLift: 'Model type lift',
    routeWins: 'Route wins',
    resonanceTrend: 'Receiver resonance trend',
    meritTrend: 'Merit trend',
    incidentTrend: 'Incident trend',
    scorecardTakeaways: 'What this makes visible',
    scorecardDisclaimer: 'Scorecard disclosure',
    sourceLabel: 'Snapshot source'
  },
  ru: {
    eyebrow: 'Operator delta',
    title: 'С нами и без нас: что меняется у оператора',
    subtitle:
      'Когда очередь approvals растет, queue-wide inspection полезнее, чем ручной разбор по одной задаче. Смысл в меньшем числе слепых зон перед approve.',
    withUs: 'С нами',
    withoutUs: 'Без нас',
    withUsBody:
      'Одна очередь, один replay path, одно место, где approvals, artifacts и LTP inspection собраны вместе.',
    withoutUsBody:
      'Оператор прыгает между task id, сырыми traces и ручными решениями, которые потом трудно воспроизвести.',
    benchmark: 'Локальный benchmark snapshot',
    legal: 'Польза для legal и audit',
    disclaimerLabel: 'Ограничение',
    demoWith: 'С LS + LTP',
    demoWithout: 'Без LS + LTP',
    walkthrough: 'Путь оператора',
    statSaved: 'Секунд экономии',
    statSpeed: 'Ускорение batch',
    statCommands: 'Снижение числа команд',
    statQueue: 'Задач в проверке',
    tasks: 'задач',
    seconds: 'секунд',
    commands: 'команд',
    terminalLabel: 'Превью review-потока',
    councilEyebrow: 'Council scorecard',
    councilTitle: 'Какие модели реально улучшают сеть',
    councilSubtitle:
      'Публичное investor-safe превью совета согласования: вклад моделей, победы route, резонанс с получателем и merit-trend в одном snapshot.',
    ledgers: 'Циклов',
    topContributor: 'Лидер вклада',
    successRate: 'Успешность',
    avgResonance: 'Средний резонанс',
    avgMerit: 'Средний merit',
    avgQuality: 'Среднее quality',
    avgRelationSafety: 'Безопасность связи',
    riskyCycles: 'Рисковые циклы',
    incidents: 'Инциденты',
    reviewed: 'Reviewed',
    approvalConv: 'Approval conv',
    escalationRate: 'Escalation rate',
    contribFreq: 'Частота лучшего contributor',
    modelLift: 'Подъем по типам моделей',
    routeWins: 'Победы маршрутов',
    resonanceTrend: 'Тренд резонанса',
    meritTrend: 'Тренд merit',
    incidentTrend: 'Тренд incident',
    scorecardTakeaways: 'Что это делает видимым',
    scorecardDisclaimer: 'Ограничение scorecard',
    sourceLabel: 'Источник snapshot'
  }
} as const;

const walkthrough = {
  en: {
    with: [
      '$ ls-agent list --status waiting_approval',
      '5 tasks ready for review',
      '$ ls-agent ltp-inspect-all --status waiting_approval',
      'Batch inspect complete: 5 task(s), decision: PROCEED',
      '$ ls-agent approvals',
      'Operator sees the exact step that still needs a human decision'
    ],
    without: [
      '$ ls-agent list --status waiting_approval',
      '5 tasks ready for review',
      '$ ls-agent inspect task-001',
      '$ ls-agent ltp-inspect task-001',
      '$ ls-agent inspect task-002',
      'Repeat until the queue is finally clear'
    ]
  },
  ru: {
    with: [
      '$ ls-agent list --status waiting_approval',
      '5 задач готовы к review',
      '$ ls-agent ltp-inspect-all --status waiting_approval',
      'Batch inspect complete: 5 task(s), decision: PROCEED',
      '$ ls-agent approvals',
      'Оператор сразу видит точный шаг, где еще нужно решение человека'
    ],
    without: [
      '$ ls-agent list --status waiting_approval',
      '5 задач ждут review',
      '$ ls-agent inspect task-001',
      '$ ls-agent ltp-inspect task-001',
      '$ ls-agent inspect task-002',
      'И так по одной, пока очередь не разберут вручную'
    ]
  }
} as const;

const scenarioLabels = {
  en: {
    manual_cli_review: 'Manual CLI review',
    manual_ltp_review: 'Per-task LTP review',
    batch_ltp_review: 'Batch LTP review'
  },
  ru: {
    manual_cli_review: 'Ручной CLI review',
    manual_ltp_review: 'Поштучный LTP review',
    batch_ltp_review: 'Batch LTP review'
  }
} as const;

const programFit = {
  en: {
    eyebrow: 'Program fit',
    title: 'Why this reads as oversight infrastructure, not another assistant shell',
    body:
      'The same artifact path works for safety fellowships, residencies, and evaluation-oriented programs: one real council cycle, one ledger, one scorecard, and one benchmarkable review story.'
  },
  ru: {
    eyebrow: 'Program fit',
    title: 'Почему это читается как oversight-инфраструктура, а не как еще один assistant shell',
    body:
      'Тот же artifact path подходит для safety fellowship, residency и evaluation-oriented programs: один реальный council cycle, один ledger, один scorecard и одна понятная benchmark-story.'
  }
} as const;

function MiniBars({ data, tone = 'cyan' }: { data: ScorePoint[]; tone?: 'cyan' | 'emerald' | 'amber' }) {
  const max = Math.max(...data.map((item) => item.value), 1);
  const palette = {
    cyan: 'from-cyan-300 to-sky-500',
    emerald: 'from-emerald-300 to-emerald-500',
    amber: 'from-amber-300 to-orange-500'
  } as const;

  return (
    <div className="space-y-3">
      {data.map((item) => (
        <div key={item.label} className="space-y-1">
          <div className="flex items-center justify-between text-xs uppercase tracking-[0.14em] text-white/65">
            <span>{item.label}</span>
            <span>{item.value}</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full bg-gradient-to-r ${palette[tone]}`}
              style={{ width: `${Math.max((item.value / max) * 100, 8)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

function MiniLine({ data, stroke }: { data: ScorePoint[]; stroke: string }) {
  const width = 320;
  const height = 120;
  const padding = 12;
  const max = Math.max(...data.map((item) => item.value), 1);
  const step = data.length === 1 ? 0 : (width - padding * 2) / (data.length - 1);
  const points = data.map((item, index) => {
    const x = padding + index * step;
    const y = height - padding - (item.value / max) * (height - padding * 2);
    return { ...item, x, y };
  });
  const polyline = points.map((point) => `${point.x},${point.y}`).join(' ');

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-32 w-full overflow-visible">
      <polyline
        points={polyline}
        fill="none"
        stroke={stroke}
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      {points.map((point) => (
        <g key={point.label}>
          <circle cx={point.x} cy={point.y} r="4" fill={stroke} />
          <text x={point.x} y={height - 2} textAnchor="middle" fontSize="10" fill="rgba(255,255,255,0.55)">
            {point.label}
          </text>
        </g>
      ))}
    </svg>
  );
}

export default function OperatorDelta() {
  const { i18n } = useTranslation();
  const lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = copy[lang];
  const program = programFit[lang];
  const [mode, setMode] = useState<'with' | 'without'>('with');

  const stats = [
    { label: text.statSaved, value: `${payload.summary.seconds_saved_vs_manual_ltp.toFixed(2)} ${text.seconds}` },
    { label: text.statSpeed, value: `${payload.summary.batch_speedup_vs_manual_ltp_pct.toFixed(2)}%` },
    { label: text.statCommands, value: `${payload.summary.command_reduction_pct.toFixed(2)}%` },
    { label: text.statQueue, value: `${payload.summary.tasks_reviewed} ${text.tasks}` }
  ];

  return (
    <section className="section" id="operator-delta">
      <div className="rounded-[2rem] border border-cyan-300/20 bg-[radial-gradient(circle_at_top,rgba(116,247,255,0.14),transparent_40%),linear-gradient(135deg,rgba(9,20,43,0.9),rgba(4,8,20,0.96))] p-6 shadow-[0_20px_80px_rgba(0,0,0,0.35)] md:p-10">
        <div className="max-w-3xl">
          <p className="text-xs uppercase tracking-[0.25em] text-cyan-200">{text.eyebrow}</p>
          <h2 className="mt-4 text-3xl font-semibold leading-tight md:text-5xl">{text.title}</h2>
          <p className="mt-4 text-base text-white/75 md:text-lg">{text.subtitle}</p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-2">
          <article className="rounded-2xl border border-cyan-300/20 bg-cyan-300/8 p-5 md:col-span-2">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-cyan-200">
              <Scale className="h-4 w-4" />
              {program.eyebrow}
            </div>
            <p className="mt-4 text-lg font-medium">{program.title}</p>
            <p className="mt-3 text-sm text-white/70">{program.body}</p>
          </article>
          <article className="rounded-2xl border border-emerald-300/25 bg-emerald-400/8 p-5">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-emerald-200">
              <ShieldCheck className="h-4 w-4" />
              {text.withUs}
            </div>
            <p className="mt-4 text-lg font-medium">{payload.investor_takeaway.with_ls}</p>
            <p className="mt-3 text-sm text-white/70">{text.withUsBody}</p>
          </article>
          <article className="rounded-2xl border border-rose-300/20 bg-rose-400/8 p-5">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.18em] text-rose-200">
              <FileText className="h-4 w-4" />
              {text.withoutUs}
            </div>
            <p className="mt-4 text-lg font-medium">{payload.investor_takeaway.without_ls}</p>
            <p className="mt-3 text-sm text-white/70">{text.withoutUsBody}</p>
          </article>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-4">
          {stats.map((stat) => (
            <div key={stat.label} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{stat.label}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{stat.value}</div>
            </div>
          ))}
        </div>

        <div className="mt-8 grid gap-6 lg:grid-cols-[1.4fr,0.9fr]">
          <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
            <div className="flex items-center gap-2 text-sm uppercase tracking-[0.16em] text-cyan-200">
              <Gauge className="h-4 w-4" />
              {text.benchmark}
            </div>
            <div className="mt-5 space-y-3">
              {payload.scenarios.map((scenario) => (
                <div key={scenario.name} className="rounded-xl border border-white/8 bg-white/5 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium">
                        {scenarioLabels[lang][scenario.name as keyof (typeof scenarioLabels)[typeof lang]] || scenario.name}
                      </p>
                      <p className="mt-1 text-sm text-white/65">{scenario.notes}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-xl font-semibold text-cyan-100">{scenario.seconds.toFixed(2)}s</p>
                      <p className="text-xs uppercase tracking-[0.15em] text-white/55">{scenario.commands} {text.commands}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="flex items-center gap-2 text-sm uppercase tracking-[0.16em] text-cyan-200">
                <Scale className="h-4 w-4" />
                {text.legal}
              </div>
              <ul className="mt-4 space-y-3 text-sm text-white/80">
                {payload.investor_takeaway.legal_and_audit.map((item) => (
                  <li key={item} className="rounded-xl border border-white/8 bg-white/5 px-3 py-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-amber-300/20 bg-amber-400/8 p-5 text-sm text-amber-50/90">
              <div className="text-xs uppercase tracking-[0.16em] text-amber-100/80">{text.disclaimerLabel}</div>
              <p className="mt-3">{payload.investor_takeaway.disclaimer}</p>
            </div>
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-white/10 bg-black/25 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <div className="text-sm uppercase tracking-[0.16em] text-cyan-200">{text.walkthrough}</div>
              <div className="mt-2 text-lg font-medium text-white">{text.terminalLabel}</div>
            </div>
            <div className="inline-flex rounded-full border border-white/10 bg-white/5 p-1">
              <button
                onClick={() => setMode('with')}
                className={`rounded-full px-4 py-2 text-sm transition ${mode === 'with' ? 'bg-cyan-300 text-slate-950' : 'text-white/70'}`}
              >
                {text.demoWith}
              </button>
              <button
                onClick={() => setMode('without')}
                className={`rounded-full px-4 py-2 text-sm transition ${mode === 'without' ? 'bg-cyan-300 text-slate-950' : 'text-white/70'}`}
              >
                {text.demoWithout}
              </button>
            </div>
          </div>

          <div className="mt-5 rounded-2xl border border-cyan-300/15 bg-slate-950/85 p-4 font-mono text-sm text-cyan-100">
            {(mode === 'with' ? walkthrough[lang].with : walkthrough[lang].without).map((line, index) => (
              <div key={`${mode}-${index}`} className={`py-1 ${line.startsWith('$') ? 'text-cyan-200' : 'text-slate-200'}`}>
                {line}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 rounded-2xl border border-cyan-300/15 bg-[radial-gradient(circle_at_top_right,rgba(96,165,250,0.16),transparent_22rem),rgba(2,6,23,0.86)] p-5 md:p-6">
          <div className="max-w-3xl">
            <div className="text-xs uppercase tracking-[0.2em] text-cyan-200">{text.councilEyebrow}</div>
            <h3 className="mt-3 text-2xl font-semibold md:text-4xl">{text.councilTitle}</h3>
            <p className="mt-3 text-sm text-white/70 md:text-base">{text.councilSubtitle}</p>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-9">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.ledgers}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.ledgers}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.topContributor}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.top_contributor}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.successRate}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.success_rate.toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.avgResonance}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.avg_resonance.toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.avgMerit}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.avg_merit.toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.avgQuality}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{(scorecard.summary.avg_quality ?? 0).toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.avgRelationSafety}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{(scorecard.summary.avg_relation_safety ?? 0).toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.riskyCycles}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.risky_cycle_count ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.incidents}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.incident_count ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.reviewed}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{scorecard.summary.reviewed_cycle_count ?? 0}</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.approvalConv}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{(scorecard.summary.approval_conversion_rate ?? 0).toFixed(1)}%</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="text-xs uppercase tracking-[0.16em] text-white/55">{text.escalationRate}</div>
              <div className="mt-3 text-2xl font-semibold text-cyan-100">{(scorecard.summary.escalation_rate ?? 0).toFixed(1)}%</div>
            </div>
          </div>

          <div className="mt-3 text-xs uppercase tracking-[0.14em] text-white/45">
            {text.sourceLabel}: {scorecard.source}
          </div>

          <div className="mt-6 grid gap-4 xl:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-cyan-200">{text.contribFreq}</div>
              <div className="mt-4">
                <MiniBars data={scorecard.bars.best_contributor_frequency} tone="cyan" />
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-emerald-200">{text.modelLift}</div>
              <div className="mt-4">
                <MiniBars data={scorecard.bars.model_type_lift} tone="emerald" />
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-amber-200">{text.routeWins}</div>
              <div className="mt-4">
                <MiniBars data={scorecard.bars.route_wins} tone="amber" />
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-3">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-cyan-200">{text.resonanceTrend}</div>
              <div className="mt-4">
                <MiniLine data={scorecard.lines.resonance_trend} stroke="#67e8f9" />
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-emerald-200">{text.meritTrend}</div>
              <div className="mt-4">
                <MiniLine data={scorecard.lines.merit_trend} stroke="#6ee7b7" />
              </div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm uppercase tracking-[0.16em] text-rose-200">{text.incidentTrend}</div>
              <div className="mt-4">
                <MiniLine data={scorecard.lines.incident_trend ?? []} stroke="#fda4af" />
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[1.15fr,0.85fr]">
            <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
              <div className="text-sm uppercase tracking-[0.16em] text-cyan-200">{text.scorecardTakeaways}</div>
              <ul className="mt-4 space-y-3 text-sm text-white/80">
                {scorecard.takeaways.with_ls.map((item) => (
                  <li key={item} className="rounded-xl border border-white/8 bg-white/5 px-3 py-3">
                    {item}
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-amber-300/20 bg-amber-400/8 p-5 text-sm text-amber-50/90">
              <div className="text-xs uppercase tracking-[0.16em] text-amber-100/80">{text.scorecardDisclaimer}</div>
              <p className="mt-3">{scorecard.takeaways.disclaimer}</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
