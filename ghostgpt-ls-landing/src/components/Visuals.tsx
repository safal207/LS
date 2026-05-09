import { useTranslation } from 'react-i18next';

type VisualCard = {
  title: string;
  badge: string;
  purpose: string;
  readout: string;
  stats: string[];
};

function Diagram({ index, lang }: { index: number; lang: 'en' | 'ru' }) {
  if (index === 0) {
    const nodes =
      lang === 'ru'
        ? [
            { label: 'человек', note: 'ставит цель', color: 'bg-cyan-300' },
            { label: 'LS', note: 'держит память', color: 'bg-blue-300' },
            { label: 'агенты', note: 'работают синхронно', color: 'bg-emerald-300' }
          ]
        : [
            { label: 'operator', note: 'sets task', color: 'bg-cyan-300' },
            { label: 'memory', note: 'keeps context', color: 'bg-blue-300' },
            { label: 'agents', note: 'share one version', color: 'bg-emerald-300' }
          ];

    return (
      <div className="flex h-full items-center gap-2">
        {nodes.map((node, nodeIdx) => (
          <div key={node.label} className="flex flex-1 items-center gap-2">
            <div className="min-w-0 flex-1 rounded-xl border border-white/10 bg-slate-950/70 px-3 py-3 text-center">
              <div className={`mx-auto h-3.5 w-3.5 rounded-full ${node.color} shadow-[0_0_18px_rgba(116,247,255,.7)]`} />
              <div className="mt-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-white/75">
                {node.label}
              </div>
              <div className="mt-1 text-[10px] leading-tight text-cyan-100/75">
                {node.note}
              </div>
            </div>
            {nodeIdx < nodes.length - 1 && (
              <div className="flex w-8 shrink-0 items-center text-cyan-200/70">
                <div className="h-px flex-1 bg-cyan-200/50" />
                <div className="h-2 w-2 rotate-45 border-r border-t border-cyan-200/60" />
              </div>
            )}
          </div>
        ))}
      </div>
    );
  }

  if (index === 1) {
    return (
      <div className="flex h-full items-center gap-3">
        {(lang === 'ru'
          ? ['черновик', 'проверка', 'правка', 'одобрение']
          : ['agent drafts', 'LS reviews', 'LS improves', 'you approve']
        ).map((step, stepIdx) => (
          <div key={step} className="flex flex-1 flex-col items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_18px_rgba(116,247,255,.8)]" />
            <div className="h-px w-full bg-cyan-200/35" />
            <span className="text-[10px] uppercase tracking-[0.12em] text-white/65">
              {stepIdx + 1}. {step}
            </span>
          </div>
        ))}
      </div>
    );
  }

  const growth =
    lang === 'ru'
      ? [
          { label: 'контекст сохранен', value: '1', height: 54 },
          { label: 'риск найден', value: '2', height: 66 },
          { label: 'ответ улучшен', value: '3', height: 80 },
          { label: 'можно отправлять', value: '4', height: 92 }
        ]
      : [
          { label: 'start', value: '42%', height: 42 },
          { label: 'after edits', value: '58%', height: 58 },
          { label: 'fewer errors', value: '73%', height: 73 },
          { label: 'stable', value: '86%', height: 86 }
        ];

  return (
    <div className="flex h-full items-end gap-3">
      {growth.map((item) => (
        <div key={item.label} className="flex flex-1 flex-col items-center gap-2">
          <span className="text-[10px] font-semibold text-cyan-100">{item.value}</span>
          <div
            className="w-full rounded-t-lg bg-gradient-to-t from-blue-500/55 to-cyan-300"
            style={{ height: `${item.height}%` }}
          />
          <span className="text-center text-[9px] uppercase leading-tight tracking-[0.08em] text-white/65">
            {item.label}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function Visuals() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'ru' ? 'ru' : 'en';

  const cards: Record<'en' | 'ru', VisualCard[]> = {
    en: [
      {
        title: t('visuals.web4'),
        badge: 'Memory mesh',
        purpose: 'Shows where operator context lives across agents, tools, and sessions.',
        readout: 'Use it to see whether a task is grounded in shared memory or drifting into an isolated thread.',
        stats: ['agents', 'memory', 'handoff']
      },
      {
        title: t('visuals.temporal'),
        badge: 'Causal timeline',
        purpose: 'Shows the order of decisions, approvals, edits, and model outputs.',
        readout: 'Use it to replay why the system reached a recommendation before approving it.',
        stats: ['cause', 'review', 'repair']
      },
      {
        title: t('visuals.growth'),
        badge: 'Stability trend',
        purpose: 'Shows whether repeated feedback is making the runtime more reliable.',
        readout: 'Use it to track fewer contradictions, better routing, and stronger answer quality over time.',
        stats: ['quality', 'trust', 'drift']
      }
    ],
    ru: [
      {
        title: t('visuals.web4'),
        badge: 'Основа доверия',
        purpose: 'Все агенты работают из одной памяти: задача, стиль, ограничения и прошлые решения не распадаются по разным чатам.',
        readout: 'Для рынка это важно: чем больше агентов у пользователя, тем ценнее слой, который держит общий контекст.',
        stats: ['одна память', 'единая цель', 'меньше повторов']
      },
      {
        title: t('visuals.temporal'),
        badge: 'Контроль риска',
        purpose: 'Ответ проходит понятный путь: агент пишет черновик, LS проверяет слабые места, человек видит правку и решает.',
        readout: 'Для клиента это снимает страх: ИИ не публикует сырой результат без проверки и человеческого контроля.',
        stats: ['черновик', 'проверка', 'решение']
      },
      {
        title: t('visuals.growth'),
        badge: 'Накопление ценности',
        purpose: 'Каждая правка становится частью стандарта: следующие ответы ближе к нужному уровню и требуют меньше ручной доработки.',
        readout: 'Для продукта это главное: LS становится ценнее с каждым использованием, потому что учится на реальных решениях.',
        stats: ['учится', 'улучшает', 'масштабирует']
      }
    ]
  };

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('visuals.title')}</h2>

      <div className="grid gap-5 md:grid-cols-3">
        {cards[lang].map((card, idx) => (
          <article
            key={card.title}
            className="glass group flex min-h-[22rem] flex-col p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15"
          >
            <div className="flex items-center justify-between gap-3">
              <p className="text-base font-semibold text-ghost-200">{card.title}</p>
              <div className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-[10px] uppercase tracking-[0.18em] text-cyan-200">
                {card.badge}
              </div>
            </div>

            <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/65 p-4">
              <div className="relative h-32 rounded-[1.1rem] border border-white/10 bg-[linear-gradient(135deg,rgba(15,23,42,.95),rgba(30,64,175,.28))] p-4">
                <Diagram index={idx} lang={lang} />
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                {card.stats.map((stat) => (
                  <span
                    key={stat}
                    className="rounded-full border border-white/10 bg-white/5 px-2 py-1 text-center text-[10px] uppercase tracking-[0.12em] text-white/60"
                  >
                    {stat}
                  </span>
                ))}
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-white/70">{card.purpose}</p>
            <p className="mt-3 border-t border-white/10 pt-3 text-xs leading-5 text-cyan-100/80">
              {card.readout}
            </p>
          </article>
        ))}
      </div>

    </section>
  );
}
