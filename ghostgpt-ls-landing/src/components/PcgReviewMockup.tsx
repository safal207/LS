import { Check, Clock3, LockKeyhole, Pencil, ShieldCheck, X } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

type Decision = 'accept' | 'reject' | 'revise' | 'defer';
type Lang = 'en' | 'ru';

const proposal = {
  status: 'proposed',
  sessionSummary:
    'Strategy session where the user reframed LS as a personal, goal-directed cognitive garden rather than a generic shared network.',
  nodeFamily: 'goal',
  claim:
    'LS should focus on personal, goal-directed cognitive gardens that turn useful AI work into reviewed growth state.',
  evidence: [
    'The user described each person developing their own cognitive graph.',
    'The user said connected agents and sessions should cultivate that graph like a garden.',
    'The user connected the direction to human development and commercial value.'
  ],
  skillDelta: ['strategic_product_framing', 'architecture_boundary_setting', 'human_capital_positioning'],
  practiceNeeded:
    'Convert the insight into a schema, examples, and one small MVP flow so the direction becomes an inspectable artifact.',
  compoundingScore: 0.82,
  sharingScope: 'private'
};

const copy: Record<
  Lang,
  {
    eyebrow: string;
    title: string;
    subtitle: string;
    status: string;
    private: string;
    session: string;
    nodeFamily: string;
    claim: string;
    evidence: string;
    skillDelta: string;
    practice: string;
    score: string;
    scoreNote: string;
    boundaryTitle: string;
    boundaryBody: string;
    reviewTitle: string;
    decisionTitle: string;
    actions: Record<Decision, string>;
    decisionNotes: Record<Decision, string>;
  }
> = {
  en: {
    eyebrow: 'PCG review mockup',
    title: 'Review a proposed garden update before it becomes memory',
    subtitle:
      'A proposed update stays private and non-durable until the person accepts, rejects, revises, or defers it.',
    status: 'Proposed',
    private: 'Private by default',
    session: 'Session summary',
    nodeFamily: 'Node family',
    claim: 'Claim',
    evidence: 'Evidence',
    skillDelta: 'Skill delta',
    practice: 'Practice needed',
    score: 'Compounding score',
    scoreNote: 'fixture priority signal, not a benchmark or psychological truth claim',
    boundaryTitle: 'Sharing boundary',
    boundaryBody:
      'Durable state is off. External action is off. Sharing scope remains private until explicit human review changes it.',
    reviewTitle: 'Human review',
    decisionTitle: 'Current decision',
    actions: {
      accept: 'Accept',
      reject: 'Reject',
      revise: 'Revise',
      defer: 'Defer'
    },
    decisionNotes: {
      accept: 'Accept would commit this update into the private graph, with external sharing still blocked.',
      reject: 'Reject keeps the session as source material but prevents this claim from becoming graph state.',
      revise: 'Revise sends the claim back for a tighter statement, evidence edit, or smaller node family.',
      defer: 'Defer keeps the proposal in review without writing durable state.'
    }
  },
  ru: {
    eyebrow: 'Макет проверки PCG',
    title: 'Проверь предложение до того, как оно станет памятью',
    subtitle:
      'Обновление остается личным и не сохраняется как постоянное состояние, пока человек не примет решение.',
    status: 'На проверке',
    private: 'Личное по умолчанию',
    session: 'Сводка сессии',
    nodeFamily: 'Тип узла',
    claim: 'Утверждение',
    evidence: 'Доказательства',
    skillDelta: 'Изменение навыка',
    practice: 'Что практиковать',
    score: 'Сигнал накопления',
    scoreNote: 'локальный приоритет из примера, не бенчмарк и не оценка личности',
    boundaryTitle: 'Граница доступа',
    boundaryBody:
      'Постоянная запись выключена. Внешнее действие выключено. Доступ остается личным, пока человек явно не изменит решение.',
    reviewTitle: 'Решение человека',
    decisionTitle: 'Текущее решение',
    actions: {
      accept: 'Принять',
      reject: 'Отклонить',
      revise: 'Исправить',
      defer: 'Отложить'
    },
    decisionNotes: {
      accept: 'Принятие сохранит обновление в личный граф, но внешний доступ все равно останется закрыт.',
      reject: 'Отклонение оставит сессию как источник, но не даст утверждению стать состоянием графа.',
      revise: 'Правка вернет утверждение на уточнение: короче, с лучшими доказательствами или другим типом узла.',
      defer: 'Отложить значит оставить предложение на проверке без постоянной записи.'
    }
  }
};

const decisionIcons = {
  accept: Check,
  reject: X,
  revise: Pencil,
  defer: Clock3
} as const;

const decisionClasses = {
  accept: 'border-emerald-300/50 bg-emerald-300/15 text-emerald-50 hover:bg-emerald-300/25',
  reject: 'border-rose-300/45 bg-rose-300/12 text-rose-50 hover:bg-rose-300/22',
  revise: 'border-cyan-300/45 bg-cyan-300/12 text-cyan-50 hover:bg-cyan-300/22',
  defer: 'border-amber-300/45 bg-amber-300/12 text-amber-50 hover:bg-amber-300/22'
} as const;

export default function PcgReviewMockup() {
  const { i18n } = useTranslation();
  const lang: Lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = copy[lang];
  const [decision, setDecision] = useState<Decision>('defer');
  const scorePercent = Math.round(proposal.compoundingScore * 100);

  return (
    <section className="section" id="pcg-review-mockup">
      <div className="mb-6 max-w-3xl">
        <div className="mb-3 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
          {text.eyebrow}
        </div>
        <h2 className="text-2xl font-semibold leading-tight md:text-4xl">{text.title}</h2>
        <p className="mt-4 text-base leading-7 text-white/72">{text.subtitle}</p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
        <div className="min-w-0 rounded-lg border border-white/15 bg-slate-950/70 p-4 shadow-[0_18px_60px_rgba(2,6,23,.28)] md:p-5">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full border border-violet-300/35 bg-violet-300/12 px-3 py-1 text-xs uppercase tracking-[0.14em] text-violet-100">
                {text.status}
              </span>
              <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/35 bg-emerald-300/12 px-3 py-1 text-xs uppercase tracking-[0.14em] text-emerald-100">
                <LockKeyhole className="h-3.5 w-3.5" />
                {text.private}
              </span>
            </div>
            <span className="text-xs uppercase tracking-[0.16em] text-white/45">{proposal.status}</span>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-[0.8fr_1.2fr]">
            <div className="min-w-0 rounded-lg border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.session}</p>
              <p className="mt-3 text-sm leading-6 text-white/78">{proposal.sessionSummary}</p>
            </div>

            <div className="min-w-0 rounded-lg border border-white/10 bg-white/5 p-4">
              <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.claim}</p>
              <p className="mt-3 break-words text-base leading-7 text-white">{proposal.claim}</p>
            </div>
          </div>

          <div className="mt-4 min-w-0 rounded-lg border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.evidence}</p>
            <ul className="mt-3 grid gap-2 text-sm leading-6 text-white/78">
              {proposal.evidence.map((item) => (
                <li key={item} className="flex gap-2">
                  <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="grid min-w-0 gap-4">
          <div className="rounded-lg border border-white/15 bg-black/25 p-4 md:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.reviewTitle}</p>
                <h3 className="mt-2 text-xl font-semibold">{text.decisionTitle}</h3>
              </div>
              <span className="rounded-full border border-white/15 bg-white/8 px-3 py-1 text-xs uppercase tracking-[0.14em] text-white/70">
                {text.actions[decision]}
              </span>
            </div>

            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {(Object.keys(text.actions) as Decision[]).map((action) => {
                const Icon = decisionIcons[action];
                const active = decision === action;
                return (
                  <button
                    key={action}
                    type="button"
                    title={text.actions[action]}
                    aria-pressed={active}
                    onClick={() => setDecision(action)}
                    className={`flex min-h-12 w-full items-center justify-center gap-2 rounded-lg border px-3 py-3 text-sm font-medium transition ${
                      active ? decisionClasses[action] : 'border-white/12 bg-white/5 text-white/70 hover:bg-white/10'
                    }`}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    <span className="min-w-0 text-center leading-tight">{text.actions[action]}</span>
                  </button>
                );
              })}
            </div>

            <p
              aria-live="polite"
              className="mt-4 rounded-lg border border-white/10 bg-slate-950/70 p-3 text-sm leading-6 text-white/75"
              role="status"
            >
              {text.decisionNotes[decision]}
            </p>
          </div>

          <div className="rounded-lg border border-white/15 bg-black/25 p-4 md:p-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">{text.nodeFamily}</p>
                <p className="mt-2 text-sm font-semibold text-white">{proposal.nodeFamily}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/5 p-3">
                <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">{text.score}</p>
                <p className="mt-2 text-sm font-semibold text-cyan-100">{scorePercent}%</p>
              </div>
            </div>

            <div className="mt-4">
              <div className="h-2 overflow-hidden rounded-full bg-white/10">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-emerald-300 to-amber-300"
                  style={{ width: `${scorePercent}%` }}
                />
              </div>
              <p className="mt-2 text-xs leading-5 text-white/55">{text.scoreNote}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-white/15 bg-black/20 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.skillDelta}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {proposal.skillDelta.map((skill) => (
              <span key={skill} className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-3 py-1 text-xs text-cyan-50">
                {skill}
              </span>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-white/15 bg-black/20 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-cyan-200">{text.practice}</p>
          <p className="mt-3 text-sm leading-6 text-white/75">{proposal.practiceNeeded}</p>
        </div>

        <div className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 p-4">
          <p className="text-xs uppercase tracking-[0.16em] text-emerald-100">{text.boundaryTitle}</p>
          <p className="mt-3 text-sm leading-6 text-emerald-50/85">{text.boundaryBody}</p>
          <div className="mt-3 text-xs uppercase tracking-[0.14em] text-emerald-100/70">
            sharing_scope: {proposal.sharingScope}
          </div>
        </div>
      </div>
    </section>
  );
}
