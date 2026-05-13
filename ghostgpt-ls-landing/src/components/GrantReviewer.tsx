import { ShieldCheck, Sprout, TerminalSquare } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const links = [
  {
    key: 'brief',
    href: 'https://github.com/safal207/LS/blob/main/docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md'
  },
  {
    key: 'demo',
    href: 'https://github.com/safal207/LS/blob/main/docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md'
  },
  {
    key: 'redteam',
    href: 'https://github.com/safal207/LS/blob/main/docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md'
  }
];

const icons = [Sprout, TerminalSquare, ShieldCheck];

export default function GrantReviewer() {
  const { t } = useTranslation();
  const cards = t('grant.cards', { returnObjects: true }) as Array<{ title: string; body: string }>;
  const steps = t('grant.path', { returnObjects: true }) as string[];

  return (
    <section className="section" id="grant-reviewer">
      <div className="glass p-6 md:p-10">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mb-4 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
            {t('grant.eyebrow')}
          </div>
          <h2 className="text-3xl font-semibold md:text-5xl">{t('grant.title')}</h2>
          <p className="mt-5 text-base text-white/75 md:text-lg">{t('grant.subtitle')}</p>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {cards.map((card, index) => {
            const Icon = icons[index] ?? Sprout;
            return (
              <div key={card.title} className="rounded-2xl border border-white/10 bg-white/5 p-5 text-left">
                <Icon className="mb-4 h-6 w-6 text-cyan-200" />
                <h3 className="text-lg font-semibold">{card.title}</h3>
                <p className="mt-3 text-sm leading-6 text-white/70">{card.body}</p>
              </div>
            );
          })}
        </div>

        <div className="mt-8 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-5">
          <h3 className="text-xl font-semibold">{t('grant.pathTitle')}</h3>
          <ol className="mt-4 grid gap-3 text-left text-sm text-white/75 md:grid-cols-2">
            {steps.map((step) => (
              <li key={step} className="rounded-xl bg-black/20 px-4 py-3">{step}</li>
            ))}
          </ol>
        </div>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {links.map((link) => (
            <a
              key={link.key}
              href={link.href}
              target="_blank"
              rel="noreferrer"
              className="rounded-xl border border-ghost-300/70 px-5 py-3 transition duration-300 hover:-translate-y-1 hover:bg-ghost-300 hover:text-ghost-900"
            >
              {t(`grant.links.${link.key}`)}
            </a>
          ))}
        </div>
      </div>
    </section>
  );
}
