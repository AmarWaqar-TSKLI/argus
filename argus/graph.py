"""The Argus crawl-and-audit loop.

        ┌────────────────────────────────────┐
        ▼                                    │
START → explore → dom_audit → vision_audit ──┤ more in frontier?
                                             │
                                             └─ no → report → END
"""
from langgraph.graph import END, START, StateGraph

from argus.nodes.dom_audit import dom_audit
from argus.nodes.explorer import explore
from argus.nodes.reporter import report
from argus.nodes.vision_audit import vision_audit
from argus.state import ArgusState


def should_continue(state: ArgusState) -> str:
    if state["frontier"] and len(state["visited"]) < state["max_pages"]:
        return "explore"
    return "report"


def build_graph():
    g = StateGraph(ArgusState)
    g.add_node("explore", explore)
    g.add_node("dom_audit", dom_audit)
    g.add_node("vision_audit", vision_audit)
    g.add_node("report", report)

    g.add_edge(START, "explore")
    g.add_edge("explore", "dom_audit")
    g.add_edge("dom_audit", "vision_audit")
    g.add_conditional_edges("vision_audit", should_continue, ["explore", "report"])
    g.add_edge("report", END)
    return g.compile()
