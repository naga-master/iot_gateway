# Central event handling system
import asyncio
from typing import Dict, Any

# Event Manager is the central nervous system
class EventManager:
    def __init__(self):
        # Stores callbacks for each event type
        self.subscribers = {}
        # Queue for async event processing
        self.event_queue = asyncio.Queue()

    async def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        # When an event is published:
        await self.event_queue.put((event_type, data))
        # Example: Device command event
        # event_type = "device.command"
        # data = {"device_id": "bulb1", "command": "TURN_ON"}
        
    async def subscribe(self, event_type: str, callback) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        # {"device.command": handle_command_event(function to handle the bulb command)}
        self.subscribers[event_type].append(callback)

    async def process_events(self) -> None:
        while True:
            # Continuously process events from queue
            event_type, data = await self.event_queue.get()
            # Call all subscribers for this event type
            if event_type in self.subscribers:
                for callback in self.subscribers[event_type]:
                    await callback(data)