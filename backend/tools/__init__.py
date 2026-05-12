from typing import Callable


class ToolError(Exception):
    pass


COACH_TOOLS: dict[str, Callable] = {}
ANALYST_TOOLS: dict[str, Callable] = {}
COACH_SCHEMAS: list[dict] = []
ANALYST_SCHEMAS: list[dict] = []


def coach_tool(name: str, schema: dict):
    def decorator(fn: Callable) -> Callable:
        COACH_TOOLS[name] = fn
        COACH_SCHEMAS.append({"name": name, **schema})
        return fn
    return decorator


def analyst_tool(name: str, schema: dict):
    def decorator(fn: Callable) -> Callable:
        ANALYST_TOOLS[name] = fn
        ANALYST_SCHEMAS.append({"name": name, **schema})
        return fn
    return decorator
