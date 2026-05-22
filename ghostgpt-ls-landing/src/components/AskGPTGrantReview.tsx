import { Clipboard, ExternalLink, MessageSquareText } from 'lucide-react';
import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';

const REPO_URL = 'https://github.com/safal207/LS';
const GRANT_PATH_URL = 'https://github.com/safal207/LS/blob/main/docs/GRANT_REVIEWER_PATH.md';
const BRIEF_URL = 'https://github.com/safal207/LS/blob/main/docs/GRANT_READY_BRIEF_PERSONAL_COGNITIVE_GARDEN.md';
const DEMO_URL = 'https://github.com/safal207/LS/blob/main/docs/PERSONAL_COGNITIVE_GARDEN_RUNNER.md';
const RED_TEAM_URL = 'https://github.com/safal207/LS/blob/main/docs/PERSONAL_COGNITIVE_GARDEN_RED_TEAM.md';

type CopyState = 'idle' | 'copied' | 'failed';

const labels = {
  en: {
    eyebrow: 'Interactive reviewer check',
    title: 'Ask GPT to review the grant case',
    body:
      'This opens ChatGPT with a prebuilt prompt. The reviewer can independently ask what LS is, whether it is grant-worthy, and what evidence is still missing.',
    promptLabel: 'Generated prompt',
    copy: 'Copy prompt',
    copied: 'Copied',
    failed: 'Copy failed',
    open: 'Open in ChatGPT',
    note: 'No prompt is sent to an LS backend. The browser opens ChatGPT with the text below.'
  },
  ru: {
    eyebrow: 'Интерактив для ревьюера',
    title: 'Спросить GPT о грантовой ценности LS',
    body:
      'Блок открывает ChatGPT с готовым prompt. Ревьюер может независимо спросить, что такое LS, стоит ли давать грант и каких доказательств ещё не хватает.',
    promptLabel: 'Сформированный prompt',
    copy: 'Скопировать prompt',
    copied: 'Скопировано',
    failed: 'Не удалось скопировать',
    open: 'Открыть в ChatGPT',
    note: 'Prompt не отправляется на backend LS. Браузер просто открывает ChatGPT с текстом ниже.'
  }
};

function buildGrantReviewPrompt(language: 'en' | 'ru'): string {
  const sharedFacts = `
Project: LS / Liminal Stack landing and repository.
Repository: ${REPO_URL}
Grant reviewer path: ${GRANT_PATH_URL}
Grant-ready brief: ${BRIEF_URL}
Demo path: ${DEMO_URL}
Red-team safety boundary: ${RED_TEAM_URL}

Core claim:
LS is a local-first coordination and oversight runtime for human-plus-model work. Its current grant-facing package focuses on Personal Cognitive Garden: turning AI-assisted sessions into evidence-backed, human-reviewed, human-owned skill capital without employer surveillance.

What to evaluate:
- Is the research question clear and fundable?
- Is the artifact path reproducible enough for a grant reviewer?
- Are the safety boundaries credible, especially anti-surveillance and consent-before-memory?
- Is the project technically differentiated from ordinary AI productivity dashboards?
- What evidence, experiments, docs, or demos should be added before funding?
`;

  if (language === 'ru') {
    return `Ты выступаешь как строгий, но конструктивный грантовый рецензент AI safety / human-centered AI / open-source infrastructure.

Задача: оцени проект LS по материалам ниже.

Ответь структурно:
1. Что это за проект в 5-7 предложениях.
2. В чём его сильная исследовательская гипотеза.
3. Чем он отличается от обычного AI productivity / dashboard инструмента.
4. Стоит ли рассматривать его на грант: yes / no / maybe.
5. Какие 3-5 доказательств или артефактов сильнее всего повысили бы шанс funding.
6. Главные риски/слабые места.
7. Итоговая рекомендация для grant reviewer.

${sharedFacts}`.trim();
  }

  return `You are a strict but constructive grant reviewer for AI safety, human-centered AI, and open-source infrastructure.

Task: evaluate the LS project using the materials below.

Answer in a structured way:
1. Explain what this project is in 5-7 sentences.
2. Identify its strongest research hypothesis.
3. Explain how it differs from an ordinary AI productivity dashboard.
4. State whether it should be considered for grant funding: yes / no / maybe.
5. List the 3-5 evidence artifacts that would most improve its funding case.
6. Identify the main risks or weak points.
7. Give a final grant-review recommendation.

${sharedFacts}`.trim();
}

function chatGptUrl(prompt: string): string {
  return `https://chatgpt.com/?q=${encodeURIComponent(prompt)}`;
}

export default function AskGPTGrantReview() {
  const { i18n } = useTranslation();
  const lang = i18n.language === 'ru' ? 'ru' : 'en';
  const text = labels[lang];
  const prompt = useMemo(() => buildGrantReviewPrompt(lang), [lang]);
  const [copyState, setCopyState] = useState<CopyState>('idle');

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopyState('copied');
      window.setTimeout(() => setCopyState('idle'), 1800);
    } catch {
      setCopyState('failed');
      window.setTimeout(() => setCopyState('idle'), 1800);
    }
  };

  return (
    <section className="section" id="ask-gpt-review">
      <div className="glass overflow-hidden p-6 md:p-8">
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.1fr] lg:items-start">
          <div>
            <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-cyan-300/30 bg-cyan-300/10 px-4 py-1 text-xs uppercase tracking-widest text-cyan-100">
              <MessageSquareText className="h-3.5 w-3.5" />
              {text.eyebrow}
            </div>
            <h2 className="text-2xl font-semibold md:text-4xl">{text.title}</h2>
            <p className="mt-4 text-sm leading-6 text-white/75 md:text-base">{text.body}</p>
            <p className="mt-4 rounded-xl border border-white/10 bg-black/20 p-3 text-xs leading-5 text-white/60">
              {text.note}
            </p>
            <div className="mt-5 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={copyPrompt}
                className="inline-flex items-center gap-2 rounded-xl border border-cyan-300/60 px-4 py-3 text-sm font-medium text-cyan-100 transition hover:bg-cyan-300 hover:text-ghost-900"
              >
                <Clipboard className="h-4 w-4" />
                {copyState === 'copied' ? text.copied : copyState === 'failed' ? text.failed : text.copy}
              </button>
              <a
                href={chatGptUrl(prompt)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 rounded-xl bg-cyan-200 px-4 py-3 text-sm font-semibold text-ghost-900 transition hover:bg-white"
              >
                <ExternalLink className="h-4 w-4" />
                {text.open}
              </a>
            </div>
          </div>

          <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
            <div className="mb-3 text-xs uppercase tracking-wider text-white/60">{text.promptLabel}</div>
            <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-cyan-50/85">
              {prompt}
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}
