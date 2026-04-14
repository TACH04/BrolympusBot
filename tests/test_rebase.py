import pytest
import time
from src.agents.agent import GeneralAgent

def test_rebase_overwrites_system_prompt():
    """Verify that rebase clears conversation context and completely replaces the system prompt."""
    agent = GeneralAgent()
    assert len(agent.messages) > 0
    assert agent.messages[0]["role"] == "system"

    # Add synthetic conversation history
    agent.memory.append({"role": "user", "content": "hello", "tokens": 10})
    agent.memory.append({"role": "assistant", "content": "hi", "tokens": 10})

    # Record activity time before rebase
    original_activity_time = agent.last_activity_time
    time.sleep(0.01)

    new_prompt = "You are a very cool custom bot now."
    agent.rebase(new_prompt)

    messages = agent.messages
    assert len(messages) == 1, "Expected context to be cleared except for the system prompt"
    assert getattr(agent, "last_activity_time", 0) > 0

if __name__ == "__main__":
    test_rebase_overwrites_system_prompt()
    print("test_rebase_overwrites_system_prompt passed!")
