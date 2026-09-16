import asyncio
from typing import Any, Callable


class FaultInjectionError(Exception):
    """Custom exception raised when a fault is injected."""
    pass


class FaultInjector:
    """
    Manages and injects simulated tool faults (DEV-GUIDE 9.5).
    Types: timeout | empty | http_403 | http_429
    """
    def __init__(self, fault_configs: list[dict[str, Any]] | None = None):
        self.fault_configs = fault_configs or []
        self.call_counters: dict[str, int] = {}
        self.injected_history: list[dict[str, Any]] = []

    def record_call(self, tool_name: str) -> dict[str, Any] | None:
        count = self.call_counters.get(tool_name, 0) + 1
        self.call_counters[tool_name] = count

        for fault in self.fault_configs:
            if fault.get("tool") == tool_name and fault.get("on_call") == count:
                fault_info = {
                    "tool": tool_name,
                    "call_index": count,
                    "type": fault.get("type"),
                }
                self.injected_history.append(fault_info)
                return fault_info
        return None

    async def execute_with_fault(
        self,
        tool_name: str,
        func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        fault = self.record_call(tool_name)
        if fault:
            f_type = fault.get("type")
            if f_type == "timeout":
                raise asyncio.TimeoutError(f"Simulated timeout on {tool_name} call #{fault['call_index']}")
            elif f_type == "empty":
                return []
            elif f_type == "http_403":
                raise FaultInjectionError(f"Simulated HTTP 403 Forbidden for {tool_name}")
            elif f_type == "http_429":
                raise FaultInjectionError(f"Simulated HTTP 429 Too Many Requests for {tool_name}")

        return await func(*args, **kwargs)
