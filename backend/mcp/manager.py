from .transport.base import MCPTransport


class MCPManager:

    def __init__(self):
        self.transports = {}

    def register(self, transport: MCPTransport):
        self.transports[transport.name] = transport

    async def connect_all(self):

        for transport in self.transports.values():

            print(f"Connecting -> {transport.name}")

            await transport.connect()

            print(f"Connected -> {transport.name}")

    async def disconnect_all(self):

        for transport in self.transports.values():
            await transport.disconnect()

    def sessions(self):
        return {
            name: transport.session
            for name, transport in self.transports.items()
        }

    def get_transport(self, name):
        return self.transports[name]