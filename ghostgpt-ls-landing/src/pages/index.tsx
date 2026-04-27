import { useTranslation } from 'react-i18next';
import CTA from '../components/CTA';
import Features from '../components/Features';
import Hero from '../components/Hero';
import OperatorDelta from '../components/OperatorDelta';
import ProblemSolution from '../components/ProblemSolution';
import ReflectiveRuntime from '../components/ReflectiveRuntime';
import Roadmap from '../components/Roadmap';
import HcpMarketplacePanel from '../components/HcpMarketplacePanel';
import RuntimeLivePanel from '../components/RuntimeLivePanel';
import Visuals from '../components/Visuals';

export default function IndexPage() {
  const { i18n } = useTranslation();

  const onSwitchLang = () => {
    i18n.changeLanguage(i18n.language === 'ru' ? 'en' : 'ru');
  };

  return (
    <main>
      <Hero onSwitchLang={onSwitchLang} />
      <ProblemSolution />
      <Features />
      <ReflectiveRuntime />
      <RuntimeLivePanel />
      <HcpMarketplacePanel />
      <OperatorDelta />
      <Roadmap />
      <Visuals />
      <CTA />
    </main>
  );
}
