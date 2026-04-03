import os
import json
import datetime
from dotenv import load_dotenv
import ollama

from tools import OLLAMA_TOOLS, execute_tool

load_dotenv()
MODEL = os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
SERVER_TIMEZONE = os.getenv("SERVER_TIMEZONE", "America/Los_Angeles")

def get_system_prompt():
    """Generates a dynamic system prompt with the current time and context."""
    now = datetime.datetime.now()
    return f"""You are a helpful, professional AI calendar assistant.
You can manage the user's Google Calendar using the tools provided.

Current Context:
- Current Date and Time: {now.strftime('%A, %Y-%m-%d %H:%M:%S')}
- Timezone: {SERVER_TIMEZONE}

When scheduling events, always confirm the time and duration. If a year is not specified, assume the current year or the next occurrence of that date.
When responding after a tool call, be concise and let the user know what was done.
"""

def estimate_tokens(text):
    if not text:
        return 0
    return len(str(text)) // 4


class CalendarAgent:
    def __init__(self):
        self.model = MODEL
        self.reset()
        
    def reset(self):
        prompt = get_system_prompt()
        self.messages = [
            {"role": "system", "content": prompt, "tokens": estimate_tokens(prompt)}
        ]
        
    def get_history(self):
        return self.messages
        
    def chat_step(self, user_input=None):
        """
        Takes user input, appends to history, and processes one turn of Ollama.
        Yields status updates and intermediate results to the caller (useful for UI).
        """
        if user_input:
            tokens = estimate_tokens(user_input)
            self.messages.append({"role": "user", "content": user_input, "tokens": tokens})
            yield {"type": "status", "content": "Assistant is thinking...", "tokens": estimate_tokens("Assistant is thinking...")}
            
        try:
            MAX_TURNS = 10
            turn_count = 0
            
            while turn_count < MAX_TURNS:
                response = ollama.chat(
                    model=self.model,
                    messages=self.messages,
                    tools=OLLAMA_TOOLS
                )
                
                msg = response.get('message', {})
                if not isinstance(msg, dict) and hasattr(msg, 'model_dump'):
                    msg = msg.model_dump()
                
                msg['tokens'] = estimate_tokens(msg.get('content', ''))
                if msg.get('tool_calls'):
                    msg['tokens'] += estimate_tokens(str(msg['tool_calls']))
                    
                self.messages.append(msg)
                
                # Check for tool invocations
                if msg.get('tool_calls'):
                    for tool_call in msg['tool_calls']:
                        tool_name = tool_call['function']['name']
                        tool_args = tool_call['function']['arguments']
                        
                        yield {
                            "type": "tool_call",
                            "tool": tool_name,
                            "args": tool_args,
                            "tokens": estimate_tokens(tool_name) + estimate_tokens(str(tool_args))
                        }
                        
                        tool_result = execute_tool(tool_name, tool_args)
                        result_tokens = estimate_tokens(tool_result)
                        
                        self.messages.append({
                            "role": "tool",
                            "name": tool_name,
                            "content": str(tool_result),
                            "tokens": result_tokens
                        })
                        
                        yield {
                            "type": "tool_result",
                            "tool": tool_name,
                            "result": tool_result,
                            "tokens": result_tokens
                        }
                        
                    yield {"type": "status", "content": "Assistant is processing tool results...", "tokens": estimate_tokens("Assistant is processing tool results...")}
                    turn_count += 1
                else:
                    yield {"type": "message", "content": msg.get('content'), "tokens": msg['tokens']}
                    break
                    
            if turn_count >= MAX_TURNS:
                yield {"type": "error", "content": f"Reached maximum number of tool turns ({MAX_TURNS})."}
                
        except Exception as e:
            yield {"type": "error", "content": str(e)}

def cli_chat_loop():
    print(f"Starting Calendar LLM Harness (Model: {MODEL})")
    print("Type 'quit' or 'exit' to stop.\n")
    
    agent = CalendarAgent()
    
    while True:
        try:
            user_input = input("You> ").strip()
            if not user_input:
                continue
                
            if user_input.lower() in ['quit', 'exit']:
                print("Goodbye!")
                break
                
            for event in agent.chat_step(user_input):
                if event['type'] == 'status':
                    print(event['content'])
                elif event['type'] == 'tool_call':
                    print(f"-> Calling Tool: {event['tool']} with {event['args']}")
                elif event['type'] == 'tool_result':
                    print(f"<- Tool Result: {event['result']}")
                elif event['type'] == 'message':
                    print(f"\nAssistant> {event['content']}\n")
                elif event['type'] == 'error':
                    print(f"\n[ERROR] {event['content']}\n")
                    
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break

if __name__ == "__main__":
    cli_chat_loop()
