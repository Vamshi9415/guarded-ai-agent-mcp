# backend/agent/test/test_agent_scenarios.py
"""
Manual, end-to-end walkthrough of the guarded agent - not a pytest suite.
Makes real Gemini API calls and spawns the real local MCP server (plus
Context7 if CONTEXT7_API_KEY is set), so this costs a few API calls and
takes roughly 30-60 seconds to run, mostly due to one deliberate ~4s wait
in the approval-timeout scenario below.

Covers every outcome the system can produce, one example of each:
  - a plain reply with no tool call at all
  - a tool call allowed with no rule in its way      (list_records)
  - a tool call allowed only after a rewrite          (create_record)
  - a tool call that needs - and gets - approval      (update_record)
  - a tool call blocked outright                      (delete_record)
  - a tool call that needs approval and times out     (read_record)
  - two tool calls prompted by a single message
  - Context7 (skipped automatically if not configured)
  - Agent.reset() vs Agent.new_conversation()
  - hitting MAX_TOOL_TURNS
  - hitting a per-conversation token budget
  - ApprovalManager.reject(), called directly (no rule needed for this one)

Run from the project root:
    python backend/agent/test/test_agent_scenarios.py

Scenario order is deliberate, not arbitrary - see the comment above the
auto-approver task for why.
"""
import asyncio
import os
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = CURRENT_DIR.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

load_dotenv()

from backend.agent.agent import Agent
from backend.agent.tool_loop import ToolLoop
from backend.llm.gemini import GeminiClient
from backend.mcp.manager import MCPManager
from backend.mcp.registry import ToolRegistry
from backend.mcp.transport.stdio_transport import StdioTransport
from backend.mcp.transport.streamble_http_transport import StreamableHTTPTransport
from backend.policy.approvals import ApprovalManager
from backend.policy.engine import PolicyEngine
from backend.policy.models import (
    ArgumentConstraint,
    ConstraintType,
    ConversationBudget,
    PolicyRule,
    RuleAction,
    RuleType,
)
from backend.policy.store import InMemoryPolicyStore

LOCAL_SERVER_PATH = ROOT_DIR / "backend" / "mcp" / "server.py"


def section(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


async def ask(agent: Agent, prompt: str) -> None:
    """Sends one prompt and prints both the model's reply and any tool
    results produced along the way - the tool result text is what the
    guardrail actually said (e.g. "This tool call was blocked: ..."),
    which the model's own reply may only paraphrase."""
    print(f"\nyou> {prompt}")
    before = len(agent.messages)
    reply = await agent.chat(prompt)
    for msg in agent.messages[before:]:
        if msg.role == "tool":
            tag = "ERROR" if msg.is_error else "OK"
            print(f"   [tool:{tag}] {msg.name} -> {msg.content}")
    print(f"agent> {reply}")


async def auto_approver(approvals: ApprovalManager, store: InMemoryPolicyStore) -> None:
    """Background loop that approves whatever's pending, so the
    update_record scenario doesn't need a human watching the terminal.
    Must be cancelled before the read_record scenario runs, or it would
    approve that one too and the timeout demo would never trigger."""
    try:
        while True:
            for approval in await store.list_pending_approvals():
                print(f"   [auto-approver] approving {approval.tool_name} ({approval.id})")
                await approvals.approve(approval.id, resolved_by="test-admin", reason="auto-approved by test script")
            await asyncio.sleep(0.3)
    except asyncio.CancelledError:
        pass


async def build_manager() -> MCPManager:
    manager = MCPManager()
    manager.register(
        StdioTransport(name="local_crud", command=sys.executable, args=[str(LOCAL_SERVER_PATH)])
    )
    context7_key = os.getenv("CONTEXT7_API_KEY")
    if context7_key:
        manager.register(
            StreamableHTTPTransport(
                name="context7",
                url="https://mcp.context7.com/mcp",
                headers={"CONTEXT7_API_KEY": context7_key},
            )
        )
    await manager.connect_all()
    return manager


async def seed_rules(store: InMemoryPolicyStore) -> None:
    await store.create_rule(PolicyRule(
        name="block-delete-record",
        action=RuleAction.BLOCK,
        tool_pattern="delete_record",
        rule_type=RuleType.EXACT,
        priority=100,
        reason="delete_record is never allowed in this demo",
    ))
    await store.create_rule(PolicyRule(
        name="sandbox-create-record-path",
        action=RuleAction.ALLOW,
        tool_pattern="create_record",
        rule_type=RuleType.EXACT,
        priority=10,
        constraints=[
            ArgumentConstraint(
                field="storage_path",
                constraint_type=ConstraintType.PATH_PREFIX,
                value="/sandbox",
                allow_rewrite=True,
            )
        ],
    ))
    await store.create_rule(PolicyRule(
        name="approve-update-record",
        action=RuleAction.REQUIRE_APPROVAL,
        tool_pattern="update_record",
        rule_type=RuleType.EXACT,
        priority=10,
        approval_timeout_seconds=30,
    ))
    await store.create_rule(PolicyRule(
        name="approve-read-record-short-timeout",
        action=RuleAction.REQUIRE_APPROVAL,
        tool_pattern="read_record",
        rule_type=RuleType.EXACT,
        priority=10,
        approval_timeout_seconds=4,  # deliberately short - nothing approves this one
    ))


async def main() -> None:
    manager = await build_manager()
    registry = ToolRegistry(manager)
    await registry.discover()
    print(f"Discovered {registry.count} tools across {len(manager.sessions())} server(s).")

    llm = GeminiClient()
    store = InMemoryPolicyStore()
    await seed_rules(store)

    # Constructed explicitly and shared with the background auto-approver
    # below - see module docstring for why PolicyEngine must NOT build its
    # own separate ApprovalManager here.
    approvals = ApprovalManager(store)
    policy = PolicyEngine(store, approval_manager=approvals)

    tool_loop = ToolLoop(llm, registry, policy)
    agent = Agent(tool_loop)

    try:
        section("1. Plain conversation - no tool call at all")
        await ask(agent, "What's 17 times 24? Just answer, no need to look anything up.")

        section("2. Tool call, no rule in the way - list_records (ALLOWED)")
        await ask(agent, "What records currently exist in the database? List them all.")

        section("3. Tool call rewritten - create_record path traversal corrected")
        await ask(
            agent,
            "Create a new record with key 'user_5', name 'Eve', role 'Tester', "
            "and use the storage path '../../etc/evil' for it.",
        )

        section("4. Tool call requiring approval - update_record (auto-approved)")
        approver_task = asyncio.create_task(auto_approver(approvals, store))
        await ask(agent, "Please update the role for user_1 to 'SuperAdmin'.")
        approver_task.cancel()
        await asyncio.gather(approver_task, return_exceptions=True)

        section("5. Tool call blocked outright - delete_record")
        await ask(agent, "Please delete the record for user_2.")

        section("6. Tool call requiring approval, nobody answers - read_record TIMES OUT")
        print("   (waiting ~4s for an approval that will never come...)")
        await ask(agent, "Please show me the full details stored for user_1.")

        section("7. Two tool calls from one prompt")
        await ask(
            agent,
            "First list every record in the database, then create a new record "
            "with key 'user_6', name 'Grace', role 'Tester', storage path "
            "'/sandbox/data/grace'.",
        )

        if os.getenv("CONTEXT7_API_KEY"):
            section("8. Context7 (remote MCP server)")
            await ask(agent, "Use the documentation lookup tool to find information about the Python 'requests' library.")
        else:
            section("8. Context7 - SKIPPED (CONTEXT7_API_KEY not set)")

        section("9. reset() - same conversation_id, history wiped")
        before_id = agent.conversation_id
        agent.reset()
        print(f"   conversation_id unchanged: {agent.conversation_id == before_id}")
        await ask(agent, "Do you remember what I said about user_1 earlier?")

        section("10. new_conversation() - fresh id and history")
        new_id = agent.new_conversation()
        print(f"   new conversation_id: {new_id} (different from {before_id}: {new_id != before_id})")

        section("11. Hitting MAX_TOOL_TURNS")
        capped_loop = ToolLoop(llm, registry, policy, max_tool_turns=1)
        capped_agent = Agent(capped_loop)
        await ask(capped_agent, "List all the records currently in the database.")

        section("12. Hitting a per-conversation token budget")
        await store.set_budget(ConversationBudget(conversation_id="budget-demo", max_tokens=50))
        budget_agent = Agent(tool_loop, conversation_id="budget-demo")
        await ask(budget_agent, "What records exist in the database?")
        budget_state = await store.get_budget_state("budget-demo")
        print(f"   recorded usage for budget-demo: {budget_state.total_tokens} tokens")

        section("13. ApprovalManager.reject() - called directly, no rule needed")
        pending = await approvals.submit_request(
            conversation_id="rejection-demo",
            tool_name="manual_review_demo",
            arguments={"example": "value"},
            matched_rule_id="manual-demo",
            timeout_seconds=30,
        )
        waiter = asyncio.create_task(approvals.wait_for_resolution(pending.id))
        await asyncio.sleep(0.2)
        await approvals.reject(pending.id, resolved_by="test-admin", reason="manual rejection demo")
        resolved = await waiter
        print(f"   resolved status: {resolved.status.value}, reason: {resolved.resolution_reason}")

        section("Policy decision log (everything above, in order)")
        for log in await store.get_logs():
            print(
                f"   [{log.timestamp.isoformat(timespec='seconds')}] "
                f"{log.conversation_id} | {log.tool_name} -> {log.outcome.value} "
                f"({log.execution_time_ms:.1f}ms) {('| ' + log.reason) if log.reason else ''}"
            )

    finally:
        await manager.disconnect_all()
        await llm.close()


if __name__ == "__main__":
    asyncio.run(main())