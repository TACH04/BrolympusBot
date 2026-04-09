---
name: Web Search & Investigation
description: Protocols for thorough web searching and deep investigation. Use for factual lookups, deep dives, and comprehensive research tasks.
---

# Web Search & Investigation Skill

This skill provides a rigorous protocol for gathering and verifying information from the web. Follow these guidelines to ensure your answers are accurate, up-to-date, and comprehensive.

## Tool Hierarchy

You have three main tools for investigation. Choose based on the complexity of the task:

1.  **`search_web`**: Use for quick facts, current news headlines, or finding specific URLs.
2.  **`scrape_url`**: Use when you have a specific, relevant source (e.g., a documentation page, a deep-dive article) that you need to read in its entirety to extract detailed information.
3.  **`deep_research`**: Use for complex questions that require synthesizing data from multiple sources, broad exploration of a topic, or when the user explicitly asks for a "comprehensive report".

## The Investigation Protocol

### 1. Be Thorough (The Multi-Query Strategy)
Never rely on a single search query if the topic has any complexity.
- If the first query doesn't yield definitive results, **rephrase and try again**.
- Use "search operators" if needed (though plain queries usually work well).
- If one source seems biased or incomplete, search for a second opinion.

### 2. Follow the Trail (Deep Reading)
`search_web` only gives you snippets.
- If a snippet looks promising but doesn't have the full answer, **use `scrape_url`** to read the full content of that page.
- Do not guess or hallucinate details that are missing from snippets.

### 3. Synthesis and Quality
- Cross-reference facts between different sources.
- Check the "freshness" of the information (especially for technology or news).
- If you find conflicting information, present both views or look for a tie-breaking source.

## When to use Simple vs Deep Research

- **Simple Search (`search_web`)**: "What time is the game tonight?", "Who is the CEO of Apple?", "Current price of Bitcoin".
- **Deep Research sub-agent (`deep_research`)**: "Compare the pros and cons of three different LLM providers", "Research the historical development of the Renaissance in Italy", "Give me a comprehensive report on the current state of fusion energy".

## Reporting to the User
- Always cite your findings if possible (e.g., "According to [Source Name]...").
- If you can't find an answer after thorough searching, be honest about it. Do not invent facts.
