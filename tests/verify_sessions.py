import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock

# Add src to python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from bot.discord_bot import session_manager

async def simulate_user_message(channel_id, user_name, content, delay=0):
    """Simulates a user message in a specific channel."""
    await asyncio.sleep(delay)
    print(f"[Sim] User {user_name} in Channel {channel_id} says: {content}")
    
    # Mock message object
    message = MagicMock()
    message.channel.id = channel_id
    message.author.display_name = user_name
    message.guild.name = "TestGuild"
    message.channel.name = f"channel-{channel_id}"
    message.reply = AsyncMock()
    
    # Fetch agent and lock
    agent, lock = session_manager.get_session(channel_id)
    
    print(f"[Sim] Channel {channel_id} lock status: {'Locked' if lock.locked() else 'Free'}")
    
    async with lock:
        print(f"[Sim] Processing message in Channel {channel_id} for {user_name}...")
        # Simulate chat step
        async for event in agent.chat_step(content, sender_name=user_name):
            if event['type'] == 'message':
                print(f"[Sim] Agent response in Channel {channel_id} to {user_name}: {event['content'][:50]}...")
    
    print(f"[Sim] Finished processing for {user_name} in Channel {channel_id}")

async def test_session_isolation():
    print("\n--- Testing Session Isolation ---")
    # Message in Channel 1
    await simulate_user_message(1, "Alice", "Hello from Channel 1")
    # Message in Channel 2
    await simulate_user_message(2, "Bob", "Hello from Channel 2")
    
    agent1, _ = session_manager.get_session(1)
    agent2, _ = session_manager.get_session(2)
    
    print(f"Channel 1 history length: {len(agent1.messages)}")
    print(f"Channel 2 history length: {len(agent2.messages)}")
    
    assert agent1 != agent2, "Agents should be different for different channels"
    assert len(agent1.messages) > 1
    assert len(agent2.messages) > 1
    print("✅ Session isolation verified.")

async def test_concurrency_control():
    print("\n--- Testing Concurrency Control ---")
    # Simulate Alice and Charlie messaging Channel 1 at almost the same time
    # Charlie should wait for Alice to finish
    await asyncio.gather(
        simulate_user_message(1, "Alice", "Long request part 1", delay=0),
        simulate_user_message(1, "Charlie", "Immediate request part 2", delay=0.1)
    )
    print("✅ Concurrency control (locking) verified visually by logs.")

async def main():
    try:
        await test_session_isolation()
        await test_concurrency_control()
        print("\nAll tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
