# Memory & Context Management

CalGuy handles long-term conversations and large tool outputs through a specialized `MemoryManager`. This ensures that the AI stays within the token limits of the local **Ollama** models while retaining essential context.

## 1. Token Thresholds

The system monitors tokens in real-time. By default, it uses the following targets:
*   **Context Window**: 32,768 tokens (`OLLAMA_NUM_CTX`).
*   **Compression Trigger**: 80% of the window (approx. 26,000 tokens).
*   **Safety Tail**: The last **10 messages** are always preserved as raw text to maintain immediate conversation flow.

---

## 2. Tool Result Pruning

To prevent massive data dumps (like a year's worth of calendar events) from instantly "blowing up" the context window, the system prunes tool outputs:
*   **Standard Tools**: Truncated after **12,000 characters**.
*   **Research Tools** (`scrape_url`): Allowed up to **64,000+ characters** (depending on context window) before pruning, as research requires more density.
*   **Notification**: When a result is pruned, the agent receives a note: `[Tool result from 'tool_name' was truncated — X chars → Y shown]`.

---

## 3. Sub-Agent Briefing

When a **Research Sub-Agent** is spawned, it doesn't receive the entire chat history (which would be redundant and expensive). Instead, the `MemoryManager` performs a **Briefing**:
1.  The system analyzes the last 10 messages.
2.  An LLM extracts **Active Goals**, **Constraints** (dates, timezones, preferences), and **Key Entities**.
3.  The sub-agent receives this 2-3 sentence "Brief" as its starting context.

---

## 4. Recursive Compression

When the 80% token threshold is crossed, the system performs **Automatic History Compression**:

### The Compression Layout
After compression, the message list is reconstructed as follows:
1.  **System Prompt**: Anchored at the start.
2.  **Memory Summary Block**: A dense, factual summary of all previous turns.
3.  **Raw Recent Tail**: The last 10 messages kept in their original form.

### The Summarization Prompt
The system uses an "Expert Context Compressor" prompt that instructs the LLM to:
*   Retain specific dates, names, and actionable details.
*   Omit pleasantries and redundant chatter.
*   Integrate previous summaries into the new one (Recursive Summarization).

---

## 5. Token Estimation
Since local models don't always expose a tokenizer API easily, CalGuy uses a rough but safe estimate: **1 token ≈ 4 characters**. This conservative estimate helps prevent unexpected overflows.
