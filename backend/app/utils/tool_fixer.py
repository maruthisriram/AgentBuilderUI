"""
Tool Call Fixer — handles malformed LLM tool calling outputs.
Fixes concatenated names, wrong formats, text-based tool calls, etc.
"""

import re
import json

from app.utils.logging import get_logger

logger = get_logger("tool_fixer")


def fix_tool_calls(response, available_tools):
    """
    Fix malformed tool calls from LLMs that don't produce clean OpenAI-format calls.
    Handles: concatenated name+args, missing args, wrong format, text-based tool calls.
    """
    if not hasattr(response, "tool_calls") or not response.tool_calls:
        # Try to extract tool calls from text content (fallback for non-tool-calling LLMs)
        if hasattr(response, "content") and response.content and available_tools:
            extracted = _extract_tool_calls_from_text(response.content, available_tools)
            if extracted:
                logger.info(f"Extracted {len(extracted)} tool calls from text content")
                response.tool_calls = extracted
                return response
        return response

    tool_names = {t.name for t in available_tools}
    fixed_calls = []

    for tc in response.tool_calls:
        name = tc.get("name", "")
        args = tc.get("args", {})
        tc_id = tc.get("id", f"call_{hash(name) % 100000}")

        # Fix 1: Name has args concatenated (e.g., "search_kb {"query": "..."}")
        if " " in name:
            parts = name.split(" ", 1)
            name = parts[0]
            if not args:
                try:
                    args = json.loads(parts[1])
                except Exception:
                    args = {"query": parts[1]}
            logger.debug(f"Fixed concatenated tool call: {tc.get('name')} -> {name}")

        # Fix 2: Name has hyphens (not allowed in OpenAI format)
        name = name.replace("-", "_")

        # Fix 3: Name doesn't match any tool — try fuzzy match
        if name not in tool_names:
            matched = _fuzzy_match_tool(name, tool_names)
            if matched:
                logger.debug(f"Fuzzy matched tool: {name} -> {matched}")
                name = matched

        # Fix 4: Args is a string instead of dict
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"query": args}

        tc["name"] = name
        tc["args"] = args
        tc["id"] = tc_id
        fixed_calls.append(tc)

    response.tool_calls = fixed_calls

    # Also fix in additional_kwargs
    if hasattr(response, "additional_kwargs"):
        ak_tool_calls = response.additional_kwargs.get("tool_calls", [])
        for i, atc in enumerate(ak_tool_calls):
            fn = atc.get("function", {})
            if i < len(fixed_calls):
                fn["name"] = fixed_calls[i]["name"]
                if isinstance(fn.get("arguments"), str):
                    try:
                        fn["arguments"] = json.dumps(fixed_calls[i]["args"])
                    except Exception:
                        pass

    return response


def _fuzzy_match_tool(name, tool_names):
    """Try to match a malformed tool name to an actual tool."""
    name_lower = name.lower()
    for tn in tool_names:
        if tn.lower() == name_lower:
            return tn
        if name_lower in tn.lower() or tn.lower() in name_lower:
            return tn
    return None


def _extract_tool_calls_from_text(content, available_tools):
    """
    Fallback: Extract tool calls from LLM text output.
    Handles patterns like: "I'll use web_search("query")" or "Action: web_search\nInput: query"
    """
    tool_names = {t.name for t in available_tools}
    extracted = []

    for tool_name in tool_names:
        # Pattern: tool_name("arg") or tool_name(arg)
        pattern = rf'{re.escape(tool_name)}\s*\(\s*["\']?(.+?)["\']?\s*\)'
        match = re.search(pattern, content)
        if match:
            extracted.append({
                "name": tool_name,
                "args": {"query": match.group(1)},
                "id": f"call_extracted_{len(extracted)}",
            })
            continue

        # Pattern: Action: tool_name / Input: arg
        pattern = rf'Action:\s*{re.escape(tool_name)}\s*\n\s*(?:Action\s*)?Input:\s*(.+)'
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            extracted.append({
                "name": tool_name,
                "args": {"query": match.group(1).strip()},
                "id": f"call_extracted_{len(extracted)}",
            })

    return extracted if extracted else None
