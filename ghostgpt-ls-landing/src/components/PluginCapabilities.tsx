import { CheckCircle2, FileText, GitPullRequestArrow, Inbox, PlugZap } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const icons = [GitPullRequestArrow, PlugZap, CheckCircle2, Inbox] as const;

export default function PluginCapabilities() {
  const { t } = useTranslation();
  const items = t('plugin.items', { returnObjects: true }) as Array<{
    title: string;
    body: string;
    command: string;
  }>;

  return (
    <section className="section" id="plugin-capabilities">
      <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
        <div>
          <div className="mb-4 inline-flex rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
            {t('plugin.eyebrow')}
          </div>
          <h2 className="text-3xl font-semibold md:text-5xl">{t('plugin.title')}</h2>
          <p className="mt-5 text-base leading-7 text-white/75 md:text-lg">{t('plugin.subtitle')}</p>

          <div className="mt-6 rounded-2xl border border-white/10 bg-black/25 p-5">
            <div className="flex items-center gap-3 text-cyan-100">
              <FileText className="h-5 w-5" />
              <span className="text-sm font-semibold uppercase tracking-widest">{t('plugin.flowTitle')}</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-white/75">{t('plugin.flowBody')}</p>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          {items.map((item, index) => {
            const Icon = icons[index] ?? PlugZap;
            return (
              <article key={item.title} className="glass p-5 transition hover:-translate-y-1 hover:bg-white/15">
                <Icon className="mb-4 h-6 w-6 text-cyan-200" />
                <h3 className="text-lg font-semibold">{item.title}</h3>
                <p className="mt-3 text-sm leading-6 text-white/70">{item.body}</p>
                <code className="mt-4 block rounded-xl border border-cyan-300/20 bg-black/30 px-3 py-2 text-xs leading-5 text-cyan-100">
                  {item.command}
                </code>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}
