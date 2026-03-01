"""
Agent Builder Engine
Converts frontend graph JSON into an executable LangGraph agent.
Shows which node is executing and filters internal sub-tool events.
"""

from typing import TypedDict, Annotated, Sequence
import operator
import json

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from llm_providers import get_llm
from tools import TOOL_REGISTRY


class AgentState(TypedDict):
    """State that flows through the agent graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]


def build_agent_from_graph(graph_json: dict):
    nodes_data = graph_json.get("nodes", [])

    if not nodes_data:
        raise ValueError("No nodes in the agent graph")

    llm_nodes = [n for n in nodes_data if n.get("data", {}).get("category") == "llm"]
    tool_nodes = [n for n in nodes_data if n.get("data", {}).get("category") == "tool"]

    if not llm_nodes:
        raise ValueError("At least one LLM node is required")

    tools = []
    tool_info = {}
    for tn in tool_nodes:
        tool_id = tn["data"].get("toolId", "")
        if tool_id in TOOL_REGISTRY:
            t = TOOL_REGISTRY[tool_id]
            tools.append(t)
            tool_info[t.name] = {
                "label": tn["data"].get("label", tool_id),
                "toolId": tool_id,
            }

    primary_llm_data = llm_nodes[0]["data"]
    llm_label = primary_llm_data.get("label", "LLM")
    model = primary_llm_data.get("model", "llama-3.3-70b-versatile")
    config = primary_llm_data.get("config", {})
    temperature = config.get("temperature", 0.7)
    max_tokens = config.get("maxTokens", 1024)
    system_prompt = config.get("systemPrompt", "You are a helpful assistant.")

    if tools:
        tools_desc = ", ".join([info["label"] for info in tool_info.values()])
        system_prompt += (
            f"\n\nYou have access to the following tools: {tools_desc}. "
            "You MUST use these tools when the user asks something that requires "
            "real-time data, calculations, code execution, or web information. "
            "Always use the appropriate tool instead of saying you cannot access information. "
            "Call the tool first, then use the tool's output to formulate your answer."
        )

    llm = get_llm(model=model, temperature=temperature, max_tokens=max_tokens)

    if tools:
        llm_with_tools = llm.bind_tools(tools)
    else:
        llm_with_tools = llm

    workflow = StateGraph(AgentState)

    def agent_node(state):
        messages = list(state["messages"])
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages.insert(0, SystemMessage(content=system_prompt))
        try:
            response = llm_with_tools.invoke(messages)
        except Exception as e:
            error_msg = str(e)
            if "Failed to call a function" in error_msg or "failed_generation" in error_msg:
                messages.append(HumanMessage(
                    content="Please call the tool with a simple string argument."
                ))
                try:
                    response = llm_with_tools.invoke(messages)
                except Exception:
                    response = AIMessage(content="I encountered an error using the tool. Let me answer based on what I know.")
            else:
                raise
        return {"messages": [response]}

    workflow.add_node("agent", agent_node)

    if tools:
        def safe_tool_node(state):
            try:
                tool_executor = ToolNode(tools)
                return tool_executor.invoke(state)
            except Exception as e:
                last_msg = state["messages"][-1]
                tool_calls = getattr(last_msg, "tool_calls", [])
                error_messages = []
                for tc in tool_calls:
                    error_messages.append(ToolMessage(content=f"Tool error: {str(e)}", tool_call_id=tc["id"]))
                return {"messages": error_messages} if error_messages else {"messages": []}

        workflow.add_node("tools", safe_tool_node)

        def should_continue(state):
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
        workflow.add_edge("tools", "agent")
    else:
        workflow.add_edge("agent", END)

    workflow.set_entry_point("agent")
    compiled = workflow.compile()
    return compiled, system_prompt, tool_info, llm_label


# Known internal sub-tools to filter out (these are internal to our tools, not graph nodes)
INTERNAL_TOOLS = {"tavily_search_results_json", "TavilySearchResults"}


async def run_agent(graph_json: dict, message: str, history: list = None):
    """
    Build and execute the agent, yielding structured SSE events.
    Filters internal sub-tools and clearly shows graph node execution.
    """
    compiled, system_prompt, tool_info, llm_label = build_agent_from_graph(graph_json)

    messages = []
    if history:
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant" and h["content"]:
                messages.append(AIMessage(content=h["content"]))

    messages.append(HumanMessage(content=message))

    config = {"recursion_limit": 25}
    current_tool_label = None
    llm_call_count = 0  # Track which LLM call we're on
    has_tools = bool(tool_info)

    async for event in compiled.astream_events(
        {"messages": messages},
        config=config,
        version="v2",
    ):
        kind = event.get("event", "")
        tags = event.get("tags", [])

        # Only handle events from the top-level graph nodes, skip deeply nested ones
        # by checking if the event name is one of our known tools or the LLM
        event_name = event.get("name", "")

        if kind == "on_chat_model_start":
            llm_call_count += 1
            if llm_call_count == 1 and has_tools:
                # First LLM call — deciding which tools to use
                yield json.dumps({
                    "type": "step",
                    "step": "node_executing",
                    "nodeType": "llm",
                    "nodeName": llm_label,
                    "detail": "Analyzing query...",
                })
            elif llm_call_count > 1 and has_tools:
                # Second LLM call — generating final answer from tool results
                yield json.dumps({
                    "type": "step",
                    "step": "node_executing",
                    "nodeType": "llm",
                    "nodeName": llm_label,
                    "detail": "Generating answer...",
                })
            else:
                # No tools, just answering
                yield json.dumps({
                    "type": "step",
                    "step": "node_executing",
                    "nodeType": "llm",
                    "nodeName": llm_label,
                    "detail": "Generating response...",
                })

        elif kind == "on_chat_model_stream":
            content = event.get("data", {}).get("chunk", None)
            if content and hasattr(content, "content") and content.content:
                if isinstance(content.content, str) and content.content:
                    yield json.dumps({"type": "token", "token": content.content})

        elif kind == "on_chat_model_end":
            output = event.get("data", {}).get("output", None)
            if output and hasattr(output, "tool_calls") and output.tool_calls:
                for tc in output.tool_calls:
                    func_name = tc.get("name", "unknown")
                    # Skip internal sub-tools
                    if func_name in INTERNAL_TOOLS:
                        continue
                    tool_args = tc.get("args", {})
                    info = tool_info.get(func_name, {})
                    node_label = info.get("label", func_name)
                    # Simplify the input display
                    if isinstance(tool_args, dict) and len(tool_args) == 1:
                        input_display = list(tool_args.values())[0]
                    else:
                        input_display = json.dumps(tool_args) if isinstance(tool_args, dict) else str(tool_args)
                    yield json.dumps({
                        "type": "step",
                        "step": "tool_call",
                        "toolName": func_name,
                        "nodeName": node_label,
                        "input": str(input_display),
                    })

        elif kind == "on_tool_start":
            tool_name = event.get("name", "")
            # Skip internal sub-tools
            if tool_name in INTERNAL_TOOLS:
                continue
            if tool_name in tool_info:
                info = tool_info[tool_name]
                current_tool_label = info["label"]
                yield json.dumps({
                    "type": "step",
                    "step": "node_executing",
                    "nodeType": "tool",
                    "nodeName": current_tool_label,
                    "detail": "Running...",
                })

        elif kind == "on_tool_end":
            tool_name = event.get("name", "")
            # Skip internal sub-tools
            if tool_name in INTERNAL_TOOLS:
                continue
            if tool_name in tool_info:
                tool_output = event.get("data", {}).get("output", "")
                if hasattr(tool_output, "content"):
                    tool_output = tool_output.content
                content_str = str(tool_output)[:400]
                info = tool_info[tool_name]
                yield json.dumps({
                    "type": "step",
                    "step": "tool_result",
                    "nodeName": info["label"],
                    "content": content_str,
                })

    yield json.dumps({"type": "step", "step": "done"})
