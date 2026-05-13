import { useTranslation } from 'react-i18next';

export default function CTA() {
  const { t } = useTranslation();
  const actions = [
    {
      label: t('cta.demo'),
      href: 'https://github.com/safal207/LS/blob/main/docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md'
    },
    {
      label: t('cta.community'),
      href: 'https://github.com/safal207/LS/blob/main/docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md'
    },
    { label: t('cta.contact'), href: 'mailto:core@ghostos.ai' }
  ];

  return (
    <section className="section pb-20" id="contact-cta">
      <div className="glass p-8 text-center md:p-12">
        <h2 className="text-2xl font-semibold md:text-4xl">{t('cta.title')}</h2>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {actions.map((action) => (
            <a
              key={action.label}
              href={action.href}
              target={action.href.startsWith('http') ? '_blank' : undefined}
              rel={action.href.startsWith('http') ? 'noreferrer' : undefined}
              className="rounded-xl border border-ghost-300/70 px-5 py-3 transition duration-300 hover:-translate-y-1 hover:bg-ghost-300 hover:text-ghost-900"
            >
              {action.label}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
