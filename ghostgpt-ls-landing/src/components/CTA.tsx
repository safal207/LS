import { useTranslation } from 'react-i18next';

export default function CTA() {
  const { t } = useTranslation();

  return (
    <section className="section pb-20">
      <div className="glass p-8 text-center md:p-12">
        <h2 className="text-2xl font-semibold md:text-4xl">{t('cta.title')}</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {[t('cta.demo'), t('cta.community'), t('cta.contact')].map((label) => (
            <button
              key={label}
              className="rounded-xl border border-ghost-300/70 px-5 py-3 transition duration-300 hover:-translate-y-1 hover:bg-ghost-300 hover:text-ghost-900"
            >
              {label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
