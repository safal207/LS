# GitHub Pages Setup

The repository is prepared to deploy the landing page from `ghostgpt-ls-landing` to GitHub Pages.

Expected public URL:

```text
https://safal207.github.io/LS/
```

## Workflow

Deployment is handled by:

```text
.github/workflows/pages.yml
```

The workflow:

1. checks out the repository,
2. installs Node dependencies in `ghostgpt-ls-landing`,
3. builds the Vite landing page,
4. copies `ghostgpt-ls-landing/dist` into `_site`,
5. uploads the Pages artifact,
6. deploys through `actions/deploy-pages`.

## Required GitHub Repository Setting

In the GitHub repository:

1. Open `Settings`.
2. Open `Pages`.
3. Set `Build and deployment` source to `GitHub Actions`.
4. Save.
5. Run the `Deploy Landing To Pages` workflow manually once, or push to `main`.

## Local Check

```bash
cd ghostgpt-ls-landing
npm ci
npm run build
```

The landing uses relative Vite assets, so the build works under the `/LS/` project path.
