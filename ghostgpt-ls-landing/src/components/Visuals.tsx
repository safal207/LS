import { ArrowRight, CheckCircle2, GitBranch, ShieldCheck, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

type Step = {
  title: string;
  badge: string;
  problem: string;
  result: string;
  stats: string[];
  nodes: Array<{ label: string; note: string; tone: string }>;
};

const copy: Record<'en' | 'ru', { eyebrow: string; hint: string; steps: Step[] }> = {
  en: {
    eyebrow: 'Interactive flow',
    hint: 'Click a step to see what LS changes before the answer reaches the user.',
    steps: [
      {
        title: 'Shared context',
        badge: 'Trust base',
        problem: 'Agents often continue from partial memory and silently invent the missing bridge.',
        result: 'LS keeps one shared working state: task, constraints, prior decision, and active handoff.',
        stats: ['one memory', 'one goal', 'less repeat'],
        nodes: [
          { label: 'Human', note: 'sets goal', tone: 'bg-cyan-300' },
          { label: 'LS', note: 'keeps context', tone: 'bg-blue-300' },
          { label: 'Agents', note: 'share state', tone: 'bg-emerald-300' }
        ]
      },
      {
        title: 'Risk check',
        badge: 'Before action',
        problem: 'A raw agent can suggest action before evidence, permission, or continuity is clear.',
        result: 'LS routes the draft through checks: evidence, memory consent, action boundary, and repair prompt.',
        stats: ['draft', 'check', 'repair'],
        nodes: [
          { label: 'Draft', note: 'agent output', tone: 'bg-cyan-300' },
          { label: 'Gate', note: 'evidence', tone: 'bg-amber-300' },
          { label: 'Repair', note: 'safe next step', tone: 'bg-emerald-300' }
        ]
      },
      {
        title: 'Skill capital',
        badge: 'Compounds',
        problem: 'Useful sessions disappear into chat history after the immediate task is done.',
        result: 'LS turns the session into a proposed skill, artifact, or growth direction for human review.',
        stats: ['proposal', 'consent', 'report'],
        nodes: [
          { label: 'Session', note: 'work done', tone: 'bg-cyan-300' },
          { label: 'Proposal', note: 'review', tone: 'bg-violet-300' },
          { label: 'Capital', note: 'accepted', tone: 'bg-emerald-300' }
        ]
      }
    ]
  },
  ru: {
    eyebrow: 'Интерактивный поток',
    hint: 'Нажми на шаг и посмотри, что LS меняет до того, как ответ попадет к пользователю.',
    steps: [
      {
        title: 'Общий контекст',
        badge: 'Основа доверия',
        problem: 'Агенты часто продолжают из обрывка памяти и незаметно додумывают недостающий мост.',
        result: 'LS держит единое рабочее состояние: задачу, ограничения, прошлое решение и текущую передачу.',
        stats: ['одна память', 'одна цель', 'меньше повторов'],
        nodes: [
          { label: 'Человек', note: 'ставит цель', tone: 'bg-cyan-300' },
          { label: 'LS', note: 'держит контекст', tone: 'bg-blue-300' },
          { label: 'Агенты', note: 'видят одно', tone: 'bg-emerald-300' }
        ]
      },
      {
        title: 'Проверка риска',
        badge: 'До действия',
        problem: 'Сырой агент может предложить действие до доказательств, разрешения или ясного контекста.',
        result: 'LS прогоняет черновик через проверки: доказательства, согласие на память, границу действия и подсказку для исправления.',
        stats: ['черновик', 'проверка', 'правка'],
        nodes: [
          { label: 'Черновик', note: 'ответ агента', tone: 'bg-cyan-300' },
          { label: 'Шлюз', note: 'доказательства', tone: 'bg-amber-300' },
          { label: 'Правка', note: 'безопасный шаг', tone: 'bg-emerald-300' }
        ]
      },
      {
        title: 'Капитал навыков',
        badge: 'Накопление',
        problem: 'Полезная сессия пропадает в истории чата сразу после выполнения задачи.',
        result: 'LS превращает сессию в предложенный навык, артефакт или направление роста для проверки человеком.',
        stats: ['предложение', 'согласие', 'отчет'],
        nodes: [
          { label: 'Сессия', note: 'работа сделана', tone: 'bg-cyan-300' },
          { label: 'Предложение', note: 'на проверке', tone: 'bg-violet-300' },
          { label: 'Капитал', note: 'принято', tone: 'bg-emerald-300' }
        ]
      }
    ]
  }
};

function FlowDiagram({ step }: { step: Step }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4">
      <div className="grid gap-3 md:grid-cols-3">
        {step.nodes.map((node, index) => (
          <div key={node.label} className="flex items-center gap-3">
            <div className="min-w-0 flex-1 rounded-xl border border-white/10 bg-white/5 p-4 text-center">
              <div className={`mx-auto h-4 w-4 rounded-full ${node.tone} shadow-[0_0_18px_rgba(116,247,255,.7)]`} />
              <div className="mt-3 text-sm font-semibold uppercase tracking-[0.12em] text-white/85">{node.label}</div>
              <div className="mt-1 text-xs text-cyan-100/75">{node.note}</div>
            </div>
            {index < step.nodes.length - 1 && <ArrowRight className="hidden h-5 w-5 shrink-0 text-cyan-200/70 md:block" />}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function Visuals() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'ru' ? 'ru' : 'en';
  const [active, setActive] = useState(0);
  const content = copy[lang];
  const step = content.steps[active];
  const icons = [GitBranch, ShieldCheck, Sparkles] as const;

  return (
    <section className="section" id="visual-flow">
      <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <div className="mb-3 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
            {content.eyebrow}
          </div>
          <h2 className="text-2xl font-semibold md:text-4xl">{t('visuals.title')}</h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-white/65">{content.hint}</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {content.steps.map((item, index) => {
          const Icon = icons[index] ?? CheckCircle2;
          const isActive = active === index;
          return (
            <button
              key={item.title}
              type="button"
              onClick={() => setActive(index)}
              className={`rounded-2xl border p-4 text-left transition ${
                isActive
                  ? 'border-cyan-300/60 bg-cyan-300/15 shadow-[0_0_32px_rgba(34,211,238,.16)]'
                  : 'border-white/10 bg-white/5 hover:-translate-y-1 hover:bg-white/10'
              }`}
            >
              <Icon className="h-5 w-5 text-cyan-200" />
              <div className="mt-3 flex items-center justify-between gap-3">
                <span className="text-lg font-semibold">{item.title}</span>
                <span className="rounded-full border border-cyan-300/25 px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-cyan-100">
                  {item.badge}
                </span>
              </div>
              <p className="mt-3 text-sm leading-6 text-white/65">{item.problem}</p>
            </button>
          );
        })}
      </div>

      <div className="glass mt-5 p-5 md:p-6">
        <div className="flex flex-col gap-5 lg:grid lg:grid-cols-[1.1fr_0.9fr]">
          <FlowDiagram step={step} />
          <div className="flex flex-col justify-between gap-5">
            <div>
              <div className="text-xs uppercase tracking-[0.18em] text-cyan-200">{step.badge}</div>
              <h3 className="mt-2 text-2xl font-semibold">{step.title}</h3>
              <p className="mt-4 text-base leading-7 text-white/75">{step.result}</p>
            </div>
            <div className="grid grid-cols-3 gap-2">
              {step.stats.map((stat) => (
                <span
                  key={stat}
                  className="rounded-xl border border-cyan-300/20 bg-cyan-300/10 px-3 py-3 text-center text-xs uppercase tracking-[0.12em] text-cyan-100"
                >
                  {stat}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
