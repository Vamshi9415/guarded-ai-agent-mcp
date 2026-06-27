# backend/agent/agent.py
"""
Agent: conversation-state owner.

The Agent is the user-facing entry point for one guarded conversation.
It is deliberately the most ignorant class in the system - it does not
know an LLM provider exists, that tools are executed through MCP, or
that a policy engine is gating any of it. All of that lives behind the
single ToolLoop dependency it's handed at construction time. That's what
lets the same Agent be reused, unchanged, from a FastAPI route handler,
a CLI REPL, a test harness, or anything else that can await a method and
print a string.

What the Agent actually owns:
    - conversation_id   a stable identifier for this conversation,
                         threaded through to PolicyEngine so budgets,
                         approvals, and logs are scoped correctly
    - messages           the conversation history, as a list[Message]
    - system_prompt       the one message that seeds that history

What it explicitly delegates, and to what:
    - "what should happen next given this history" -> ToolLoop.run()
    - which LLM, which tools, which guardrails are involved -> whatever
      ToolLoop was itself constructed with, none of which this module
      ever imports

Note on ToolLoop's StopReason: this module deliberately does not import
it. _extract_reply below keys its fallback wording off
result.stop_reason.value - a plain str - rather than the StopReason enum
type itself, so Agent's only coupling to ToolLoop's internals is a
duck-typed attribute access, the same pattern used at every other
cross-module boundary in this codebase (see UsageLike in
policy/models.py). A future StopReason this dict doesn't recognize falls
through to the generic fallback rather than breaking.
"""
from __future__ import annotations

import uuid

from ..llm.base import Message
from .tool_loop import ToolLoop, ToolLoopResult

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful assistant with access to a set of tools. Use "
    "tools when they would help answer the user's request, and respond "
    "directly when they would not."
)

# Returned to the caller instead of None or an empty string in the cases
# where a turn ends with no assistant text at all - see _extract_reply.
# Keyed by the *string value* of StopReason members (StopReason itself
# is never imported here - see module docstring) so the message actually
# explains what happened, rather than a single generic "something went
# wrong" for every case.
_NO_TEXT_FALLBACK_BY_STOP_REASON_VALUE: dict[str, str] = {
    "max_turns_reached": (
        "I wasn't able to finish this within the allowed number of tool "
        "calls. Could you narrow down what you'd like me to do?"
    ),
    "budget_exceeded": (
        "This conversation has reached its token budget, so I can't "
        "continue right now."
    ),
}
_GENERIC_NO_TEXT_FALLBACK = "I don't have a response for that right now."


class Agent:
    """Owns one guarded conversation's identity and history; delegates
    everything about *how* a reply gets produced to an injected
    ToolLoop. Holds no reference to any LLM client, MCP transport,
    ToolRegistry, or PolicyEngine - those are ToolLoop's concerns, and
    ToolLoop is the only collaborator this class knows about.

    Not safe for concurrent calls against one instance: chat() reads
    self.messages, awaits the tool loop, then writes self.messages, with
    no lock around that read-modify-write. Two overlapping chat() calls
    on the same Agent could interleave and corrupt history. Each
    conversation should have exactly one Agent, with callers awaiting
    one chat() call to completion before starting the next for that
    conversation - an Agent is a per-conversation object, never a shared
    concurrently-hit singleton, consistent with the no-singleton,
    no-global-state stance the rest of this codebase already takes.
    """

    def __init__(
        self,
        tool_loop: ToolLoop,
        conversation_id: str | None = None,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ) -> None:
        """
        Args:
            tool_loop: The injected ToolLoop this Agent delegates every
                reply to. The Agent never constructs its own - whoever
                builds an Agent decides which LLM client, ToolRegistry,
                and PolicyEngine that ToolLoop is wired to.
            conversation_id: Stable id for this conversation, threaded
                through to ToolLoop.run() (and from there into
                PolicyEngine's budget/approval/log scoping). Generated as
                a fresh canonical UUID4 string if not supplied - the same
                form backend.policy.models uses for PolicyRule.id and
                ApprovalRequest.id, the two existing identifiers closest
                in kind to this one (long-lived, logged, displayed) as
                opposed to ToolCall.id's deliberately short, ephemeral
                per-call form.
            system_prompt: Seeds the conversation history as its first
                message. Stored so reset() can restore exactly this
                prompt later, rather than only being usable once at
                construction time.
        """
        self._tool_loop = tool_loop
        self._conversation_id = conversation_id or str(uuid.uuid4())
        self._system_prompt = system_prompt
        self._messages: list[Message] = [Message.system(system_prompt)]

    # ------------------------------------------------------------------
    # Public read-only state
    # ------------------------------------------------------------------

    @property
    def conversation_id(self) -> str:
        """The stable id for this conversation. Fixed for the lifetime
        of this Agent instance - reset() clears history, but never
        changes this; new_conversation() is the one that does."""
        return self._conversation_id

    @property
    def messages(self) -> tuple[Message, ...]:
        """A snapshot of the current history, oldest first, as a tuple.

        A tuple specifically (not a list) to signal the read-only nature
        of this snapshot at the type level, not just provide it -
        mutating what this returns has no effect on Agent's actual state
        either way, but a tuple makes that intent visible without
        needing a docstring to explain it. Individual Message objects
        within it are not deep-copied; every module in this codebase
        already treats Message as effectively immutable (built fresh via
        Message.user()/.assistant()/.tool_result() rather than mutated in
        place), so a shallow copy here is consistent with that existing
        discipline, not a gap.
        """
        return tuple(self._messages)

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    async def chat(self, user_input: str) -> str:
        """Advances the conversation by one user turn and returns the
        assistant's reply text.

        The next-turn history is built as a new list - self._messages
        plus the new user message - without mutating self._messages (or
        anything a caller might be holding a reference to via the
        messages property) until ToolLoop.run() has actually returned
        successfully. Only then does the result become this Agent's new
        history. If ToolLoop.run() raises, self._messages is left exactly
        as it was before this call: a failed turn never leaves the
        conversation half-updated, and the caller can safely retry
        chat() with the same input.

        Args:
            user_input: The user's message for this turn.

        Returns:
            The assistant's reply text. Never None - see
            _extract_reply for what's returned on the turns where the
            model itself produced no closing text (hitting the tool-turn
            cap, or the token budget running out mid-turn).
        """
        pending_history = self._messages + [Message.user(user_input)]

        result = await self._tool_loop.run(pending_history, self._conversation_id)

        self._messages = result.messages
        return self._extract_reply(result)

    def reset(self) -> None:
        """Clears history back to just the system prompt this Agent was
        constructed with.

        conversation_id is deliberately left unchanged: clearing what
        context is shown to the model is a different action from
        starting an entirely new conversation (new_conversation(), just
        below) - a reset conversation should still resolve to the same
        budget and rule scope it had before, not a fresh one.
        """
        self._messages = [Message.system(self._system_prompt)]

    def new_conversation(self) -> str:
        """Starts an entirely new conversation on this same Agent
        instance: a freshly generated conversation_id, plus history
        reset back to just the system prompt - the combination reset()
        alone deliberately doesn't provide (see its docstring). For
        cases where the old budget, approval history, and rule scope
        genuinely should not carry over - a CLI's "start over" command,
        or a dashboard's "new chat" action.

        Returns:
            The newly generated conversation_id, so callers that need to
            display or persist it immediately don't have to separately
            read the conversation_id property right after calling this.
        """
        self._conversation_id = str(uuid.uuid4())
        self.reset()
        return self._conversation_id

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_reply(result: ToolLoopResult) -> str:
        """Converts a ToolLoopResult into the str chat() promises.

        final_text is Optional on ToolLoopResult by design - None
        whenever a turn ends without the model producing closing text
        (hitting the tool-turn cap, or the token budget running out
        before any trailing text was generated). This is the one place
        that gap is resolved, with wording specific to *why* there's
        nothing to show, rather than chat() returning None or raising
        for what is, for a guarded agent, an entirely expected outcome.
        """
        if result.final_text is not None:
            return result.final_text

        return _NO_TEXT_FALLBACK_BY_STOP_REASON_VALUE.get(
            result.stop_reason.value, _GENERIC_NO_TEXT_FALLBACK
        )