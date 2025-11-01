# Flare Worker

Cloudflare Worker that receives Python code from the Flare CLI, executes it in isolated Cloudflare Sandboxes, and returns results. Handles serialization and can run functions in parallel across multiple containers.

## Prerequisites

- Node.js 18+ and npm
- Docker running ([Docker Desktop](https://docs.docker.com/desktop/) recommended)
- Cloudflare account with Workers enabled

## Deploy

```bash
npm install
npx wrangler deploy
```

Generate an API key and configure the Flare CLI:

```bash
flare config init
```

Then set the generated key as a secret in your worker:

```bash
echo 'sk_your_generated_key' | npx wrangler secret put API_KEY
```

**Note:** First deployment takes 2-3 minutes while the container image builds.

## Local Development

```bash
cp .env.example .env
npm install
npm run dev
```

Server runs at `http://localhost:8787`.

Configure the Flare CLI to use the local worker:

```bash
flare config init  # Use http://localhost:8787 as the worker URL
```

## Configuration

Edit `wrangler.jsonc` to adjust resources:

```jsonc
"containers": [{
  "instance_type": "standard-1",  // Options: lite, basic, standard-1/2/3/4
  "max_instances": 10              // Max concurrent sandboxes
}]
```

See [Cloudflare Container Limits](https://developers.cloudflare.com/containers/platform-details/limits/) for details.
