"""
Safe tool execution example for Scooper.

This example demonstrates how to:
- Create tools with different permission levels
- Configure permission policies (allowlist/denylist)
- Implement approval workflows
- Set execution limits
- Handle permission and approval errors
"""

import asyncio

from scooper.exceptions import (
    ExecutionLimitExceededError,
    ToolApprovalDeniedError,
    ToolPermissionDeniedError,
)
from scooper.tools import Tool, ToolInput, ToolRegistry, ToolResult
from scooper.tools.permissions import (
    ApprovalRequest,
    ToolPermissionLevel,
    ToolPermissionPolicy,
)
from scooper.tools.safe_registry import SafeToolRegistry


class ReadFileTool(Tool):
    """A safe tool that reads files (no approval required)."""

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Reads content from a file"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.ALLOWED

    def validate_input(self, tool_input: ToolInput) -> bool:
        return hasattr(tool_input, "filename")

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        filename = tool_input.filename
        return ToolResult(
            success=True,
            output=f"Content of {filename}: [simulated file content]",
            metadata={"filename": filename, "permission": "allowed"},
        )


class WriteFileTool(Tool):
    """A tool that writes files (requires approval)."""

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Writes content to a file (requires approval)"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL

    def validate_input(self, tool_input: ToolInput) -> bool:
        return hasattr(tool_input, "filename") and hasattr(tool_input, "content")

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        filename = tool_input.filename
        content = tool_input.content
        return ToolResult(
            success=True,
            output=f"Successfully wrote to {filename}",
            metadata={
                "filename": filename,
                "bytes_written": len(str(content)),
                "permission": "requires_approval",
            },
        )


class DeleteFileTool(Tool):
    """A dangerous tool that deletes files (requires approval)."""

    @property
    def name(self) -> str:
        return "delete_file"

    @property
    def description(self) -> str:
        return "Deletes a file (requires approval)"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL

    def validate_input(self, tool_input: ToolInput) -> bool:
        return hasattr(tool_input, "filename")

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        filename = tool_input.filename
        return ToolResult(
            success=True,
            output=f"Successfully deleted {filename}",
            metadata={"filename": filename, "permission": "requires_approval"},
        )


class ExecuteCommandTool(Tool):
    """A very dangerous tool that executes system commands."""

    @property
    def name(self) -> str:
        return "execute_command"

    @property
    def description(self) -> str:
        return "Executes a system command"

    @property
    def permission_level(self) -> ToolPermissionLevel:
        return ToolPermissionLevel.REQUIRES_APPROVAL

    def validate_input(self, tool_input: ToolInput) -> bool:
        return hasattr(tool_input, "command")

    async def execute(self, tool_input: ToolInput) -> ToolResult:
        command = tool_input.command
        return ToolResult(
            success=True,
            output=f"Executed: {command}",
            metadata={"command": command},
        )


async def interactive_approval_callback(request: ApprovalRequest) -> bool:
    """Simulated approval callback that demonstrates the approval workflow.

    In a real application, this would:
    - Show a UI prompt to the user
    - Log the request for audit purposes
    - Check against a policy database
    - etc.
    """
    print("\n🔔 APPROVAL REQUIRED:")
    print(f"   Tool: {request.tool_name}")
    print(f"   Arguments: {request.arguments}")
    if request.session_id:
        print(f"   Session: {request.session_id}")

    # Simulate approval logic
    # For demo purposes, approve write but deny delete
    if request.tool_name == "write_file":
        print("   ✓ APPROVED (write operations allowed)")
        return True
    elif request.tool_name == "delete_file":
        print("   ✗ DENIED (delete operations not allowed)")
        return False
    elif request.tool_name == "execute_command":
        print("   ✗ DENIED (command execution not allowed)")
        return False
    else:
        # Default: approve
        print("   ✓ APPROVED")
        return True


async def main() -> None:
    """Run safe tool execution examples."""
    print("=" * 70)
    print("SCOOPER SAFE TOOL EXECUTION EXAMPLE")
    print("=" * 70)
    print()

    # Create base registry
    registry = ToolRegistry()
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(DeleteFileTool())
    registry.register(ExecuteCommandTool())

    print(f"✓ Registered {len(registry)} tools")
    print(f"  Available: {', '.join(registry.list_tools())}")
    print()

    # =========================================================================
    # Example 1: Basic allowlist enforcement
    # =========================================================================
    print("=" * 70)
    print("Example 1: Allowlist Enforcement")
    print("=" * 70)

    policy_allowlist = ToolPermissionPolicy(allowlist={"read_file", "write_file"})
    safe_registry_1 = SafeToolRegistry(registry, policy=policy_allowlist)

    print("\n→ Policy: Allowlist = {read_file, write_file}")

    # Allowed tool
    print("\n  Executing allowed tool (read_file):")
    try:
        result = await safe_registry_1.execute(
            "read_file", ToolInput(filename="data.txt")
        )
        print(f"    ✓ Success: {result.output}")
    except ToolPermissionDeniedError as e:
        print(f"    ✗ Denied: {e}")

    # Denied tool
    print("\n  Attempting denied tool (delete_file):")
    try:
        result = await safe_registry_1.execute(
            "delete_file", ToolInput(filename="data.txt")
        )
        print(f"    ✓ Success: {result.output}")
    except ToolPermissionDeniedError as e:
        print(f"    ✗ Denied: {e}")

    # =========================================================================
    # Example 2: Denylist enforcement
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 2: Denylist Enforcement")
    print("=" * 70)

    policy_denylist = ToolPermissionPolicy(
        denylist={"delete_file", "execute_command"}
    )
    safe_registry_2 = SafeToolRegistry(registry, policy=policy_denylist)

    print("\n→ Policy: Denylist = {delete_file, execute_command}")

    # Allowed tool
    print("\n  Executing allowed tool (read_file):")
    try:
        result = await safe_registry_2.execute(
            "read_file", ToolInput(filename="data.txt")
        )
        print(f"    ✓ Success: {result.output}")
    except ToolPermissionDeniedError as e:
        print(f"    ✗ Denied: {e}")

    # Denied tool
    print("\n  Attempting denied tool (execute_command):")
    try:
        result = await safe_registry_2.execute(
            "execute_command", ToolInput(command="rm -rf /")
        )
        print(f"    ✓ Success: {result.output}")
    except ToolPermissionDeniedError as e:
        print(f"    ✗ Denied: {e}")

    # =========================================================================
    # Example 3: Approval workflow
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 3: Approval Workflow")
    print("=" * 70)

    policy_approval = ToolPermissionPolicy(
        approval_callback=interactive_approval_callback
    )
    safe_registry_3 = SafeToolRegistry(
        registry, policy=policy_approval, session_id="demo-session-001"
    )

    print("\n→ Policy: Approval callback configured")

    # Tool that doesn't require approval
    print("\n  Executing tool without approval requirement (read_file):")
    result = await safe_registry_3.execute(
        "read_file", ToolInput(filename="data.txt")
    )
    print(f"    ✓ Executed without approval: {result.output}")

    # Tool requiring approval - approved
    print("\n  Executing tool with approval requirement (write_file):")
    try:
        result = await safe_registry_3.execute(
            "write_file", ToolInput(filename="output.txt", content="Hello World")
        )
        print(f"    ✓ Success after approval: {result.output}")
    except ToolApprovalDeniedError as e:
        print(f"    ✗ Approval denied: {e}")

    # Tool requiring approval - denied
    print("\n  Executing tool with approval requirement (delete_file):")
    try:
        result = await safe_registry_3.execute(
            "delete_file", ToolInput(filename="important.txt")
        )
        print(f"    ✓ Success after approval: {result.output}")
    except ToolApprovalDeniedError as e:
        print(f"    ✗ Approval denied: {e}")

    # =========================================================================
    # Example 4: Execution limits
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 4: Execution Limits")
    print("=" * 70)

    safe_registry_4 = SafeToolRegistry(registry, max_tool_calls_per_execution=3)

    print("\n→ Policy: Maximum 3 tool calls per execution")

    try:
        # Execute 3 tools successfully
        for i in range(1, 4):
            result = await safe_registry_4.execute(
                "read_file", ToolInput(filename=f"file{i}.txt")
            )
            print(f"\n  Call {i}/3: ✓ {result.output}")

        # Fourth call should fail
        print("\n  Attempting 4th call (exceeds limit):")
        result = await safe_registry_4.execute(
            "read_file", ToolInput(filename="file4.txt")
        )
        print(f"    ✓ Success: {result.output}")

    except ExecutionLimitExceededError as e:
        print(f"    ✗ Limit exceeded: {e}")

    print(f"\n  Total calls made: {safe_registry_4.tool_calls_made}")

    # Reset counter
    safe_registry_4.reset_call_count()
    print(f"  After reset: {safe_registry_4.tool_calls_made}")

    # =========================================================================
    # Example 5: Combined policies
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 5: Combined Policies")
    print("=" * 70)

    # Allowlist + denylist + approval + limits
    policy_combined = ToolPermissionPolicy(
        allowlist={"read_file", "write_file", "delete_file"},
        denylist={"execute_command"},  # Denylist overrides allowlist
        approval_callback=interactive_approval_callback,
    )

    safe_registry_5 = SafeToolRegistry(
        registry,
        policy=policy_combined,
        max_tool_calls_per_execution=5,
        session_id="demo-session-002",
    )

    print("\n→ Policy:")
    print("  - Allowlist: {read_file, write_file, delete_file}")
    print("  - Denylist: {execute_command}")
    print("  - Approval callback: enabled")
    print("  - Max calls: 5")

    test_cases = [
        ("read_file", {"filename": "data.txt"}, "allowed, no approval"),
        ("write_file", {"filename": "out.txt", "content": "test"}, "allowed, needs approval"),
        ("delete_file", {"filename": "temp.txt"}, "allowed, needs approval (denied)"),
        ("execute_command", {"command": "ls"}, "denied by denylist"),
    ]

    for tool_name, args, description in test_cases:
        print(f"\n  Testing {tool_name} ({description}):")
        try:
            result = await safe_registry_5.execute(tool_name, ToolInput(**args))
            print(f"    ✓ Success: {result.output}")
        except (ToolPermissionDeniedError, ToolApprovalDeniedError) as e:
            print(f"    ✗ Blocked: {e}")

    # =========================================================================
    # Example 6: Tool requiring approval without policy
    # =========================================================================
    print("\n" + "=" * 70)
    print("Example 6: Approval Required Without Policy (Fail Closed)")
    print("=" * 70)

    # No policy configured = no approval mechanism
    safe_registry_6 = SafeToolRegistry(registry)

    print("\n→ No policy configured (approval-required tools will fail)")

    # Safe tool works
    print("\n  Executing safe tool (read_file):")
    result = await safe_registry_6.execute(
        "read_file", ToolInput(filename="data.txt")
    )
    print(f"    ✓ Success: {result.output}")

    # Approval-required tool fails closed
    print("\n  Attempting approval-required tool (write_file):")
    try:
        result = await safe_registry_6.execute(
            "write_file", ToolInput(filename="test.txt", content="data")
        )
        print(f"    ✓ Success: {result.output}")
    except Exception as e:
        print(f"    ✗ Failed closed: {e}")

    print("\n" + "=" * 70)
    print("EXAMPLE COMPLETE")
    print("=" * 70)
    print("\nKey Takeaways:")
    print("  • Denylist always overrides allowlist")
    print("  • Approval-required tools fail closed without approval handler")
    print("  • Execution limits prevent runaway tool usage")
    print("  • All checks happen before tool execution (not controlled by model)")
    print("  • Permission errors can be caught and handled gracefully")


if __name__ == "__main__":
    asyncio.run(main())
