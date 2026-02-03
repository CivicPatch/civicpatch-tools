import asyncio
from typing import Dict, List

class MemoryPubSubService:
    def __init__(self):
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}

    def subscribe(self, key: str) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers.setdefault(key, []).append(queue)
        return queue

    def unsubscribe(self, key: str, queue: asyncio.Queue):
        if key in self.subscribers:
            self.subscribers[key].remove(queue)
            if not self.subscribers[key]:
                del self.subscribers[key]

    async def publish(self, key: str, message: str):
        for queue in self.subscribers.get(key, []):
            await queue.put(message)

memory_pubsub = MemoryPubSubService()