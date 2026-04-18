# AI Agent Memory Backends: Mem0, Graphiti, Honcho — Deep Study

## The Memory Problem in AI Agents
LLMs are stateless. Memory backends give agents persistent context about users, conversations, and evolving facts.

---

## 1. MEM0 — The Memory Layer for Personalized AI

**Repo:** `github.com/mem0ai/mem0` | **Stars:** 25k+ | **License:** Apache 2.0 | **YC S24**

### What It Is
An intelligent memory layer that enables personalized AI interactions. Remembers user preferences, adapts to individual needs, and continuously learns over time.

### Key Stats (from LOCOMO benchmark)
- **+26% Accuracy** over OpenAI Memory
- **91% Faster** than full-context approaches
- **90% Lower Token Usage** than full-context

### Architecture
```
User/Agent/Session Memory → LLM Extraction → Vector Store → Search + Reranking
                                     ↓
                              Graph Memory (optional)
                                     ↓
                           Entity Relationships
```

### Core Concepts

**Three Memory Types:**
1. **User Memory** — persists across all conversations for a user
2. **Session Memory** — scoped to a single conversation
3. **Agent Memory** — agent's own learned state

**Operations:**
- `memory.add(messages, user_id=...)` — extract and store memories from conversation
- `memory.search(query, user_id=...)` — retrieve relevant memories
- `memory.update(memory_id, data)` — update existing memories
- `memory.delete(memory_id)` — remove memories
- `memory.get_all(user_id=...)` — list all memories for a user

### Quick Start
```python
from mem0 import Memory

memory = Memory()  # defaults to OpenAI for LLM + embeddings

# Add memories from conversation
messages = [
    {"role": "user", "content": "I prefer dark mode and vim keybindings"},
    {"role": "assistant", "content": "Got it, I'll remember that!"}
]
memory.add(messages, user_id="alice")

# Search memories
results = memory.search("What does Alice prefer?", user_id="alice")
# → [{"memory": "Prefers dark mode and vim keybindings", ...}]
```

### Deployment Options
- **Hosted Platform** (app.mem0.ai) — fully managed, SOC 2, enterprise features
- **Self-Hosted** — `pip install mem0ai`, requires vector store + LLM
- **CLI** — `npm install -g @mem0/cli` for terminal management

### Platform Features (Hosted)
- **Graph Memory** — relationship-aware recall across entities
- **Async Client** — non-blocking add/search for agents
- **Rerankers** — boost retrieval quality
- **Metadata Filters** — filter by custom categories
- **Webhooks** — event-driven integrations
- **Multimodal Support** — images, documents
- **MCP Integration** — universal AI client connection

### Integrations
LangChain, CrewAI, Vercel AI SDK, Chroma extension, browser extension (ChatGPT/Perplexity/Claude)

### Best For
- Chatbot personalization (remember user preferences)
- Customer support (recall past tickets/history)
- Healthcare (track patient history)
- Productivity apps (adaptive workflows)
- When you want **simple, vector-based memory** with optional graph

---

## 2. GRAPHITI — Temporal Context Graphs for AI Agents

**Repo:** `github.com/getzep/graphiti` | **By:** Zep | **License:** Apache 2.0

### What It Is
A framework for building and querying **temporal context graphs** for AI agents. Unlike static knowledge graphs, tracks how facts change over time with full provenance.

### Key Innovation: Bi-Temporal Tracking
Every fact has:
- **Valid From** — when it became true
- **Valid Until** — when it was superseded
- **Provenance** — traces back to the episode (raw data) that produced it

### Architecture
```
Episodes (raw data)
    ↓ LLM extraction
Entities (nodes) + Relationships (edges)
    ↓ Temporal validity windows
Context Graph (Neo4j / FalkorDB / Kuzu / Neptune)
    ↓ Hybrid retrieval
Semantic + BM25 + Graph Traversal
```

### Context Graph Components
| Component | Stores |
|-----------|--------|
| **Entities** (nodes) | People, products, concepts — with evolving summaries |
| **Facts/Relationships** (edges) | Entity → Relationship → Entity triplets with temporal validity |
| **Episodes** (provenance) | Raw data as ingested — ground truth stream |
| **Custom Types** (ontology) | Developer-defined entity/edge types via Pydantic models |

### Quick Start
```python
from graphiti_core import Graphiti
from graphiti_core.nodes import EpisodeType

# Connect to Neo4j
graphiti = Graphiti(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
await graphiti.build_indices_and_constraints()

# Add episodes (raw data → graph)
await graphiti.add_episode(
    name="user_preference",
    episode_body="Kendra loves Adidas shoes as of March 2026",
    source=EpisodeType.text,
    source_description="user message",
    reference_time=datetime(2026, 3, 15)
)

# Search with hybrid retrieval
results = await graphiti.search("What shoes does Kendra like?")
# → Returns edges with facts, validity windows, source nodes

# Graph-aware reranking
results = await graphiti.search(
    "shoes",
    center_node_uuid=some_node_uuid  # rerank by graph distance
)
```

### Key Features
- **Temporal Fact Management** — old facts invalidated (not deleted), query any time period
- **Incremental Updates** — new data integrates immediately, no batch recomputation
- **Hybrid Retrieval** — semantic embeddings + BM25 keyword + graph traversal
- **Prescribed & Learned Ontology** — define types upfront via Pydantic OR let structure emerge
- **Contradiction Handling** — automatic fact invalidation with history preserved
- **Sub-second Queries** — optimized for large datasets

### Graph Backends
- **Neo4j** (default, 5.26+)
- **FalkorDB** (Redis-based graph, Docker-friendly)
- **Kuzu** (embedded graph DB)
- **Amazon Neptune** (+ OpenSearch for full-text)

### LLM Providers
OpenAI (default), Anthropic, Google Gemini, Groq. Works best with models supporting **Structured Output**.

### MCP Server
Has an MCP server for Claude, Cursor, and other MCP clients to get graph-based memory with temporal awareness.

### Graphiti vs GraphRAG
| Aspect | GraphRAG | Graphiti |
|--------|----------|----------|
| Data handling | Batch | Continuous, incremental |
| Retrieval | Sequential LLM summarization | Hybrid semantic + keyword + graph |
| Temporal | Basic timestamps | Bi-temporal with automatic invalidation |
| Query latency | Seconds | Sub-second |
| Adaptability | Low | High |

### Best For
- **Dynamic, evolving data** (user preferences change, relationships evolve)
- **Fact tracking** (what was true then vs now)
- **Complex entity relationships** (social graphs, organizational knowledge)
- **When you need provenance** (trace any fact back to source data)
- **Production agent memory** (Zep built on this for enterprise)

---

## 3. HONCHO — Entity-Centric Memory with Psychological Reasoning

**Repo:** `github.com/plastic-labs/honcho` | **Stars:** 2.4k | **Version:** 3.0.6

### What It Is
An open-source memory library with a managed service for building **stateful agents**. Uses an entity-centric "peer" model where both users AND agents are first-class entities with evolving representations.

### Key Differentiator: Psychological Reasoning
Honcho doesn't just store facts — it **reasons about peer psychology** to build comprehensive representations of users and agents.

### Architecture
```
Workspaces
├── Peers (users + agents as equals)
│   ├── Sessions (conversations)
│   └── Collections (stored conclusions)
│
└── Sessions
    ├── Peers (many-to-many)
    └── Messages
         ↓
    Background Processing
    ├── Representation updates (peer modeling)
    └── Session summaries
         ↓
    Derived Conclusions
```

### Core Concepts

**Peer Paradigm:**
Both users and agents are "peers" — unified entity model enabling:
- Multi-participant sessions (humans + AI agents mixed)
- Configurable observation (which peers observe which)
- Flexible identity management

**Primitives:**
- **Workspace** — top-level container (your app)
- **Peer** — any entity (user, agent, group, idea)
- **Session** — conversation thread
- **Message** — individual utterance
- **Collection** — stored documents/conclusions

### Quick Start
```python
from honcho import Honcho

honcho = Honcho(workspace_id="my-app")

# Create peers
alice = honcho.peer("alice")
tutor = honcho.peer("tutor")

# Create session with messages
session = honcho.session("session-1")
session.add_messages([
    alice.message("Help me with math homework"),
    tutor.message("Sure, send me your first problem!"),
])

# Ask questions about users (Chat API)
response = alice.chat("What learning styles does this user respond to best?")

# Get session context for LLM (auto-summarized, token-limited)
context = session.context(summary=True, tokens=10_000)
openai_messages = context.to_openai(assistant=tutor)

# Search across peer history
results = alice.search("Math Homework")

# Get session-scoped peer representation
alice_in_session = session.representation(alice)
```

### Reasoning Pipeline
1. Messages arrive via API
2. **Background Tasks** enqueued:
   - `representation` — update peer psychological model
   - `summary` — create session summaries
3. Session-based queue ensures proper ordering
4. Results stored in reserved Collections

### Retrieval Methods
1. **Chat API** — natural language queries about peers ("What motivates this user?")
2. **Context** — auto-summarized conversation state for token management
3. **Search** — hybrid search at workspace/session/peer level
4. **Representation** — session-scoped model of a peer

### Deployment
- **Managed** (app.honcho.dev) — $100 free credits, dedicated instance
- **Self-Hosted** — FastAPI server, Postgres + pgvector, Python 3.10+

### LLM Providers
Configurable per function:
- Gemini (default for deriver, summary, dialectic low)
- Anthropic (default for dialectic medium/high/max, dream)
- OpenAI (default for embeddings)
- Groq (optional)

### Best For
- **Personalized agents** that need deep user understanding
- **Multi-agent systems** where agents observe and learn from each other
- **Educational/tutoring** apps (learning style detection)
- **Customer service** with psychological profiling
- **When "who is this user?" matters more than "what did they say?"**

---

## COMPARISON MATRIX

| Feature | Mem0 | Graphiti | Honcho |
|---------|------|----------|--------|
| **Primary model** | Vector + optional graph | Temporal knowledge graph | Entity-centric + reasoning |
| **Memory granularity** | Facts/preferences | Entities + relationships | Peer psychology |
| **Temporal tracking** | No | Yes (bi-temporal) | Yes (session-based) |
| **Graph backend** | Optional (platform) | Neo4j/FalkorDB/Kuzu/Neptune | Postgres + pgvector |
| **Reasoning** | LLM extraction | LLM extraction | Psychological reasoning pipeline |
| **Query method** | Semantic search | Hybrid (semantic + keyword + graph) | Chat API + search + context |
| **Setup complexity** | Low (pip install) | Medium (needs graph DB) | Medium (needs Postgres) |
| **Hosted option** | Yes (SOC 2) | Via Zep (enterprise) | Yes ($100 free) |
| **MCP support** | Yes | Yes | Unknown |
| **Multi-agent** | User/agent memory | Entity relationships | Peer paradigm (first-class) |
| **Token management** | No (raw search) | No (raw search) | Yes (context endpoint) |
| **Open source** | Yes (Apache 2.0) | Yes (Apache 2.0) | Yes |
| **Best for** | Simple personalization | Complex evolving knowledge | User psychology modeling |

---

## INTEGRATION WITH AI AGENT FRAMEWORKS

### With OpenAI Agents SDK
All three can be integrated as tools or context providers:

```python
# Mem0 as a tool
@function_tool
def recall_user_preferences(query: str, user_id: str) -> str:
    """Search user's stored preferences and memories."""
    results = memory.search(query, user_id=user_id)
    return "\n".join(r["memory"] for r in results["results"])

# Graphiti as context provider
@function_tool
def search_knowledge_graph(query: str) -> str:
    """Search the temporal knowledge graph for facts."""
    results = await graphiti.search(query)
    return "\n".join(r.fact for r in results)

# Honcho for personalization
@function_tool
def understand_user(question: str, user_id: str) -> str:
    """Ask questions about user psychology and preferences."""
    peer = honcho.peer(user_id)
    return peer.chat(question)
```

### With MCP-Anything
- **Mem0**: Has MCP server, can generate MCP tools from memory operations
- **Graphiti**: Has official MCP server for Claude/Cursor
- **Honcho**: Can be wrapped as MCP tools via OpenAPI spec

---

## WHICH TO USE WHEN

**Choose Mem0 if:**
- You want simple, drop-in memory for chatbots
- Vector search is enough (no complex relationships)
- You want managed infrastructure option
- Budget-conscious (free tier available)

**Choose Graphiti if:**
- Facts change over time and you need history
- Entity relationships matter (social graphs, org charts)
- You need provenance (trace facts to source)
- You already use Neo4j or are comfortable with graph DBs
- Sub-second query latency is critical

**Choose Honcho if:**
- You need deep user understanding (psychology, learning styles)
- Multi-agent systems with peer observation
- Token management for long conversations
- "Who is this user?" is as important as "what did they say?"

---

## Files Reference
- Mem0: `github.com/mem0ai/mem0` | `docs.mem0.ai`
- Graphiti: `github.com/getzep/graphiti` | Paper: `arxiv.org/abs/2501.13956`
- Honcho: `github.com/plastic-labs/honcho` | `docs.honcho.dev`
- Zep (Graphiti's managed version): `getzep.com`
