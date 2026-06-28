from contextlib import AsyncExitStack

from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from .base import MCPTransport


class StreamableHTTPTransport(MCPTransport):

    def __init__(
        self,
        name: str,
        url: str,
        headers: dict | None = None,
    ):
        super().__init__(name)

        self.url = url
        self.headers = headers or {}

        self.stack = AsyncExitStack()

    async def connect(self, stack: AsyncExitStack | None = None):
        if stack is not None:
            self.stack = stack

        read_stream, write_stream, _ = (
            await self.stack.enter_async_context(
                streamablehttp_client(
                    self.url,
                    headers=self.headers,
                )
            )
        )

        self.session = await self.stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream,
            )
        )

        await self.session.initialize()

        return self.session

    async def disconnect(self):
        if self.stack is not None:
            await self.stack.aclose()
            self.stack = None