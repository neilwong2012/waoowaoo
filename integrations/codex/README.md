# Codex OAuth bridge

This optional integration exposes an existing Codex ChatGPT login as the
OpenAI-compatible text and image endpoints used by waoowaoo. The default text
model is `gpt-5.6-sol`; image generation uses the bridge's Codex image path.

> [!WARNING]
> This is an experimental, unofficial compatibility bridge based on
> [`codex-as-api`](https://github.com/Eunho-J/codex-as-api). It uses your Codex
> subscription limits rather than OpenAI API billing and can require updates
> when the Codex backend changes.

## Start

1. Install the Codex CLI and run `codex login`. Confirm that
   `~/.codex/auth.json` exists. Never commit this file.
2. From the repository root, start waoowaoo with the bridge:

   ```bash
   docker compose -f docker-compose.yml -f docker-compose.codex.yml up -d --build
   ```

   If the Codex config directory is not `~/.codex`, set
   `WAOOWAOO_CODEX_CONFIG_DIR` to its absolute path before starting.

3. In **Settings > API Configuration**, add an **OpenAI Compatible** provider:

   - Name: `Codex OAuth`
   - Base URL: `http://codex-bridge:18080/v1`
   - API key: `local-codex-oauth` (a non-secret placeholder)
   - API mode: OpenAI official

4. Add these models:

   - Text: `gpt-5.6-sol`, Chat Completions protocol
   - Image: `gpt-5.5`

   For the image compatibility template, use `POST /images/generations` with:

   ```json
   {
     "model": "{{model}}",
     "prompt": "{{prompt}}"
   }
   ```

   Read the generated image from `$.data[0].url`.

The mounted Codex directory is writable so refreshed OAuth credentials can be
saved. Only run this locally on a machine and Docker environment you trust.

## Verify

```bash
docker compose -f docker-compose.yml -f docker-compose.codex.yml ps
docker compose -f docker-compose.yml -f docker-compose.codex.yml exec codex-bridge \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:18080/health').read().decode())"
```
