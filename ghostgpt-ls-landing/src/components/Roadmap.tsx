import { ArrowUpRight } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Phase = { q: string; name: string };

export default function Roadmap() {
  const { t, i18n } = useTranslation();
  const phases = t('roadmap.phases', { returnObjects: true }) as Phase[];
  const lang = i18n.language === 'ru' ? 'ru' : 'en';

  const captions = {
    en: [
      'Operator review becomes visible and inspectable.',
      'Temporal memory starts shaping decisions in motion.',
      'Cross-device coordination leaves the single-machine box.',
      'The intelligence marketplace turns into an operational layer.'
    ],
    ru: [
      'Операторский review становится видимым и проверяемым.',
      'Временная память начинает влиять на решения прямо в потоке.',
      'Координация выходит за пределы одной машины.',
      'Intelligence marketplace превращается в рабочий слой.'
    ]
  } as const;

  return (
    <section className="section">
      <div className="mb-8 flex items-end justify-between gap-4">
        <h2 className="text-2xl font-semibold md:text-4xl">{t('roadmap.title')}</h2>
        <div className="hidden text-sm text-white/50 md:block">2026 → 2027</div>
      </div>

      <div className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        {phases.map((phase, i) => (
          <article
            key={phase.q}
            className="glass group flex min-h-[15rem] flex-col overflow-hidden p-5 transition duration-300 hover:-translate-y-1 hover:bg-white/15"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-xs font-medium tracking-[0.18em] text-cyan-200">
                {phase.q}
              </div>
              <ArrowUpRight className="h-4 w-4 text-white/35 transition group-hover:text-cyan-200" />
            </div>

            <div className="mt-6 text-xl font-semibold leading-snug text-white">
              {phase.name}
            </div>

            <p className="mt-4 text-sm leading-6 text-white/70">
              {captions[lang][i] || ''}
            </p>

            <div className="mt-auto pt-6">
              <div className="h-px w-full bg-gradient-to-r from-cyan-300/50 via-white/15 to-transparent" />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
