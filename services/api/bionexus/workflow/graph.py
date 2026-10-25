"""The investigation as a LangGraph state graph.

    scope -> recall_memory -> specialists -> coverage -> critique <-+  (repair loop, max 2 rounds)
                                                            |       |
                                                            +-------+
    critique -> retrieve -> synthesize -> finalize
             -> await_review (human interrupt) -> complete

What LangGraph is used for here: the explicit graph shape, the bounded repair loop, retry of
transient source failures, durable checkpoints (resume after a crash at the exact step), and the
human-review interrupt. What it is *not* used for: our domain state (kept in our own tables),
agent-to-agent routing (our router), or memory (our scoped stores).
"""

from collections.abc import Callable
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, interrupt

from bionexus.contracts.errors import SourceUnavailable
from bionexus.workflow.nodes import InvestigationNodes
from bionexus.workflow.state import RunState

SOURCE_RETRY = RetryPolicy(
    max_attempts=3, initial_interval=0.5, jitter=False, retry_on=SourceUnavailable
)


class GraphState(TypedDict, total=False):
    """Only control data lives in the graph; the investigation itself is loaded by run_id."""

    run_id: str
    repair_round: int
    approval: dict[str, Any]


Work = Callable[[RunState, GraphState], dict[str, Any] | None]


def _step(nodes: InvestigationNodes, name: str, work: Work) -> Callable[[GraphState], dict]:
    """Wrap a unit of work: cancel check, load domain state, do work, save, announce."""

    def run(graph_state: GraphState) -> dict:
        run_id = graph_state["run_id"]
        nodes.ensure_not_cancelled(run_id)
        state = nodes.load(run_id)
        update = work(state, graph_state)
        nodes.done(state, name)
        return update or {}

    return run


LINEAR_EDGES = [
    (START, "scope"),
    ("scope", "recall_memory"),
    ("recall_memory", "specialists"),
    ("specialists", "coverage"),
    ("coverage", "critique"),
    ("retrieve", "synthesize"),
    ("synthesize", "finalize"),
    ("finalize", "await_review"),
    ("await_review", "complete"),
    ("complete", END),
]


class InvestigationGraph:
    def __init__(self, nodes: InvestigationNodes, disabled: frozenset[str] = frozenset()) -> None:
        self._nodes = nodes
        self._disabled = disabled  # steps turned into no-ops (evaluation ablations)

    def _coverage(self, state: RunState, gs: GraphState) -> None:
        if "coverage" not in self._disabled:
            self._nodes.coverage(state)

    def _critique(self, state: RunState, gs: GraphState) -> dict:
        round_number = gs.get("repair_round", 0)
        if "critique" not in self._disabled:
            self._nodes.critique_round(state, round_number)
        return {"repair_round": round_number + 1}

    def _after_critique(self, gs: GraphState) -> str:
        if "critique" in self._disabled:
            return "retrieve"
        state = self._nodes.load(gs["run_id"])
        return (
            "critique" if self._nodes.needs_repair(state, gs.get("repair_round", 0)) else "retrieve"
        )

    @staticmethod
    def _await_review(gs: GraphState) -> dict:
        """Pause durably until a scientist approves a specific report version."""
        decision = interrupt({"run_id": gs["run_id"], "waiting_for": "scientist_review"})
        return {"approval": decision}

    def _complete(self, gs: GraphState) -> dict:
        state = self._nodes.load(gs["run_id"])
        self._nodes.complete(state, gs["approval"]["reviewer"])
        self._nodes.done(state, "complete")
        return {}

    def _work(self) -> dict[str, Work]:
        n = self._nodes
        return {
            "scope": lambda s, gs: n.scope(s),
            "recall_memory": lambda s, gs: n.recall_memory(s),
            "specialists": lambda s, gs: n.specialists(s),
            "coverage": self._coverage,
            "critique": self._critique,
            "retrieve": lambda s, gs: n.retrieve(s),
            "synthesize": lambda s, gs: n.synthesize(s),
            "finalize": lambda s, gs: n.finalize(s),
        }

    def build(self, checkpointer: BaseCheckpointSaver) -> CompiledStateGraph:
        graph = StateGraph(GraphState)
        for name, work in self._work().items():
            policy = SOURCE_RETRY if name == "specialists" else None
            graph.add_node(name, _step(self._nodes, name, work), retry_policy=policy)
        graph.add_node("await_review", self._await_review)
        graph.add_node("complete", self._complete)
        for before, after in LINEAR_EDGES:
            graph.add_edge(before, after)
        routes = {"critique": "critique", "retrieve": "retrieve"}
        graph.add_conditional_edges("critique", self._after_critique, routes)
        return graph.compile(checkpointer=checkpointer)


def build_graph(
    nodes: InvestigationNodes,
    checkpointer: BaseCheckpointSaver,
    disabled: frozenset[str] = frozenset(),
) -> CompiledStateGraph:
    return InvestigationGraph(nodes, disabled).build(checkpointer)
