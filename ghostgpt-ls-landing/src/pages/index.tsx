import { useTranslation } from 'react-i18next';
import CTA from '../components/CTA';
import Features from '../components/Features';
import Hero from '../components/Hero';
import ProblemSolution from '../components/ProblemSolution';
import Roadmap from '../components/Roadmap';
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
      <Roadmap />
      <Visuals />
      <CTA />
    </main>
  );
}
