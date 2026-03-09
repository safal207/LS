import { Fingerprint, HeartHandshake, Lightbulb, Orbit, ShieldCheck } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const config = [
  ['local', Fingerprint],
  ['causal', Lightbulb],
  ['human', HeartHandshake],
  ['anti', ShieldCheck],
  ['identity', Orbit]
] as const;

export default function Features() {
  const { t } = useTranslation();

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('features.title')}</h2>
      <div className="grid gap-4 md:grid-cols-3">
        {config.map(([key, Icon]) => (
          <article key={key} className="glass group p-5 transition hover:-translate-y-1 hover:bg-white/15">
            <Icon className="mb-3 h-6 w-6 text-ghost-300 transition group-hover:scale-110" />
            <h3 className="font-semibold">{t(`features.list.${key}.title`)}</h3>
            <p className="mt-2 text-sm text-white/80">{t(`features.list.${key}.desc`)}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
