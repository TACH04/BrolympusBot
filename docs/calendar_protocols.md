# Calendar Management Protocols

CalGuy follows strict safety protocols to ensure that events are scheduled accurately and that date "hallucinations" (common in LLMs) are minimized.

## 1. Mandatory Date Verification

The bot is strictly instructed to follow the **Date Verification Protocol**:
*   **The Rule**: Whenever a user specifies a relative date (e.g., "next Friday," "tomorrow afternoon," or "next weekend"), the agent **MUST** call the `verify_date` tool before calling `create_event`.
*   **The Purpose**: LLMs often lose track of the current day of the week or calculate the day-of-month incorrectly. `verify_date` runs on the server's system clock to confirm exactly what day of the week a YYYY-MM-DD string falls on.
*   **Agent Logic**:
    1.  User: "Schedule a meeting for next Tuesday."
    2.  Agent: Calculates "Next Tuesday" is 2026-04-14.
    3.  Agent: Calls `verify_date(date_string="2026-04-14")`.
    4.  Result: "The date 2026-04-14 falls on a Tuesday."
    5.  Agent: Proceeds to `create_event`.

---

## 2. Timezone Management

All events are scheduled relative to the server's timezone settings.
*   **Setting**: Defined by `SERVER_TIMEZONE` in the `.env` file (e.g., `America/Los_Angeles`).
*   **ISO 8601**: The system expects and provides times in ISO 8601 format (`YYYY-MM-DDTHH:MM:SS`).
*   **Manual Override**: If a user specifies a different timezone (e.g., "3 PM EST"), the agent is responsible for converting that into the server's local time before submission to the tool.

---

## 3. Event CRUD Operations

### Listing Events
The `list_upcoming_events` tool returns the next 20 events. It includes the **Event ID**, which is required for any further modifications.

### Creating Events
Requires:
*   **Summary** (Title)
*   **Start Time** (ISO 8601)
*   **End Time** (ISO 8601)
*   **Description** (Optional)

### Editing Events (The Deletion Logic)
CalGuy does **not** use a direct "Edit" or "Modify" tool. To change an event:
1.  The agent calls `list_upcoming_events` to find the correct `event_id`.
2.  The agent calls `delete_event(event_id=...)`.
3.  The agent calls `create_event` with the updated details.
*Reasoning*: This ensures that the agent doesn't partially update an event and leave inconsistent state in the Google Calendar.

---

## 4. Troubleshooting Date Issues

If the bot keeps "hallucinating" the wrong date:
1.  Check the `Current Date and Time` injected into the system prompt (found in `agent.py`).
2.  Ensure `SERVER_TIMEZONE` is correctly set in your environment.
3.  Instruct the user to provide an explicit date (e.g., "April 10th") instead of a relative one.
