# Infrastructure Setup

CalGuy requires several local services to be running to provide its full suite of capabilities. This guide covers the setup of the **Ollama**, **SearXNG**, and **Firecrawl** dependencies.

## 1. Ollama (AI Engine)

The agent runs entirely on local LLMs.

*   **Installation**: Download and install from [ollama.com](https://ollama.com).
*   **Recommended Model**: `qwen2.5-coder:32b` or similar high-capacity models with tool-calling capabilities.
*   **Pulling the Model**:
    ```bash
    ollama pull qwen2.5-coder:32b
    ```
*   **Configuration**: Ensure `OLLAMA_NUM_CTX` in your `.env` is set to at least `32768` to support long research transcripts.

---

## 2. SearXNG (Search Aggregation)

Used for the `search_web` tool. It provides a privacy-friendly, JSON-based search API.

*   **Setup via Docker**:
    The simplest way is to use the official Docker image. 
    ```bash
    docker run -d -p 8080:8080 searxng/searxng:latest
    ```
*   **API Configuration**: In your SearXNG `settings.yml`, ensure the `json` format is enabled:
    ```yaml
    search:
      formats:
        - html
        - json
    ```
*   **Connecting**: Set `SEARXNG_URL=http://localhost:8080` in your `.env`.

---

## 3. Firecrawl (Web Scraping)

Used for the `scrape_url` tool to convert Javascript-heavy websites into clean Markdown.

*   **Setup via Docker (Self-hosted)**:
    Firecrawl provides a self-hosting guide in their GitHub repository. Generally, it consists of several microservices (playwright, redis, api).
*   **Connecting**: Set `FIRECRAWL_URL=http://localhost:3002` in your `.env`.
*   **Cloud Version**: If you use the hosted version at firecrawl.dev, update the `.env`:
    ```env
    FIRECRAWL_URL=https://api.firecrawl.dev
    FIRECRAWL_API_KEY=your_apiKey_here
    ```

---

## 4. Google Calendar API

1.  Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
2.  Enable the **Google Calendar API**.
3.  Create an **OAuth 2.0 Client ID** (Desktop Application).
4.  Download the JSON credentials and path them in your `.env` as `CREDENTIALS_FILE`.
5.  On first run, the agent will prompt you to follow a link to authorize the application. This creates a `token.json` file for subsequent runs.
