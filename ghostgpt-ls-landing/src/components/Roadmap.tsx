import { useTranslation } from 'react-i18next';

type Phase = { q: string; name: string };

export default function Roadmap() {
  const { t } = useTranslation();
  const phases = t('roadmap.phases', { returnObjects: true }) as Phase[];

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('roadmap.title')}</h2>
      <div className="relative space-y-4 before:absolute before:bottom-0 before:left-2 before:top-0 before:w-0.5 before:bg-ghost-300/40">
        {phases.map((phase, i) => (
          <div key={phase.q} className="glass ml-6 p-4 transition hover:bg-white/15">
            <div className="absolute left-0 mt-2 h-4 w-4 rounded-full bg-ghost-300" style={{ top: `${i * 92 + 8}px` }} />
            <p className="text-sm text-ghost-300">{phase.q}</p>
            <p className="font-medium">{phase.name}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
