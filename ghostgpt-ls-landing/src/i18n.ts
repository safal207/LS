import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import en from '../i18n/en.json';
import ru from '../i18n/ru.json';

function silenceI18nextSponsorLogDuringInit<T>(init: () => T): T {
  if (!import.meta.env.PROD) {
    return init();
  }

  const originalLog = console.log;
  console.log = (...args: unknown[]) => {
    const firstArg = String(args[0] ?? '');
    if (firstArg.includes('i18next is maintained with support from Locize')) {
      return;
    }
    originalLog(...args);
  };

  try {
    return init();
  } finally {
    console.log = originalLog;
  }
}

silenceI18nextSponsorLogDuringInit(() => {
  i18n.use(initReactI18next).init({
    resources: { en: { translation: en }, ru: { translation: ru } },
    lng: 'en',
    fallbackLng: 'en',
    debug: false,
    saveMissing: false,
    interpolation: { escapeValue: false }
  });
});

export default i18n;
