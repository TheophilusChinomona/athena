# 📱 Meta Ecosystem + Social Media Integration — Deep Research
**Compiled: April 15, 2026**

---

## PART 1: META FOR DEVELOPERS

### Architecture
Everything runs through the **Graph API** (`graph.facebook.com/v25.0/...`):
- **Nodes**: Individual objects (Users, Pages, WhatsApp Accounts, etc.)
- **Edges**: Connections between nodes
- **HTTP-based**: Standard GET/POST/DELETE
- **Auth**: Access tokens (User, Page, System User, App tokens)

### Key APIs

| API | Purpose |
|-----|---------|
| **Graph API** | Core data API for all Meta platforms |
| **WhatsApp Cloud API** | Send/receive WhatsApp messages |
| **Marketing Messages API** | Optimized bulk marketing via WhatsApp |
| **Business Management API** | Programmatic WABA management |
| **WhatsApp Calling API** | Voice calls within WhatsApp |
| **Groups API** | WhatsApp group management |
| **Catalogs API** | Product catalog management |
| **Instagram Graph API** | Publish content, manage comments, get insights |
| **Instagram Messaging API** | DM management for business accounts |

### App Review Process
- Register app at `developers.facebook.com`
- Request permissions (`instagram_basic`, `whatsapp_business_messaging`, etc.)
- Submit for App Review with screencasts + use case descriptions
- Business Verification required for advanced features
- Review can take days to weeks

---

## PART 2: WHATSAPP BUSINESS API

### Cloud API Is Now The Only Option
**On-Premises API fully sunset October 2025.** Cloud API only.

**Why Cloud won:**
- 90%+ cost reduction vs On-Prem
- Up to 1,000 messages/second (4x On-Prem)
- 99.9% uptime, <5s p99 latency
- SOC2, SOC3, ISO 27001 compliant

### Message Types (18+)
Text, Image, Video, Audio, Document, Sticker, Location, Contacts, Template, Interactive Lists, Reply Buttons, CTA URL Buttons, Media Carousel, Flows, Reactions, Order, Catalog, Address

### Templates
Must be categorized:
- **Marketing** — always charged
- **Utility** — free within Customer Service Window (CSW)
- **Authentication** — OTP/verification

Max 100 template creations/hour/WABA. Quality rating affects messaging limits.

### Customer Service Window (CSW)
- **24-hour window** after user's last message
- Free-form messages only work within CSW
- Template messages work outside CSW (but cost money for marketing)
- 72-hour free entry point for Click-to-WhatsApp ads

### Pricing (Changed July 2025)
Moved from conversation-based to **per-message pricing**:
- Non-template messages: **free** within CSW
- Utility templates: **free** within CSW
- Marketing templates: **always charged**
- Rates vary by country (check Meta's rate card)

### Rate Limits
- Up to 1,000 msg/sec throughput
- Messaging tiers: 250 → 1K → 10K → 100K → unlimited unique users/24hrs
- Tier based on quality rating + business verification status

### AI Chatbot Integration Pattern
```
User sends WhatsApp msg
    → Meta webhook (your server)
    → Extract message text
    → Send to LLM (OpenRouter/OpenAI)
    → Get response
    → POST to WhatsApp Cloud API
    → User receives reply
```

### Key Considerations for AI Bots
- **Typing indicators** — show "typing..." while LLM processes
- **CSW awareness** — use templates outside 24-hour window
- **Quality maintenance** — keep quality rating high to unlock higher limits
- **Message deduplication** — webhooks can deliver duplicates
- **Business verification** — required for higher limits and Official Business Account

---

## PART 3: INSTAGRAM DEVELOPER APIs

### What AI Agents Can Do on Instagram

| Capability | Details |
|-----------|---------|
| **Publish Content** | Images, videos, carousels, Reels via Content Publishing API |
| **Read Media/Insights** | Engagement metrics (likes, comments, shares, impressions, reach) |
| **Comment Management** | Read, create, moderate comments on owned media |
| **Stories** | Publish stories + get story insights |
| **Webhooks** | Real-time notifications for comments, mentions, messaging |
| **DM Management** | Via Messenger Platform API (business accounts only) |
| **User Profile Data** | Follower counts, profile info |

### Account Requirements
- **Instagram Business or Creator account** (not personal)
- Must be linked to a **Facebook Page**
- Requires **Meta App** registered at developers.facebook.com
- OAuth with permissions: `instagram_basic`, `instagram_content_publish`, `instagram_manage_comments`, `instagram_manage_insights`

### Rate Limits
- **Content Publishing**: ~25 API-calls per user per 24 hours
- **Total API calls**: ~200 calls per user per hour
- Cannot post to other users' accounts
- No automated DMs to non-consenting users
- Video uploads: max 60 min for Reels via API

### Restrictions
- Must comply with Meta Platform Terms
- AI-generated content must be disclosed (Meta's policy)
- Aggressive anti-automation detection
- Unofficial APIs (instagrapi) = high ban risk

---

## PART 4: POSTIZ — Open Source Social Media Scheduler

### What It Is
An **open-source (AGPL-3.0)** social media scheduling tool — the open-source Buffer/Hootsuite alternative. 28.5K+ GitHub stars.

### Supported Platforms (30+)
Instagram, Facebook, X/Twitter, LinkedIn, TikTok, YouTube, Reddit, Threads, Pinterest, Discord, Slack, Bluesky, Mastodon, Dribbble, Telegram, Medium, Dev.to, Hashnode, WordPress, Google My Business, Twitch

### Key Features
- Schedule & cross-post across all platforms
- AI content assistant + DALL-E image generation
- Built-in Canva-like picture editor
- Analytics & engagement tracking
- Team collaboration
- Auto-actions (Plugs): auto-post, auto-like, auto-comment at milestones
- Repeated posts, RSS auto-posting
- Webhooks for real-time notifications
- Calendar views, posting sets

### Self-Hosted vs Hosted
- **Self-hosted**: Free, deployable anywhere (AWS, Railway, Coolify, etc.)
- **Hosted Cloud**: Paid plans at platform.postiz.com
- No functional difference between the two

### Pricing (Cloud)

| Plan | Price | Channels | Posts/mo |
|------|-------|----------|----------|
| Standard | $29/mo | 5 | 400 |
| Team | $39/mo | 10 | Unlimited |
| Pro | $49/mo | 30 | Unlimited |
| Ultimate | $99/mo | 100 | Unlimited |

All plans include: API, webhooks, AI copilot, custom integrations, smart agent

### Public API
- REST API at `api.postiz.com/public/v1/`
- Auth via API key (tokens start with `pos_`)
- Endpoints: integrations, posts (CRUD), analytics, notifications, uploads
- **Rate limit: 30 requests/hour**
- Platform-specific schemas (e.g., Instagram needs `post_type`)
- NodeJS SDK: `@postiz/node`
- n8n custom node: `n8n-nodes-postiz`

### 🤖 AI Agent CLI (`postiz-agent`)
**This is huge for your stack:**
- Install: `npm install -g postiz` or `npx skills add gitroomhq/postiz-agent`
- Full CLI for AI agents to: list integrations, create posts with media, trigger platform-specific tools
- OAuth2 device flow auth
- **Designed for integration with OpenClaw and other AI agent frameworks**

### Tech Stack
NextJS + NestJS + Prisma + Temporal (workflow orchestration for scheduling)

---

## PART 5: INTEGRATION PATTERNS

### Pattern A: AI Agent → Postiz → Multi-Platform
```
AI Agent generates content
    → Postiz API/CLI
    → Postiz formats for each platform
    → Publishes to Instagram + X + LinkedIn simultaneously
```

### Pattern B: WhatsApp Customer Service Bot
```
User WhatsApp msg → Webhook → FastAPI → Redis queue
    → LLM worker (OpenRouter) → Response → Cloud API
```

### Pattern C: Instagram Lead Engagement
```
Instagram comment webhook → AI classifies intent
    → High intent: DM via Instagram Messaging API
    → Low intent: Like/comment response
```

### Pattern D: Full Multi-Channel Agent
```
OpenClaw (channel gateway)
    ↓
Your AI stack (Agents SDK + Mem0 + OpenRouter)
    ↓
Postiz (social publishing) + WhatsApp Cloud API (messaging)
    ↓
Instagram + X + LinkedIn + WhatsApp + 20 more channels
```

---

## PART 6: OPEN-SOURCE TOOLS ECOSYSTEM

### Messaging Platforms
| Tool | Purpose |
|------|---------|
| **Chatwoot** | Customer engagement platform, WhatsApp+IG+Telegram, AI backend |
| **Typebot** | Beautiful chatbot builder, WhatsApp integration, self-hostable |
| **Botpress** | Visual flow builder, multi-channel, production-ready |
| **Evolution API** | Multi-tenant WhatsApp API (Baileys-based), popular in LATAM |
| **Baileys** | Reverse-engineered WhatsApp Web library (Node.js) |

### Social Media Automation
| Tool | Purpose |
|------|---------|
| **Postiz** | Scheduling + AI content generation (30+ platforms) |
| **n8n** | Workflow automation with social media + AI nodes |
| **Activepieces** | Open-source Zapier alternative |

### Content Generation
| Tool | Purpose |
|------|---------|
| **Flowise** | Drag-and-drop LLM flow builder |
| **LangFlow** | Visual LangChain builder |
| **Dify** | LLM app development platform |

---

## STRATEGIC RECOMMENDATIONS

### What to Build With

**WhatsApp AI Bot (fastest ROI):**
- Stack: WhatsApp Cloud API + Typebot + OpenAI Agents SDK + Mem0
- Effort: 1-2 weeks for MVP
- Cost: $0-200/month at small scale
- Revenue: Charge per conversation or per active user

**Social Media Automation:**
- Stack: Postiz (self-hosted) + OpenAI Agents SDK + Mem0 (brand memory)
- Effort: 1 week
- Cost: $0-100/month
- Revenue: Charge per scheduled post or per platform

**Full Multi-Channel Agent:**
- Stack: OpenClaw + Your stack + Postiz + WhatsApp Cloud API
- Effort: 2-4 weeks for production
- Revenue: Premium tier, per-channel pricing

### What NOT to Do
- ❌ Don't build your own WhatsApp integration from scratch (use Cloud API)
- ❌ Don't use unofficial Instagram APIs (ban risk)
- ❌ Don't build another scheduling tool (Postiz exists and has agent CLI)
- ❌ Don't ignore Meta's App Review process (start early, takes weeks)

### The Big Opportunity
**Postiz + Your AI Stack = AI-powered social media management for businesses**

The `postiz-agent` CLI is literally designed for OpenClaw/agent integration. Self-hosted Postiz + Mem0 (brand voice memory) + OpenAI Agents SDK (content generation) + OpenRouter (model routing) = a complete AI social media platform.

---

## Files Reference
- `/workspace/meta-developers-whatsapp-api-research.md` — Full WhatsApp API research (620 lines)
- `/workspace/research/ai-agent-social-media-integration.md` — Integration patterns
- This file covers everything consolidated
