"""Tools in one form, whichever provider the model comes from: LangChain's StructuredTool.

A tool is a function the model may ask the app to run (the model never runs
code itself). `make_tool` turns one of ours into a LangChain `StructuredTool`:
a name, a description (how the model decides to call it), its inputs as a
JSON schema, and the function that runs it. LangChain then describes it to
each provider in that provider's own format (`bind_tools`), and gives every
provider's requests back the same way, `{"name", "args", "id"}`.

`run_requests` runs those requests with `tool.invoke`, which returns each
result as a ToolMessage tied to its request by id, and records each run as
its own step in a LangSmith trace.

The inputs' JSON schema is a description for the model; LangChain does not
check it (a model can leave a "required" input out), so each tool's own code
checks what it is given.
"""

import json
from collections.abc import Callable
from typing import Any

from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool


def make_tool(name: str, description: str, parameters: dict[str, Any],
              run: Callable[[dict[str, Any]], Any]) -> StructuredTool:
    """A LangChain tool that runs `run` with the model's inputs as one dict.
    `parameters` is the inputs' JSON schema, of type "object"; `run` returns
    something JSON can hold."""
    return StructuredTool.from_function(func=lambda **args: run(args), name=name, description=description,
                                        args_schema=parameters)


def run_requests(requests: list[dict[str, Any]], tools: list[BaseTool]) -> list[ToolMessage]:
    """Run each tool request (`{"name", "args", "id"}`) and return its result
    as a ToolMessage, tied to the request by id. Every request gets a result,
    because a model's next call is refused when one is missing; a request for
    a tool that does not exist gets an error result the model can read."""
    by_name = {tool.name: tool for tool in tools}
    results = []
    for request in requests:
        tool = by_name.get(request["name"])
        if tool is None:
            error = json.dumps({"error": f"There is no tool called {request['name']}."})
            results.append(ToolMessage(error, tool_call_id=request["id"], name=request["name"]))
            continue
        results.append(tool.invoke({"type": "tool_call", "name": request["name"], "args": request["args"],
                                    "id": request["id"]}))
    return results
