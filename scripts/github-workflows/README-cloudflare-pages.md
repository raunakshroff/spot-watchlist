# Cloudflare Pages workflow (not yet in .github/workflows)

File: `cloudflare-pages.yml` in this folder.

The GITHUB_TOKEN on the box lacks classic `workflow` scope, so this branch cannot create `.github/workflows/*.yml` on the remote. To install:

1. Merge this branch (or copy the YAML) after Raunak grants a PAT with `workflow` scope, **or**
2. In the GitHub UI: Actions → New workflow → paste contents of `cloudflare-pages.yml`, **or**
3. From a machine with a workflow-scoped PAT:
   ```bash
   mkdir -p .github/workflows
   cp scripts/github-workflows/cloudflare-pages.yml .github/workflows/
   git add .github/workflows/cloudflare-pages.yml
   git commit -m "ci: install Cloudflare Pages deploy workflow"
   git push
   ```

Also add secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID`, and set `vite.config.ts` `base` to `"/"` before the first deploy.
