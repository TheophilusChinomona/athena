# Building AI Agents: OpenRouter SDK + OpenAI Agents SDK Deep Study

## Overview
Two complementary approaches to building AI agents:
1. **OpenRouter SDK** (`@openrouter/sdk`, `@openrouter/agent`, `openrouter` Python) — Universal model access layer (300+ models)
2. **OpenAI Agents SDK** (`openai-agents`) — Full agent orchestration framework with handoffs, guardrails, tracing

---

## PART 1: OpenRouter SDK

### Architecture
- **TypeScript SDK** (`@openrouter/sdk`): Auto-generated from OpenAPI specs, type-safe, always up-to-date
- **Python SDK** (`openrouter`): Pydantic-validated, type-hinted, async support
- **Agent Package** (`@openrouter/agent`): Standalone agent toolkit (callModel, tools, stop conditions)

### Core TypeScript Usage

```typescript
import OpenRouter from '@openrouter/sdk';

const client = new OpenRouter({
  apiKey: process.env.OPENROUTER_API_KEY
});

// Basic chat
const response = await client.chat.send({
  model: "minimax/minimax-m2",
  messages: [{ role: "user", content: "Hello!" }]
});

// Streaming
const stream = await client.chat.send({
  model: "minimax/minimax-m2",
  messages: [{ role: "user", content: "Write a story" }],
  stream: true
});
for await (const chunk of stream) {
  const content = chunk.choices[0]?.delta?.content;
}
```

### Agent Package (`@openrouter/agent`) — The Agentic Part

```typescript
import { OpenRouter, callModel } from '@openrouter/agent';
import { tool } from '@openrouter/agent/tool';
import { stepCountIs, hasToolCall } from '@openrouter/agent/stop-conditions';

const client = new OpenRouter({ apiKey: process.env.OPENROUTER_API_KEY });

// callModel: The core agentic API
const result = client.callModel({
  model: 'openai/gpt-4o',
  input: 'Hello',
  tools: [myTool],
  stopWhen: stepCountIs(5)
});
const text = await result.getText();
```

### Key Agent Concepts (OpenRouter)
- **callModel**: Core function for agentic model calls with tools, stop conditions
- **tool**: Define tools with typed parameters
- **Stop conditions**: `stepCountIs(n)`, `hasToolCall(name)`, `maxCost(amount)`
- **Conversation state**: `createInitialState()`, `updateState()`
- **Message format converters**: `fromClaudeMessages()`, `fromChatMessages()`

### OpenRouter Agentic Usage (Skill for AI Assistants)
- Install via: `npx add-skill OpenRouterTeam/agent-skills`
- Works with: Claude Code, Cursor, GitHub Copilot, Codex, OpenCode, Amp, Roo Code
- Teaches AI assistants: SDK installation, callModel API, chat completions, embeddings, error handling, streaming, tool use

---

## PART 2: OpenAI Agents SDK

### Installation
```bash
pip install openai-agents
# Voice support: pip install 'openai-agents[voice]'
# Redis sessions: pip install 'openai-agents[redis]'
```

### Core Concepts

#### 1. Agents
An Agent = LLM + instructions + tools + guardrails + handoffs + output_type

```python
from agents import Agent, Runner

agent = Agent(
    name="History Tutor",
    instructions="You answer history questions clearly and concisely.",
    model="gpt-4o",  # optional, defaults to OpenAI
)

result = await Runner.run(agent, "What caused WW1?")
print(result.final_output)
```

**Agent Properties:**
- `name` (required)
- `instructions` (required) — system prompt
- `model` — model name or model object
- `tools` — list of function tools
- `handoffs` — list of agents to delegate to
- `output_type` — Pydantic model for structured output
- `guardrails` — input/output validation
- `model_settings` — temperature, top_p, etc.

**Agent Design Patterns:**
- **Manager**: Agent uses other agents as tools (orchestrator pattern)
- **Handoffs**: Agent delegates entire conversation to specialist agent
- **Routing**: Triage agent routes to appropriate specialist via handoffs
- **Deterministic flow**: Chain agents sequentially with explicit control flow
- **Parallelization**: Run multiple agents concurrently, combine results

#### 2. Tools
Five categories:
1. **Function tools** — `@function_tool` decorator wraps Python functions
2. **Hosted tools** — OpenAI-managed (web search, file search, code interpreter)
3. **Agents as tools** — `agent.as_tool()` exposes agent without handoff
4. **ComputerTool / ShellTool** — local/hosted container execution
5. **Codex tool** (experimental) — workspace-scoped Codex tasks

```python
from agents import function_tool
from typing import Annotated

@function_tool
def get_weather(city: Annotated[str, "City name"]) -> str:
    """Get current weather for a city."""
    return f"Weather in {city}: Sunny, 20°C"

agent = Agent(name="Assistant", tools=[get_weather])

# Agent as tool
spanish_agent = Agent(name="Spanish", instructions="Translate to Spanish")
orchestrator = Agent(
    name="Orchestrator",
    tools=[spanish_agent.as_tool(
        tool_name="translate_spanish",
        tool_description="Translate to Spanish"
    )]
)
```

#### 3. Handoffs
Agent delegates to another specialist agent. The conversation transfers completely.

```python
french_agent = Agent(name="French", instructions="You only speak French")
spanish_agent = Agent(name="Spanish", instructions="You only speak Spanish")

triage_agent = Agent(
    name="Triage",
    instructions="Route to the appropriate language agent.",
    handoffs=[french_agent, spanish_agent],
)
# Runner handles the handoff automatically
result = await Runner.run(triage_agent, "Bonjour!")
```

Customize handoffs with `handoff()`:
```python
from agents import handoff

agent = Agent(
    handoffs=[
        handoff(spanish_agent, 
            tool_name_override="escalate_to_spanish",
            on_handoff=my_callback,
            input_type=SpanishContext
        )
    ]
)
```

#### 4. Running Agents (Runner)
Three modes:
```python
# Synchronous
result = Runner.run_sync(agent, "Hello")

# Async
result = await Runner.run(agent, "Hello")

# Streaming
result = Runner.run_streamed(agent, "Hello")
async for event in result.stream_events():
    if event.type == "run_item_stream_event":
        if event.item.type == "message_output_item":
            print(ItemHelpers.text_message_output(event.item))
```

**RunConfig** — global settings for a run:
```python
from agents import RunConfig

config = RunConfig(
    model="gpt-4o",
    model_provider=my_custom_provider,
    tracing_disabled=True,
    handoff_input_filter=my_filter,
)
result = await Runner.run(agent, "Hello", run_config=config)
```

**Conversation Management:**
```python
# Multi-turn: feed previous result back
result1 = await Runner.run(agent, "Hello")
result2 = await Runner.run(agent, result1.to_input_list())

# Or use Sessions for automatic history
from agents import SQLiteSession
session = SQLiteSession("user_123")
result1 = await Runner.run(agent, "Hello", session=session)
result2 = await Runner.run(agent, "Follow up", session=session)
```

#### 5. Models — Provider Agnostic

**OpenAI (default):**
```python
# Just set OPENAI_API_KEY
agent = Agent(name="A", model="gpt-4o")
```

**Non-OpenAI via custom ModelProvider:**
```python
from openai import AsyncOpenAI
from agents import Model, ModelProvider, OpenAIChatCompletionsModel, RunConfig

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-..."
)

class OpenRouterProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model=model_name or "anthropic/claude-sonnet-4",
            openai_client=client
        )

config = RunConfig(model_provider=OpenRouterProvider())
result = await Runner.run(agent, "Hello", run_config=config)
```

**Via LiteLLM:**
```python
from agents.extensions.models.litellm_model import LitellmModel
agent = Agent(name="A", model=LitellmModel(model="anthropic/claude-sonnet-4"))
```

**Via Any-LLM:**
- Third-party adapter for any model provider

#### 6. Guardrails
Input/Output validation that runs in parallel with agent execution.

```python
from agents import GuardrailFunctionOutput, input_guardrail, Agent
from pydantic import BaseModel

class ContentCheck(BaseModel):
    is_safe: bool
    reason: str

@input_guardrail
async def content_guardrail(agent, input, context):
    checker = Agent(name="Checker", output_type=ContentCheck)
    result = await Runner.run(checker, input)
    return GuardrailFunctionOutput(
        output_info=result.final_output,
        tripwire_triggered=not result.final_output.is_safe
    )

agent = Agent(name="A", input_guardrails=[content_guardrail])
```

**Types:** input_guardrail, output_guardrail, tool_guardrails

#### 7. Streaming
```python
result = Runner.run_streamed(agent, input="Hello")
async for event in result.stream_events():
    if event.type == "raw_response_event":
        pass  # Raw LLM tokens
    elif event.type == "agent_updated_stream_event":
        print(f"Agent: {event.new_agent.name}")
    elif event.type == "run_item_stream_event":
        if event.item.type == "tool_call_item":
            print(f"Tool called: {event.item.raw_item.name}")
        elif event.item.type == "message_output_item":
            print(ItemHelpers.text_message_output(event.item))
```

#### 8. Tracing
Built-in tracing for debugging and observability:
```python
from agents import trace

with trace("My workflow"):
    result1 = await Runner.run(agent1, input)
    result2 = await Runner.run(agent2, result1.to_input_list())
```

#### 9. Sessions (Conversation Memory)
```python
from agents import SQLiteSession

session = SQLiteSession("user_123", "conversations.db")
result = await Runner.run(agent, "Hello", session=session)

# Also: SQLAlchemySession, AsyncSQLiteSession, RedisSession, EncryptedSession
# OpenAI Conversations API sessions for server-managed memory
```

#### 10. Context Management
Share runtime state across tools and agents:
```python
from dataclasses import dataclass
from agents import RunContextWrapper

@dataclass
class AppContext:
    user_id: str
    db: Database

@function_tool
async def get_user(wrapper: RunContextWrapper[AppContext]) -> str:
    return await wrapper.context.db.get_user(wrapper.context.user_id)
```

#### 11. Human-in-the-Loop
Tool approval gates:
```python
from agents import Tool

agent = Agent(
    tools=[
        Tool(name="delete_db", on_approval="require_approval")
    ]
)
```

#### 12. MCP (Model Context Protocol)
Connect to MCP servers for external tool integration:
```python
from agents.mcp import MCPServerStdio

mcp_server = MCPServerStdio(
    command="npx",
    args=["-y", "@modelcontextprotocol/server-filesystem", "/path"]
)
agent = Agent(name="A", mcp_servers=[mcp_server])
```

---

## PART 3: Combining Both (OpenRouter + OpenAI Agents SDK)

### The Power Combo
Use **OpenAI Agents SDK** for orchestration + **OpenRouter** as the model provider:
- Access 300+ models through OpenRouter
- Full agent framework: handoffs, guardrails, tracing, streaming
- Cost optimization: route to cheapest capable model per task

```python
from openai import AsyncOpenAI
from agents import (
    Agent, Runner, ModelProvider, Model,
    OpenAIChatCompletionsModel, RunConfig,
    function_tool, set_tracing_disabled
)

# OpenRouter as model backend
client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="sk-or-..."
)

class OpenRouterProvider(ModelProvider):
    def get_model(self, model_name: str | None) -> Model:
        return OpenAIChatCompletionsModel(
            model=model_name or "anthropic/claude-sonnet-4",
            openai_client=client
        )

set_tracing_disabled(True)  # Can't trace to OpenAI with OpenRouter key

@function_tool
def search_web(query: str) -> str:
    """Search the web for information."""
    return f"Results for: {query}"

# Create agents with different models for different tasks
researcher = Agent(
    name="Researcher",
    instructions="Research topics thoroughly using search tools.",
    model="google/gemini-2.5-flash",  # cheap & fast for research
    tools=[search_web],
)

writer = Agent(
    name="Writer",
    instructions="Write polished content based on research.",
    model="anthropic/claude-sonnet-4",  # best for writing
)

triage = Agent(
    name="Triage",
    instructions="Route requests to the right specialist.",
    handoffs=[researcher, writer],
)

config = RunConfig(model_provider=OpenRouterProvider())

async def main():
    result = await Runner.run(triage, "Write a blog post about AI agents", run_config=config)
    print(result.final_output)
```

---

## Key Architectural Differences

| Feature | OpenRouter SDK | OpenAI Agents SDK |
|---------|---------------|-------------------|
| **Primary purpose** | Model access (300+) | Agent orchestration |
| **Language** | TypeScript/Python | Python (+ JS/TS version) |
| **Agent abstraction** | callModel (low-level) | Agent class (high-level) |
| **Multi-agent** | Manual coordination | Built-in handoffs/manager |
| **Streaming** | Token-level streaming | Full event stream |
| **Tools** | Manual tool definition | @function_tool decorator |
| **Guardrails** | None built-in | Input/output/tool guardrails |
| **Tracing** | None built-in | Full tracing system |
| **Sessions** | Manual state | SQLite/Redis/SQLAlchemy |
| **Model flexibility** | 300+ via API | OpenAI default, extensible |

---

## Agent Design Patterns (from examples)

1. **Agents as Tools** — Orchestrator calls specialist agents as tools
2. **Routing/Handoffs** — Triage agent routes to specialists
3. **Deterministic Flow** — Sequential agent chains with explicit control
4. **Parallelization** — Concurrent agent runs, merge results
5. **LLM-as-Judge** — One agent generates, another evaluates
6. **Input/Output Guardrails** — Safety checks in parallel
7. **Human-in-the-Loop** — Approval gates for sensitive tools
8. **Dynamic Instructions** — Runtime-generated system prompts
9. **Lifecycle Hooks** — Callbacks on agent start/end

---

## Files Reference
- OpenAI Agents SDK: `github.com/openai/openai-agents-python`
- OpenAI Agents Docs: `openai.github.io/openai-agents-python/`
- OpenRouter TypeScript: `@openrouter/sdk`
- OpenRouter Agent: `@openrouter/agent`
- OpenRouter Python: `openrouter` (PyPI)
- OpenRouter Docs: `openrouter.ai/docs/sdks/`
