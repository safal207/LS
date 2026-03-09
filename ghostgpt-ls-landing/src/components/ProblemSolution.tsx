import { AlertTriangle, BrainCircuit, DatabaseZap, ShieldAlert } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const icons = [DatabaseZap, BrainCircuit, ShieldAlert, AlertTriangle];

export default function ProblemSolution() {
  const { t } = useTranslation();
  const keys = ['centralized', 'size', 'hallucinations', 'memory'];

  return (
    <section className="section">
      <h2 className="mb-8 text-2xl font-semibold md:text-4xl">{t('problem.title')}</h2>
      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          {keys.map((key, i) => {
            const Icon = icons[i];
            return (
              <div key={key} className="glass flex items-center gap-3 p-4 transition hover:translate-x-1 hover:bg-white/15">
                <Icon className="h-5 w-5 text-ghost-300" />
                <p>{t(`problem.items.${key}`)}</p>
              </div>
            );
          })}
        </div>
        <div className="glass animate-pulse-glow p-8">
          <h3 className="mb-3 text-xl font-semibold text-ghost-300">{t('problem.solutionTitle')}</h3>
          <p className="text-white/90">{t('problem.solutionBody')}</p>
        </div>
      </div>
    </section>
  );
}
