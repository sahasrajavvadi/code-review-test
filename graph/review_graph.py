from langgraph.graph import StateGraph, START, END
from typing import TypedDict

from agents.correctness_agent import acorrectness_agent
from agents.security_agent import asecurity_agent
from agents.performance_agent import aperformance_agent
from agents.maintainability_agent import amaintainability_agent
from agents.dependency_agent import adependency_agent
from agents.test_agent import atest_agent
from agents.critic_agent import critic_agent, score_review
from agents.autofix_agent import autofix_agent


class ReviewState(TypedDict):
    diff: str
    context: str
    memory_context: str
    tool_outputs: dict
    correctness_review: str
    security_review: str
    performance_review: str
    maintainability_review: str
    dependency_review: str
    test_review: str
    final_review: str
    autofix_suggestions: str
    score: str


# --- Specialist agent nodes (all async, run in parallel) ---

async def run_correctness(state: ReviewState) -> dict:
    print("\n  🔍 Running Correctness & Reliability Agent...")
    result = await acorrectness_agent(
        state["diff"],
        memory_context=state.get("memory_context", ""),
    )
    return {"correctness_review": result}


async def run_security(state: ReviewState) -> dict:
    print("\n  🔴 Running Security Agent...")
    tools = state.get("tool_outputs", {})
    tool_text = "\n".join(filter(None, [tools.get("bandit", ""), tools.get("detect-secrets", "")]))
    result = await asecurity_agent(
        state["diff"],
        memory_context=state.get("memory_context", ""),
        tool_output=tool_text,
    )
    return {"security_review": result}


async def run_performance(state: ReviewState) -> dict:
    print("\n  🟡 Running Performance Agent...")
    tools = state.get("tool_outputs", {})
    result = await aperformance_agent(
        state["diff"],
        memory_context=state.get("memory_context", ""),
        tool_output=tools.get("radon", ""),
    )
    return {"performance_review": result}


async def run_maintainability(state: ReviewState) -> dict:
    print("\n  🏗️ Running Maintainability Agent...")
    tools = state.get("tool_outputs", {})
    tool_text = "\n".join(filter(None, [tools.get("ruff", ""), tools.get("eslint", "")]))
    result = await amaintainability_agent(
        state["diff"],
        context=state.get("context", ""),
        memory_context=state.get("memory_context", ""),
        tool_output=tool_text,
    )
    return {"maintainability_review": result}


async def run_dependency(state: ReviewState) -> dict:
    print("\n  📦 Running Dependency Agent...")
    tools = state.get("tool_outputs", {})
    result = await adependency_agent(
        state["diff"],
        tool_output=tools.get("pip-audit", ""),
        memory_context=state.get("memory_context", ""),
    )
    return {"dependency_review": result}


async def run_test(state: ReviewState) -> dict:
    print("\n  🧪 Running Test Agent...")
    result = await atest_agent(
        state["diff"],
        memory_context=state.get("memory_context", ""),
    )
    return {"test_review": result}


# --- Post-review nodes (sequential after fan-in) ---

def run_manager(state: ReviewState) -> dict:
    print("\n  ⚡ Running Manager Agent (merge decision)...")
    result = critic_agent(
        state["correctness_review"],
        state["security_review"],
        state["performance_review"],
        state["maintainability_review"],
        state.get("dependency_review", ""),
        state.get("test_review", ""),
    )
    return {"final_review": result}


def run_autofix(state: ReviewState) -> dict:
    print("\n  🔧 Running Auto-Fix Agent...")
    result = autofix_agent(state["diff"], state["final_review"])
    return {"autofix_suggestions": result}


def run_scorer(state: ReviewState) -> dict:
    print("\n  📊 Scoring review quality...")
    score = score_review(state["final_review"])
    print(f"  Review quality score: {score}/10")
    return {"score": score}


def build_graph():
    """
    6-agent parallel fan-out → manager → [autofix + scorer in parallel] → END

              ┌─► correctness ──────────────┐
              ├─► security (bandit+secrets) ┤
    START ────┼─► performance (radon) ──────┼──► manager ──┬─► autofix ──► END
              ├─► maintainability (ruff) ───┤             └─► scorer  ──► END
              ├─► dependency (pip-audit) ───┤
              └─► test ─────────────────────┘

    autofix and scorer both depend only on the manager's output,
    so LangGraph schedules them in the same superstep (parallel).
    """
    graph = StateGraph(ReviewState)

    graph.add_node("correctness", run_correctness)
    graph.add_node("security", run_security)
    graph.add_node("performance", run_performance)
    graph.add_node("maintainability", run_maintainability)
    graph.add_node("dependency", run_dependency)
    graph.add_node("test", run_test)
    graph.add_node("manager", run_manager)
    graph.add_node("autofix", run_autofix)
    graph.add_node("scorer", run_scorer)

    # Fan-out: all 6 specialists start simultaneously
    for agent in ["correctness", "security", "performance",
                   "maintainability", "dependency", "test"]:
        graph.add_edge(START, agent)
        graph.add_edge(agent, "manager")

    # After manager: autofix and scorer run in parallel
    graph.add_edge("manager", "autofix")
    graph.add_edge("manager", "scorer")
    graph.add_edge("autofix", END)
    graph.add_edge("scorer", END)

    return graph.compile()
