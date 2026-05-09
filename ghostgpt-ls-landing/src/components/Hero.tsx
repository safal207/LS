import { Sparkles } from 'lucide-react';
import { useTranslation } from 'react-i18next';

type Props = { onSwitchLang: () => void };

export default function Hero({ onSwitchLang }: Props) {
  const { t } = useTranslation();
  const proof = t('hero.proof', { returnObjects: true }) as string[];

  return (
    <section className="section pt-6 md:pt-10">
      <div className="mb-6 flex justify-end">
        <button
          onClick={onSwitchLang}
          className="glass px-4 py-2 text-sm transition hover:scale-105 hover:bg-white/20"
        >
          {t('nav.switch')}
        </button>
      </div>
      <div className="glass animate-fade-up p-6 text-center md:p-10 lg:p-12">
        <div className="mb-4 inline-flex items-center gap-2 rounded-full bg-ghost-300/20 px-4 py-1 text-xs uppercase tracking-widest text-ghost-300">
          <Sparkles className="h-3.5 w-3.5" /> {t('hero.eyebrow')}
        </div>
        <h1 className="mx-auto max-w-4xl text-3xl font-semibold leading-tight md:text-5xl lg:text-6xl">
          {t('hero.title')}
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-base text-white/80 md:text-lg lg:text-xl">
          {t('hero.subtitle')}
        </p>
        <div className="mx-auto mt-6 grid max-w-3xl gap-2 text-sm text-cyan-100/85 md:grid-cols-3">
          {proof.map((item) => (
            <div key={item} className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2">
              {item}
            </div>
          ))}
        </div>
        <a
          href="#operator-delta"
          className="mt-6 inline-flex rounded-xl bg-ghost-500 px-7 py-3 font-medium transition duration-300 hover:-translate-y-1 hover:bg-ghost-300 hover:text-ghost-900"
        >
          {t('hero.cta')}
        </a>
      </div>
    </section>
  );
}
