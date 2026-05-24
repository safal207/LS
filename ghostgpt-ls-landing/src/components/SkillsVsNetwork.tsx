import { Activity, BadgeCheck, BrainCircuit, GitBranch, Network, Route, ShieldCheck, UserCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Lang = 'en' | 'ru';

const copy = {
  en: {
    eyebrow: 'Not just skills',
    title: 'Skills tell one agent what to do. LS learns which route actually worked.',
    subtitle:
      'A skill is useful instruction. LS adds route memory, measurements, evidence, and contribution signals so the next model or IDE agent can start from verified experience.',
    skillTitle: 'Skills',
    networkTitle: 'LS Network',
    skillLead: 'Instruction for one agent',
    networkLead: 'Accumulated route experience',
    footnote:
      'LS does not claim to train model weights. It makes cooperation more precise by remembering which role route produced evidence-backed results.',
    rows: [
      ['Static instruction', 'Accumulated experience'],
      ['Helps one agent act', 'Helps the network choose a route'],
      ['Says how to do the task', 'Measures what actually worked'],
      ['Usually does not know who contributed', 'Scores role and actor contribution'],
      ['May skip result verification', 'Requires evidence, trace, and route score'],
      ['Lives inside an agent', 'Connects Codex, OpenCode, Cursor, and models through MCP']
    ],
    signals: [
      { label: 'route memory', icon: Route },
      { label: 'evidence gates', icon: ShieldCheck },
      { label: 'contribution ledger', icon: UserCheck },
      { label: 'precision metrics', icon: Activity }
    ]
  },
  ru: {
    eyebrow: 'Не просто skills',
    title: 'Skills говорят агенту, что делать. LS запоминает, какой маршрут реально сработал.',
    subtitle:
      'Skill полезен как инструкция. LS добавляет память маршрутов, метрики, доказательства и вклад участников, чтобы следующая модель или IDE-агент начинали с проверенного опыта.',
    skillTitle: 'Skills',
    networkTitle: 'LS-сеть',
    skillLead: 'Инструкция для одного агента',
    networkLead: 'Накопленный опыт маршрутов',
    footnote:
      'LS не утверждает, что обучает веса моделей. Сеть становится точнее, потому что запоминает, какой маршрут ролей дал проверенный результат.',
    rows: [
      ['Статичная инструкция', 'Накапливаемый опыт'],
      ['Помогает одному агенту действовать', 'Помогает сети выбирать маршрут'],
      ['Говорит, как делать задачу', 'Измеряет, что сработало'],
      ['Обычно не знает, кто внес вклад', 'Считает вклад ролей и участников'],
      ['Может не проверять результат', 'Требует доказательства, след и оценку маршрута'],
      ['Живет внутри агента', 'Соединяет Codex, OpenCode, Cursor и модели через MCP']
    ],
    signals: [
      { label: 'память маршрутов', icon: Route },
      { label: 'ворота доказательств', icon: ShieldCheck },
      { label: 'журнал вклада', icon: UserCheck },
      { label: 'метрики точности', icon: Activity }
    ]
  }
} as const;

export default function SkillsVsNetwork() {
  const { i18n } = useTranslation();
  const lang: Lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = copy[lang];

  return (
    <section className="section" id="skills-vs-network">
      <div className="max-w-3xl">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
          <BrainCircuit className="h-3.5 w-3.5" />
          {text.eyebrow}
        </div>
        <h2 className="text-3xl font-semibold leading-tight md:text-5xl">{text.title}</h2>
        <p className="mt-5 text-base leading-7 text-white/75 md:text-lg">{text.subtitle}</p>
      </div>

      <div className="mt-8 grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="glass p-5">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
            <div className="rounded-lg border border-white/10 bg-slate-950/45 p-4">
              <div className="flex items-center gap-3">
                <GitBranch className="h-5 w-5 text-white/65" />
                <h3 className="text-xl font-semibold">{text.skillTitle}</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-white/65">{text.skillLead}</p>
            </div>

            <div className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 p-4">
              <div className="flex items-center gap-3">
                <Network className="h-5 w-5 text-cyan-100" />
                <h3 className="text-xl font-semibold text-cyan-50">{text.networkTitle}</h3>
              </div>
              <p className="mt-3 text-sm leading-6 text-cyan-50/75">{text.networkLead}</p>
            </div>
          </div>

          <div className="mt-5 grid gap-2 sm:grid-cols-2">
            {text.signals.map(({ label, icon: Icon }) => (
              <div key={label} className="flex min-w-0 items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
                <Icon className="h-4 w-4 shrink-0 text-cyan-200" />
                <span className="min-w-0 text-sm font-medium leading-tight text-white/75">{label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="min-w-0 overflow-hidden rounded-2xl border border-white/15 bg-white/5">
          <div className="grid grid-cols-2 border-b border-white/10 bg-slate-950/55">
            <div className="border-r border-white/10 px-4 py-3 text-sm font-semibold text-white/70">{text.skillTitle}</div>
            <div className="px-4 py-3 text-sm font-semibold text-cyan-100">{text.networkTitle}</div>
          </div>

          <div className="divide-y divide-white/10">
            {text.rows.map(([skill, network]) => (
              <div key={`${skill}-${network}`} className="grid grid-cols-1 md:grid-cols-2">
                <div className="min-w-0 border-white/10 px-4 py-4 md:border-r">
                  <p className="break-words text-sm leading-6 text-white/65">{skill}</p>
                </div>
                <div className="min-w-0 bg-cyan-300/5 px-4 py-4">
                  <div className="flex gap-3">
                    <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-200" />
                    <p className="break-words text-sm font-medium leading-6 text-cyan-50/85">{network}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <p className="mt-5 max-w-3xl text-sm leading-6 text-white/58">{text.footnote}</p>
    </section>
  );
}
