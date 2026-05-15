import { Suspense, lazy } from 'react';
import { useTranslation } from 'react-i18next';
import GrantReviewer from '../components/GrantReviewer';
import Hero from '../components/Hero';

const CTA = lazy(() => import('../components/CTA'));
const Features = lazy(() => import('../components/Features'));
const OperatorDelta = lazy(() => import('../components/OperatorDelta'));
const PluginCapabilities = lazy(() => import('../components/PluginCapabilities'));
const ProblemSolution = lazy(() => import('../components/ProblemSolution'));
const ReflectiveRuntime = lazy(() => import('../components/ReflectiveRuntime'));
const Roadmap = lazy(() => import('../components/Roadmap'));
const RuntimeLivePanel = lazy(() => import('../components/RuntimeLivePanel'));
const Visuals = lazy(() => import('../components/Visuals'));

export default function IndexPage() {
  const { i18n } = useTranslation();

  const onSwitchLang = () => {
    i18n.changeLanguage(i18n.language === 'ru' ? 'en' : 'ru');
  };

  return (
    <main>
      <Hero onSwitchLang={onSwitchLang} />
      <GrantReviewer />
      <Suspense fallback={null}>
        <PluginCapabilities />
        <ProblemSolution />
        <Features />
        <ReflectiveRuntime />
        <RuntimeLivePanel />
        <OperatorDelta />
        <Roadmap />
        <Visuals />
        <CTA />
      </Suspense>
    </main>
  );
}
