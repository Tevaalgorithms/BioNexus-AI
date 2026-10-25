# How a role is built: LangGraph and LangChain

The planner, step by step. The short version, and why these two libraries are used, is in the [README](../README.md#how-a-role-is-built-langgraph-and-langchain).

The roles are **not** LangChain agents. They are small classes of our own. LangGraph decides *when* a role runs, and LangChain is only the last step that talks to a model provider. The planner is the example below because it is short and uses a model. Every path in this section is under `services/api/bionexus/`.

```text
LangGraph node  ->  Dispatcher  ->  Planner.handle()  ->  Gateway  ->  LangChain chat model  ->  provider
 (when it runs)     (our router)     (what it does)      (our rules)    (the one LangChain use)
```

### Step 1: write its instructions

Instructions are a versioned, hashed file, not a string in the code. The run's configuration release pins the exact version, and a role cannot edit its own.

```json
// skills/coverage.plan/1.0.0/skill.json
{
  "skill_id": "coverage.plan",
  "owner": "planner",
  "instructions": "Review how much evidence was found for each gene and source. Propose a few extra searches that use only alternative names ... Never state or imply what the evidence says.",
  "abstain_when": "Coverage already looks complete, or no useful alternative name is known."
}
```

### Step 2: write the role

A role subclasses `Agent`, names itself, and implements `handle()`. It asks a model through `ask_model()` and treats the reply as untrusted text.

```python
# agents/planner.py (trimmed)
class PlannerAgent(Agent):
    name: ClassVar[AgentName] = AgentName.PLANNER
    skill_id: ClassVar[str] = "coverage.plan"

    def handle(self, message: AgentMessage, state: RunState) -> AgentResult:
        outgoing = [request_message(self.name, message, state, p) for p in self._plan(state)]
        return AgentResult(outgoing=outgoing, abstained=not outgoing)

    def _plan(self, state: RunState) -> list[PlannedRequest]:
        try:
            reply = self.ask_model(state, self._prompt(state))   # -> the gateway
        except ModelUnavailable:      # optional step: no model, no extra searches
            return []
        limit = min(AO_MAX_PLANNER_REQUESTS, exchanges_available(state, MESSAGE_RESERVE))
        return self._validated(parse_json_object(reply), limit)   # a bad reply is no answer
```

The role cannot touch evidence. Its only output is a list of messages, and each one is checked by the router.

### Step 3: the model call (this is where LangChain is used)

`ask_model()` goes to our gateway, which applies the rules that matter to the product: the approved-model list, the release's model for this role, the response cache, the budget, the fallback model and the call ledger. Only then does it reach LangChain, behind our own `ModelClient` port.

```python
# agents/base.py
def ask_model(self, state, task_summary, skill_id=None) -> str:
    prompt = f"{self.instructions(state, skill_id)}\n{task_summary}"
    return self.deps.gateway.complete(state, self.name, prompt)
```

```python
# llm/langchain_client.py (trimmed): the only place LangChain's chat models are used
def anthropic_model(model_id, max_tokens, temperature, api_key):
    return ChatAnthropic(model=model_id, max_tokens=max_tokens, api_key=api_key,
                         timeout=TIMEOUT_SECONDS, max_retries=TRANSPORT_RETRIES)

class LangChainClient:
    def generate(self, model_id, prompt, max_output_tokens, temperature=None, api_key_secret=None):
        api_key = resolve_secret(api_key_secret or self._default_secret)   # read at call time
        model = self._factory(model_id, max_output_tokens, temperature, api_key)
        reply = model.invoke([HumanMessage(content=prompt)])
        usage = reply.usage_metadata or {}
        return ModelResponse(message_text(reply), usage.get("input_tokens", 0), usage.get("output_tokens", 0))
```

`ChatOpenAI` is built the same way, so a role never knows which provider answered.

### Step 4: register the role

One line in the container makes the dispatcher able to deliver messages to it. The router's allowlist (`messaging/router.py`) says who may send it what.

```python
# container.py (trimmed)
handlers = {
    AgentName.GENETICS: GeneticsAgent(deps),
    AgentName.PLANNER: PlannerAgent(deps),
    AgentName.CRITIC: critic,
    AgentName.VERIFIER: VerifierAgent(deps),
    ...
}
```

### Step 5: give it a place in the LangGraph graph

The graph decides *when* the planner runs. Its node does one thing: the supervisor sends the planner a task, and the dispatcher delivers it, so the handoff is recorded like any other.

```python
# workflow/nodes.py
def coverage(self, state: RunState) -> None:
    self._dispatcher.run(state, [self._task(state, AgentName.PLANNER, {})])
```

```python
# workflow/graph.py, InvestigationGraph.build (trimmed)
graph = StateGraph(GraphState)                       # control data only: run_id, repair_round, approval
for name, work in self._work().items():              # scope, recall_memory, specialists, coverage, ...
    policy = SOURCE_RETRY if name == "specialists" else None
    graph.add_node(name, _step(self._nodes, name, work), retry_policy=policy)
graph.add_node("await_review", self._await_review)   # pauses for a scientist
for before, after in LINEAR_EDGES:                   # START -> scope -> ... -> coverage -> critique
    graph.add_edge(before, after)
graph.add_conditional_edges("critique", self._after_critique,   # the bounded repair loop:
                            {"critique": "critique", "retrieve": "retrieve"})   # back, or move on
return graph.compile(checkpointer=checkpointer)      # PostgreSQL in production
```

### Step 6: how a message reaches the role

The graph node never calls the planner. It hands a message to the **dispatcher**, which asks the **router** to check it, then calls the recipient's `handle()`. Whatever the role returns is merged into the run, a reply is recorded, and any messages the role sent are queued and delivered the same way.

```python
# workflow/dispatcher.py (trimmed)
def _drain(self, state, initial):
    pending = deque(initial)
    while pending:
        message = pending.popleft()
        if self._accept(state, message):                    # the router checked it
            pending.extend(self._deliver(state, message))   # the role's own messages join the queue

def _deliver(self, state, message):
    result = self._agents[message.recipient].handle(message, state)    # <- PlannerAgent.handle()
    with state.lock:
        self._merge(state, result)                                     # evidence, analyses, verifications
        self._router.accept(state, reply_to(message, result, MessageType.TASK_RESULT))
    return result.outgoing
```

```python
# messaging/router.py (trimmed)
def accept(self, state, message) -> bool:
    if self._is_duplicate(state, message):     # same idempotency key: a retry never repeats work
        return False
    self._check_limits(state, message)         # at most 3 handoffs deep, 60 messages per run
    self._check_route(state, message)          # allowlist, and replies only to what was asked
    state.messages.append(message)             # recorded with the run
    return True
```

### Step 7: run it, pause it, resume it

A run is one LangGraph *thread*, named by its run id. The graph pauses at `interrupt()` until a scientist approves, and a crashed run resumes from its last checkpoint instead of starting again.

```python
# workflow/graph.py and workflow/runner.py (trimmed)
def _await_review(gs):
    decision = interrupt({"run_id": gs["run_id"], "waiting_for": "scientist_review"})
    return {"approval": decision}

# workflow/runner.py
self._graph.invoke(self._graph_input(run_id), {"configurable": {"thread_id": run_id}})   # start or resume
self._graph.invoke(Command(resume={"reviewer": reviewer}), thread(run_id))               # after approval
```

### The whole path, in order

What happens when a scientist starts an investigation and the graph reaches the planner's step. Each line is a real function.

1. `Worker.run_pending()` (`jobs/worker.py`) picks up the queued run.
2. `RunExecutor.execute()` (`workflow/runner.py`) calls `graph.invoke(...)` on the run's thread.
3. LangGraph runs its nodes in order. At `coverage`, `InvestigationNodes.coverage()` (`workflow/nodes.py`) builds a `task.request` from the supervisor to the planner.
4. `Dispatcher.run()` queues it, and `MessageRouter.accept()` checks it (duplicate, depth, volume, allowlist).
5. `Dispatcher._deliver()` calls `PlannerAgent.handle()` (`agents/planner.py`).
6. The planner builds a counts-only prompt and calls `ask_model()`, which loads the pinned skill text and calls `ModelGateway.complete()` (`llm/gateway.py`).
7. The gateway checks the response cache, the approved models and the budget, reserves the worst-case cost, and tries the bound model, then its fallback.
8. `LangChainClient.generate()` (`llm/langchain_client.py`) builds a `ChatAnthropic` or `ChatOpenAI` and calls `invoke()`. This is the only LangChain call. The gateway settles the real cost and writes the call to the ledger.
9. The planner reads the reply as untrusted text: `parse_json_object`, then validation. A bad reply means no requests.
10. `handle()` returns an `AgentResult` whose `outgoing` holds up to 4 `evidence.request` messages.
11. The dispatcher records the planner's reply first, then queues the requests. Each goes through step 4 and on to a specialist's `answer_request()`, a search with no model call.
12. New evidence is merged into the run, `nodes.done()` saves it, and LangGraph moves on to the `critique` node.

