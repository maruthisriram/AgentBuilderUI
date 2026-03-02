"""Graph Compiler — True React Flow → LangGraph compilation.
Converts frontend graph JSON into an executable LangGraph StateGraph.
Supports: pipelines, tool binding, conditional routing, handoffs, supervisor-worker delegation.
"""

from typing import TypedDict, Annotated, Sequence
import operator
import json
import re

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from app.config import settings
from app.services.llm_factory import get_llm
from app.services.tool_registry import TOOL_REGISTRY
from app.utils.tool_fixer import fix_tool_calls
from app.utils.logging import get_logger

logger = get_logger("compiler")


class AgentState(TypedDict):
    """State that flows through the agent graph."""
    messages: Annotated[Sequence[BaseMessage], operator.add]


# Known internal sub-tools to filter out
INTERNAL_TOOLS = {"tavily_search_results_json", "TavilySearchResults"}


def build_agent_from_graph(graph_json: dict):
    """
    True graph compilation: reads nodes AND edges from the React Flow graph
    and builds an equivalent LangGraph StateGraph.
    """
    nodes_data = graph_json.get("nodes", [])
    edges_data = graph_json.get("edges", [])

    if not nodes_data:
        raise ValueError("No nodes in the agent graph")

    # ── Step 1: Index all nodes by ID ──
    node_map = {}
    for n in nodes_data:
        node_map[n["id"]] = n

    # Categorize nodes
    llm_nodes = {n["id"]: n for n in nodes_data if n.get("data", {}).get("category") == "llm"}
    tool_nodes = {n["id"]: n for n in nodes_data if n.get("data", {}).get("category") == "tool"}
    flow_nodes = {n["id"]: n for n in nodes_data if n.get("data", {}).get("category") == "flow"}

    if not llm_nodes:
        raise ValueError("At least one LLM node is required")

    logger.info(f"Compiling graph: {len(llm_nodes)} LLMs, {len(tool_nodes)} tools, {len(flow_nodes)} flow nodes, {len(edges_data)} edges")

    # ── Step 2: Build adjacency from edges ──
    outgoing = {}  # source_id → [(target_id, sourceHandle)]
    incoming = {}  # target_id → [source_id]

    for edge in edges_data:
        src = edge.get("source")
        tgt = edge.get("target")
        handle = edge.get("sourceHandle", None)
        if src and tgt:
            outgoing.setdefault(src, []).append((tgt, handle))
            incoming.setdefault(tgt, []).append(src)

    # ── Step 3: For each LLM, find its connected tools ──
    llm_tools = {}  # llm_id → [tool_functions]
    llm_tool_info = {}  # llm_id → {func_name: {label, toolId}}
    tool_nodes_used = set()

    for llm_id in llm_nodes:
        tools = []
        tool_info = {}
        for target_id, _ in outgoing.get(llm_id, []):
            if target_id in tool_nodes:
                tn = tool_nodes[target_id]
                tool_id = tn["data"].get("toolId", "")
                tool_nodes_used.add(target_id)

                if tool_id == "tool-knowledge-base":
                    kb_config = tn.get("data", {}).get("config", {})
                    kb_id = kb_config.get("kbId")
                    kb_name = tn["data"].get("label", "Knowledge Base")
                    if kb_id:
                        from app.services.rag_engine import create_kb_retriever_tool
                        t = create_kb_retriever_tool(kb_id, kb_name)
                        tools.append(t)
                        tool_info[t.name] = {"label": kb_name, "toolId": tool_id}
                elif tool_id in TOOL_REGISTRY:
                    t = TOOL_REGISTRY[tool_id]
                    tools.append(t)
                    tool_info[t.name] = {
                        "label": tn["data"].get("label", tool_id),
                        "toolId": tool_id,
                    }

        # Also check tools connected TO this LLM (tool → LLM edge means tool feeds back)
        for src_id in incoming.get(llm_id, []):
            if src_id in tool_nodes and src_id not in tool_nodes_used:
                tn = tool_nodes[src_id]
                tool_id = tn["data"].get("toolId", "")
                tool_nodes_used.add(src_id)
                if tool_id in TOOL_REGISTRY:
                    t = TOOL_REGISTRY[tool_id]
                    tools.append(t)
                    tool_info[t.name] = {
                        "label": tn["data"].get("label", tool_id),
                        "toolId": tool_id,
                    }

        llm_tools[llm_id] = tools
        llm_tool_info[llm_id] = tool_info
        if tools:
            logger.info(f"LLM '{llm_nodes[llm_id]['data'].get('label')}' bound to {len(tools)} tools")

    # Merge all tool_info for event streaming
    all_tool_info = {}
    for ti in llm_tool_info.values():
        all_tool_info.update(ti)

    # ── Step 4: Detect supervisor pattern ──
    # If an LLM connects to 2+ other LLMs, it's a supervisor → wrap workers as tools
    supervisor_workers = {}  # supervisor_llm_id → [worker_llm_ids]
    worker_llm_ids = set()

    for llm_id in llm_nodes:
        llm_targets = []
        for target_id, _ in outgoing.get(llm_id, []):
            if target_id in llm_nodes:
                llm_targets.append(target_id)
        if len(llm_targets) >= 2:
            supervisor_workers[llm_id] = llm_targets
            worker_llm_ids.update(llm_targets)
            logger.info(f"Supervisor detected: '{llm_nodes[llm_id]['data'].get('label')}' → {len(llm_targets)} workers")

    # Create worker LLM tools for supervisors
    for sup_id, worker_ids in supervisor_workers.items():
        for w_id in worker_ids:
            w_node = llm_nodes[w_id]
            w_label = w_node["data"].get("label", "Worker")
            w_model = w_node["data"].get("model", settings.default_model)
            w_config = w_node["data"].get("config", {})
            w_sys_prompt = w_config.get("systemPrompt", "You are a helpful assistant.")
            w_temp = w_config.get("temperature", settings.default_temperature)
            w_max = w_config.get("maxTokens", settings.default_max_tokens)

            # Create a tool name from the worker label
            safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', w_label.lower()).strip('_')
            tool_name = f"delegate_to_{safe_name}"

            # Create a tool that invokes the worker LLM
            def make_worker_tool(_model, _temp, _max, _sys, _name, _label):
                @tool
                def worker_delegate(task: str) -> str:
                    """Delegate a task to a specialized worker agent."""
                    worker_llm = get_llm(model=_model, temperature=_temp, max_tokens=_max)
                    messages = [
                        SystemMessage(content=_sys),
                        HumanMessage(content=task),
                    ]
                    response = worker_llm.invoke(messages)
                    return response.content if hasattr(response, 'content') else str(response)

                worker_delegate.name = _name
                worker_delegate.description = (
                    f"Delegate a task to the '{_label}' specialist agent. "
                    f"This agent has the following role: {_sys[:100]}... "
                    f"Send a clear task description as input."
                )
                return worker_delegate

            w_tool = make_worker_tool(w_model, w_temp, w_max, w_sys_prompt, tool_name, w_label)

            # Add worker tool to the supervisor's tools
            if sup_id not in llm_tools:
                llm_tools[sup_id] = []
            llm_tools[sup_id].append(w_tool)

            if sup_id not in llm_tool_info:
                llm_tool_info[sup_id] = {}
            llm_tool_info[sup_id][tool_name] = {
                "label": f"{w_label} (Worker)",
                "toolId": f"worker-{w_id}",
            }
            all_tool_info[tool_name] = {
                "label": f"{w_label} (Worker)",
                "toolId": f"worker-{w_id}",
            }

    # ── Step 5: Detect handoff pipelines ──
    # For LLM → LLM edges (non-supervisor), track which LLM comes before
    handoff_source = {}  # target_llm_id → source_llm_label
    for llm_id in llm_nodes:
        if llm_id in supervisor_workers:
            continue  # Supervisors don't do handoffs
        for target_id, _ in outgoing.get(llm_id, []):
            if target_id in llm_nodes and target_id not in worker_llm_ids:
                src_label = llm_nodes[llm_id]["data"].get("label", "Previous Agent")
                handoff_source[target_id] = src_label

    # ── Step 6: Create LangGraph nodes for each LLM ──
    workflow = StateGraph(AgentState)
    llm_labels = {}  # llm_id → display label

    # Skip worker LLMs that are handled as supervisor tools
    active_llm_nodes = {k: v for k, v in llm_nodes.items() if k not in worker_llm_ids}

    for llm_id, llm_node in active_llm_nodes.items():
        llm_data = llm_node["data"]
        label = llm_data.get("label", "LLM")
        model = llm_data.get("model", settings.default_model)
        config = llm_data.get("config", {})
        temperature = config.get("temperature", settings.default_temperature)
        max_tokens = config.get("maxTokens", settings.default_max_tokens)
        system_prompt = config.get("systemPrompt", "You are a helpful assistant.")

        tools = llm_tools.get(llm_id, [])
        tool_info = llm_tool_info.get(llm_id, {})

        # Enhance system prompt for supervisors
        if llm_id in supervisor_workers:
            worker_names = [llm_nodes[w]["data"].get("label", "Worker") for w in supervisor_workers[llm_id]]
            system_prompt += (
                f"\n\nYou are a SUPERVISOR agent. You coordinate specialized worker agents: {', '.join(worker_names)}. "
                "Analyze the user's request and delegate sub-tasks to the appropriate worker(s) using your tools. "
                "You can call multiple workers if needed. After receiving their results, synthesize a final answer."
            )

        # Enhance system prompt with tool descriptions
        if tools:
            tools_desc = ", ".join([info["label"] for info in tool_info.values()])
            system_prompt += (
                f"\n\nYou have access to the following tools: {tools_desc}. "
                "You MUST use these tools when the user asks something that requires "
                "real-time data, calculations, code execution, or web information. "
                "Always use the appropriate tool instead of saying you cannot access information. "
                "Call the tool first, then use the tool's output to formulate your answer."
            )

        # Add handoff context for pipeline LLMs
        if llm_id in handoff_source:
            src_label = handoff_source[llm_id]
            system_prompt += (
                f"\n\nYou are receiving a HANDOFF from '{src_label}'. "
                "The previous agent's response is in the conversation above. "
                "Use that context and apply YOUR specific expertise to continue the task."
            )

        llm = get_llm(model=model, temperature=temperature, max_tokens=max_tokens)
        llm_with_tools = llm.bind_tools(tools) if tools else llm

        llm_labels[llm_id] = label

        # Create the agent node
        def make_agent_node(_llm_with_tools, _system_prompt, _tools, _label):
            def agent_node(state):
                messages = list(state["messages"])
                # Replace any existing system message with this node's prompt
                messages = [m for m in messages if not isinstance(m, SystemMessage)]
                messages.insert(0, SystemMessage(content=_system_prompt))
                try:
                    response = _llm_with_tools.invoke(messages)
                except Exception as e:
                    error_msg = str(e)
                    if "Failed to call a function" in error_msg or "failed_generation" in error_msg:
                        messages.append(HumanMessage(
                            content="Please call the tool with a simple string argument."
                        ))
                        try:
                            response = _llm_with_tools.invoke(messages)
                        except Exception:
                            response = AIMessage(content="I encountered an error using the tool. Let me answer based on what I know.")
                    else:
                        raise

                # Fix malformed tool calls
                if _tools:
                    response = fix_tool_calls(response, _tools)

                return {"messages": [response]}
            return agent_node

        node_name = f"llm_{llm_id}"
        workflow.add_node(node_name, make_agent_node(llm_with_tools, system_prompt, tools, label))

        # If this LLM has tools, add a tool executor node and ReAct loop
        if tools:
            tool_executor = ToolNode(tools)
            tools_node_name = f"tools_{llm_id}"

            def make_safe_tool_node(_tool_executor):
                def safe_tool_node(state):
                    try:
                        return _tool_executor.invoke(state)
                    except Exception as e:
                        last_msg = state["messages"][-1]
                        tool_calls = getattr(last_msg, "tool_calls", [])
                        error_messages = []
                        for tc in tool_calls:
                            error_messages.append(
                                ToolMessage(content=f"Tool error: {str(e)}", tool_call_id=tc["id"])
                            )
                        return {"messages": error_messages} if error_messages else {"messages": []}
                return safe_tool_node

            workflow.add_node(tools_node_name, make_safe_tool_node(tool_executor))
            workflow.add_edge(tools_node_name, node_name)  # tools → back to LLM

    # ── Step 7: Create edges from React Flow topology ──
    entry_node = None
    conditional_nodes = {}  # react_flow_id → node_data

    for flow_id, flow_node in flow_nodes.items():
        tool_id = flow_node["data"].get("toolId", "")
        if tool_id == "flow-input":
            for target_id, _ in outgoing.get(flow_id, []):
                if target_id in llm_nodes and target_id not in worker_llm_ids:
                    entry_node = f"llm_{target_id}"
        elif tool_id == "flow-conditional":
            conditional_nodes[flow_id] = flow_node

    # Process edges for active LLM nodes only (workers are handled as tools)
    for llm_id in active_llm_nodes:
        node_name = f"llm_{llm_id}"
        tools = llm_tools.get(llm_id, [])
        non_tool_targets = []

        for target_id, handle in outgoing.get(llm_id, []):
            if target_id in tool_nodes_used:
                continue  # Already handled as tool binding
            if target_id in worker_llm_ids:
                continue  # Workers are handled as supervisor tools
            if target_id in llm_nodes:
                non_tool_targets.append((f"llm_{target_id}", handle))
            elif target_id in flow_nodes:
                tool_id = flow_nodes[target_id]["data"].get("toolId", "")
                if tool_id == "flow-output":
                    non_tool_targets.append((END, handle))
                elif tool_id == "flow-conditional":
                    non_tool_targets.append((f"cond_{target_id}", handle))

        if tools:
            next_targets = non_tool_targets if non_tool_targets else [(END, None)]
            tools_node_name = f"tools_{llm_id}"

            if len(next_targets) == 1:
                done_target = next_targets[0][0]
            else:
                done_target = next_targets[0][0]

            def make_should_continue(_tools_node, _done_target):
                def should_continue(state):
                    last_message = state["messages"][-1]
                    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                        return _tools_node
                    return _done_target
                return should_continue

            route_map = {tools_node_name: tools_node_name, done_target: done_target}
            workflow.add_conditional_edges(
                node_name,
                make_should_continue(tools_node_name, done_target),
                route_map,
            )
        else:
            if non_tool_targets:
                for target, _ in non_tool_targets:
                    workflow.add_edge(node_name, target)
            else:
                workflow.add_edge(node_name, END)

    # ── Step 8: Handle Conditional Router nodes ──
    for cond_id, cond_node in conditional_nodes.items():
        cond_config = cond_node.get("data", {}).get("config", {})
        condition_str = cond_config.get("condition", "")

        cond_node_name = f"cond_{cond_id}"

        def make_cond_passthrough():
            def cond_passthrough(state):
                return {"messages": []}
            return cond_passthrough

        workflow.add_node(cond_node_name, make_cond_passthrough())

        true_target = END
        false_target = END
        for target_id, handle in outgoing.get(cond_id, []):
            target_name = END
            if target_id in active_llm_nodes:
                target_name = f"llm_{target_id}"
            elif target_id in flow_nodes and flow_nodes[target_id]["data"].get("toolId") == "flow-output":
                target_name = END

            if handle == "true":
                true_target = target_name
            elif handle == "false":
                false_target = target_name
            else:
                true_target = target_name

        def make_condition_func(_condition_str, _true_target, _false_target):
            def evaluate_condition(state):
                last_message = state["messages"][-1]
                content = last_message.content if hasattr(last_message, "content") else ""

                if _condition_str == "has_tool_calls":
                    result = hasattr(last_message, "tool_calls") and bool(last_message.tool_calls)
                elif _condition_str.startswith("contains:"):
                    keyword = _condition_str.split(":", 1)[1].strip()
                    result = keyword.lower() in content.lower()
                elif _condition_str:
                    result = _condition_str.lower() in content.lower()
                else:
                    result = True

                return _true_target if result else _false_target
            return evaluate_condition

        route_map = {true_target: true_target, false_target: false_target}
        workflow.add_conditional_edges(
            cond_node_name,
            make_condition_func(condition_str, true_target, false_target),
            route_map,
        )

    # ── Step 9: Set entry point ──
    if entry_node:
        workflow.set_entry_point(entry_node)
    else:
        first_llm_id = list(active_llm_nodes.keys())[0]
        entry_node = f"llm_{first_llm_id}"
        workflow.set_entry_point(entry_node)

    logger.info(f"Graph compiled: entry={entry_node}, supervisors={len(supervisor_workers)}, workers={len(worker_llm_ids)}, handoffs={len(handoff_source)}")

    # ── Step 10: Compile ──
    compiled = workflow.compile()
    primary_label = list(llm_labels.values())[0] if llm_labels else "LLM"

    return compiled, all_tool_info, llm_labels, primary_label


async def run_agent(graph_json: dict, message: str, history: list = None):
    """
    Build and execute the agent, yielding structured SSE events.
    Filters internal sub-tools and clearly shows graph node execution.
    """
    compiled, tool_info, llm_labels, primary_label = build_agent_from_graph(graph_json)

    messages = []
    if history:
        for h in history:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant" and h["content"]:
                messages.append(AIMessage(content=h["content"]))

    messages.append(HumanMessage(content=message))

    config = {"recursion_limit": settings.recursion_limit}
    llm_call_count = 0
    has_tools = bool(tool_info)

    logger.info(f"Running agent: message='{message[:50]}...', tools={list(tool_info.keys())}")

    async for event in compiled.astream_events(
        {"messages": messages},
        config=config,
        version="v2",
    ):
        kind = event.get("event", "")
        event_name = event.get("name", "")

        if kind == "on_chat_model_start":
            llm_call_count += 1
            node_label = primary_label
            for llm_id, label in llm_labels.items():
                if llm_id in event_name or label in event_name:
                    node_label = label
                    break

            if llm_call_count == 1 and has_tools:
                detail = "Analyzing query..."
            elif llm_call_count > 1 and has_tools:
                detail = "Generating answer..."
            else:
                detail = "Generating response..."

            yield json.dumps({
                "type": "step",
                "step": "node_executing",
                "nodeType": "llm",
                "nodeName": node_label,
                "detail": detail,
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
                    if func_name in INTERNAL_TOOLS:
                        continue
                    tool_args = tc.get("args", {})
                    info = tool_info.get(func_name, {})
                    node_label = info.get("label", func_name)
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
            if tool_name in INTERNAL_TOOLS:
                continue
            if tool_name in tool_info:
                info = tool_info[tool_name]
                yield json.dumps({
                    "type": "step",
                    "step": "node_executing",
                    "nodeType": "tool",
                    "nodeName": info["label"],
                    "detail": "Running...",
                })

        elif kind == "on_tool_end":
            tool_name = event.get("name", "")
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

    logger.info("Agent execution complete")
    yield json.dumps({"type": "step", "step": "done"})
