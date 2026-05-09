import { useTranslation } from 'react-i18next';

export default function ReflectiveRuntime() {
  const { t } = useTranslation();

  const architectureItems = t('runtime.architecture.items', { returnObjects: true }) as string[];

  return (
    <section className="section" id="runtime-explainer">
      <div className="glass p-8 md:p-10">
        <p className="text-xs uppercase tracking-[0.2em] text-cyan-200">{t('runtime.eyebrow')}</p>
        <h2 className="mt-3 text-3xl font-semibold md:text-4xl">{t('runtime.title')}</h2>

        <div className="mt-8 grid gap-6 md:grid-cols-3">
          <article className="rounded-xl border border-white/15 bg-black/20 p-5">
            <h3 className="text-lg font-semibold text-cyan-100">{t('runtime.problem.title')}</h3>
            <p className="mt-3 text-sm text-slate-200">{t('runtime.problem.body')}</p>
          </article>

          <article className="rounded-xl border border-white/15 bg-black/20 p-5">
            <h3 className="text-lg font-semibold text-cyan-100">{t('runtime.solution.title')}</h3>
            <p className="mt-3 text-sm text-slate-200">{t('runtime.solution.body')}</p>
          </article>

          <article className="rounded-xl border border-white/15 bg-black/20 p-5">
            <h3 className="text-lg font-semibold text-cyan-100">{t('runtime.architecture.title')}</h3>
            <ul className="mt-3 space-y-2 text-sm text-slate-200">
              {architectureItems.map((item) => (
                <li key={item}>- {item}</li>
              ))}
            </ul>
          </article>
        </div>
      </div>
    </section>
  );
}
