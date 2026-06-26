from contextlib import AsyncExitStack

from .transport.base import MCPTransport


class MCPManager:

    def __init__(self):
        self.transports = {}
        self.stack = None

    def register(self, transport: MCPTransport):
        self.transports[transport.name] = transport

    async def connect_all(self):

        self.stack = AsyncExitStack()

        for transport in self.transports.values():

            print(f"Connecting -> {transport.name}")

            await transport.connect(stack=self.stack)

            print(f"Connected -> {transport.name}")

    async def disconnect_all(self):

        if self.stack is not None:
            await self.stack.aclose()
            self.stack = None

        for transport in self.transports.values():
            transport.session = None

    def sessions(self):
        return {
            name: transport.session
            for name, transport in self.transports.items()
        }

    def get_transport(self, name):
        return self.transports[name]