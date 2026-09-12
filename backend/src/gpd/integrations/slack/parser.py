import re
from gpd.conversations.schemas import ConversationMessageCreate
from gpd.integrations.slack.client import SlackThread

SUPPORTED_BUG_PHRASES = (
    "create a bug",
    "create bug",
    "create a bug task",
    "create a bug from this conversation",
    "create a bug task from this conversation",
)

MENTION_PATTERN = re.compile(r"<@[a-zA-Z0-9_]+>|@gpd\b", re.IGNORECASE)


def is_bug_invocation(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    has_mention = bool(MENTION_PATTERN.search(lower))
    if not has_mention:
        return False
    return any(phrase in lower for phrase in SUPPORTED_BUG_PHRASES)

def has_mention(text: str) -> bool:
    if not text:
        return False
    return bool(MENTION_PATTERN.search(text.lower()))


def normalize_thread_messages(thread: SlackThread) -> list[ConversationMessageCreate]:
    # Sort messages by timestamp
    sorted_messages = sorted(thread.messages, key=lambda m: float(m.ts) if m.ts.replace(".", "", 1).isdigit() else 0.0)

    normalized: list[ConversationMessageCreate] = []
    for idx, msg in enumerate(sorted_messages):
        normalized.append(
            ConversationMessageCreate(
                external_message_id=msg.ts,
                author=msg.user,
                text=msg.text,
                timestamp=msg.ts,
                ordering=idx,
            )
        )
    return normalized
