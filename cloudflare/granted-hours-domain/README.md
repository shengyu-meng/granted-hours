# Granted Hours custom-domain Worker

This Worker maps `granted-hours.hyperint.net` to the production Cloudflare
Pages project at `granted-hours.pages.dev`.

It intentionally streams responses without buffering, rewrites Pages-origin
redirects back to the custom hostname, and strips private request headers before
forwarding. Future Pages deployments are visible on the custom hostname without
redeploying this Worker.

Deploy from this directory:

```sh
npx wrangler deploy
```
