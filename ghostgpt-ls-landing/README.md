# GhostGPT LS Landing

Bilingual (RU/EN) marketing landing page for GhostGPT LS using React + Tailwind + i18next.

## Run

```bash
npm install
cp .env.example .env   # optional: sets VITE_REFLECTION_API_BASE and VITE_HCP_API_BASE
npm run dev
```

Runtime Live and HCP Marketplace panels need the Python APIs. From the **repository root**, see `docs/DEV_LANDING_STACK.md` or run `.\scripts\dev_landing_stack.ps1` (Windows) to start both backends, then `npm run dev` here.

## Build for GitHub Pages/FastAPI static hosting

```bash
npm run build
```

Artifacts are generated in `dist/` and can be served by GitHub Pages or mounted by FastAPI static files.


## Notes

- Dashboard mockups are rendered with pure React/Tailwind UI blocks (no binary GIF assets), which keeps PR diff text-only.
