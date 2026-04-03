# CalGuy: AI Calendar Assistant

CalGuy is a locally-powered AI calendar management assistant that leverages **Ollama** and the **Google Calendar API**. It offers a web interface and a CLI to manage your schedule with natural language.

## 🚀 Features

- **Natural Language Interaction**: Create, delete, and list calendar events using conversational prompts.
- **Local Privacy**: Uses Ollama to run large language models locally on your machine.
- **Multi-Interface**: Supports both a CLI and a modern Flask-based web interface.
- **Smart Context**: Maintains history and context for complex scheduling tasks.

## 📋 Prerequisites

- [Ollama](https://ollama.com/) (running locally)
- [Python 3.12+](https://www.python.org/downloads/)
- Google Cloud Platform Project with Calendar API enabled

## ⚙️ Setup

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/calguy.git
cd calguy
```

### 2. Create a Virtual Environment
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the example environment file and fill in your values:
```bash
cp .env_example .env
```
Key variables:
- `OLLAMA_MODEL`: The model name in Ollama (e.g., `qwen2.5-coder:32b`).
- `SERVER_TIMEZONE`: Your local timezone (e.g., `America/New_York`).

### 5. Google Calendar API Setup
- Create a project in the [Google Cloud Console](https://console.cloud.google.com/).
- Enable the **Google Calendar API**.
- Create **OAuth 2.0 Credentials** (Desktop App).
- Download the JSON file, rename it to `client_secret.json`, and place it in the project root.

## 🏃 Usage

### Running the Web Interface
```bash
python app.py
```
Then navigate to `http://127.0.0.1:5000` in your browser.

### Running the CLI
```bash
python agent.py
```

## 🛠️ Project Structure

- `agent.py`: Main logic for the AI agent turn-taking and Ollama integration.
- `app.py`: Flask server for the web interface.
- `google_calendar.py`: Google Calendar API wrapper.
- `tools.py`: Tool definitions for the AI to interact with the calendar.
- `static/`: CSS and Client-side JS.
- `templates/`: HTML templates.

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
