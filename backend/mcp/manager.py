from contextlib import AsyncExitStack
import logging

from .transport.base import MCPTransport

logger = logging.getLogger(__name__)


class MCPManager:
    def __init__(self):
        self.transports: dict[str, MCPTransport] = {}
        self.stack: AsyncExitStack | None = None
        self.failed_transports: dict[str, str] = {}

    def register(self, transport: MCPTransport) -> None:
        self.transports[transport.name] = transport
        logger.debug("Registered MCP transport: %s (%s)", transport.name, transport.__class__.__name__)

    async def connect_all(self) -> None:
        logger.info("Starting MCP transport connection sequence for %d transport(s).", len(self.transports))

        self.stack = AsyncExitStack()
        self.failed_transports = {}

        for name, transport in self.transports.items():
            logger.debug("Preparing to connect transport '%s'. Existing session=%s", name, transport.session is not None)

            try:
                logger.info("Connecting MCP transport: %s", name)
                await transport.connect(stack=self.stack)
                logger.info("Connected MCP transport: %s", name)
                logger.debug(
                    "Transport '%s' connected successfully. session=%r",
                    name,
                    transport.session,
                )
            except Exception as exc:
                logger.exception("Failed to connect MCP transport: %s", name)
                transport.session = None
                self.failed_transports[name] = f"{type(exc).__name__}: {exc}"

        connected = self.sessions()
        logger.info(
            "MCP connection sequence finished. connected=%d failed=%d",
            len(connected),
            len(self.failed_transports),
        )

        if self.failed_transports:
            logger.warning("Failed MCP transports: %s", self.failed_transports)

        if not connected:
            raise RuntimeError("No MCP transports connected successfully.")

    async def disconnect_all(self) -> None:
        logger.info("Disconnecting all MCP transports.")

        if self.stack is not None:
            try:
                await self.stack.aclose()
                logger.debug("AsyncExitStack closed successfully.")
            finally:
                self.stack = None

        for name, transport in self.transports.items():
            if transport.session is not None:
                logger.debug("Clearing session for transport '%s'.", name)
            transport.session = None

        logger.info("All MCP transport sessions cleared.")

    def sessions(self) -> dict[str, object]:
        connected = {
            name: transport.session
            for name, transport in self.transports.items()
            if transport.session is not None
        }
        logger.debug(
            "Returning connected MCP sessions: %s",
            list(connected.keys()),
        )
        return connected

    def get_transport(self, name: str) -> MCPTransport:
        logger.debug("Fetching MCP transport by name: %s", name)
        return self.transports[name]