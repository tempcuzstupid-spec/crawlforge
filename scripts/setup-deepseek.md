# DeepSeek API Setup

1. Go to https://platform.deepseek.com and sign up
2. Top up at least $1 (they charge per token, ~$0.14 per 1M output tokens)
3. Go to **API Keys** → **Create new secret key**
4. Copy the key (starts with `sk-...`)
5. Paste into `.env` as `DEEPSEEK_API_KEY`
6. On Render, set the same as `DEEPSEEK_API_KEY` environment variable

## Pricing
- Input: $0.14 per 1M tokens (~700k words)
- Output: $0.28 per 1M tokens
- Typical crawl/agent task: ~5k-50k tokens = **$0.001-0.014 per task**

So ~100-1000 tasks per dollar. For personal use you'll pay cents per month.