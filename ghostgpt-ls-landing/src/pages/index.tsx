import { Suspense, lazy } from 'react';
import { useTranslation } from 'react-i18next';
import AskGPTGrantReview from '../components/AskGPTGrantReview';
import GrantReviewer from '../components/GrantReviewer';
import Hero from '../components/Hero';

const CTA = lazy(() => import('../components/CTA'));
const Features = lazy(() => import('../components/Features'));
const OperatorDelta = lazy(() => import('../components/OperatorDelta'));
const PcgReviewMockup = lazy(() => import('../components/PcgReviewMockup'));
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
      <AskGPTGrantReview />
      <Suspense fallback={null}>
        <PluginCapabilities />
        <PcgReviewMockup />
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
