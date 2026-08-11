"""The Argus crawl-audit-interact loop, with verification and filing.

        ┌──────────────────────────────────────────────────┐
        ▼                                                  │
START → explore → dom_audit → regression → vision_audit ───┤ more in frontier?
        (Playwright) (free)    (SSIM, free)  (VLM chain)   │
                                                           ▼ no
                        plan_flows → act_flows → verify → file_issues
                        (enumerate    (execute,             │
                         + planner)    judge)               ▼
                                              END ← report ─┘
"""
from langgraph.graph import END, START, StateGraph

from argus.nodes.dom_audit import dom_audit
from argus.nodes.explorer import explore
from argus.nodes.flows import act_flows, plan_flows
from argus.nodes.issues import file_issues
from argus.nodes.regression import regression
from argus.nodes.reporter import report
from argus.nodes.verifier import verify
from argus.nodes.vision_audit import vision_audit
from argus.state import ArgusState


def should_continue(state: ArgusState) -> str:
    if state["frontier"] and len(state["visited"]) < state["max_pages"]:
        return "explore"
    return "plan_flows"


def build_graph(checkpointer=None):
    g = StateGraph(ArgusState)
    g.add_node("explore", explore)
    g.add_node("dom_audit", dom_audit)
    g.add_node("regression", regression)
    g.add_node("vision_audit", vision_audit)
    g.add_node("plan_flows", plan_flows)
    g.add_node("act_flows", act_flows)
    g.add_node("verify", verify)
    g.add_node("file_issues", file_issues)
    g.add_node("report", report)

    g.add_edge(START, "explore")
    g.add_edge("explore", "dom_audit")
    g.add_edge("dom_audit", "regression")
    g.add_edge("regression", "vision_audit")
    g.add_conditional_edges("vision_audit", should_continue, ["explore", "plan_flows"])
    g.add_edge("plan_flows", "act_flows")
    g.add_edge("act_flows", "verify")
    g.add_edge("verify", "file_issues")
    g.add_edge("file_issues", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer)
