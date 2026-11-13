"""Telegram Update handlers for processing messages and callbacks."""
import logging
from typing import Any

from chats.feedback import apply_feedback_fields, save_log_feedback
from chats.models import WorkspaceChatLog
from chats.services import extract_response_from_ollama_payload
from llm.chat import run_chat
from workspaces.models import TelegramBot, TelegramChatSession
from workspaces.telegram.client import TelegramClient

logger = logging.getLogger(__name__)


def handle_telegram_update(
    bot: TelegramBot,
    update: dict[str, Any],
    client: TelegramClient | None = None,
) -> None:
    """Process an incoming update from Telegram."""
    if client is None:
        client = TelegramClient()

    token = bot.get_token()
    if not token:
        logger.warning("Bot %s has no token configured", bot.id)
        return

    message = update.get("message")
    callback_query = update.get("callback_query")

    if not message and not callback_query:
        return

    if bot.workspace is None:
        if message:
            chat_id = message.get("chat", {}).get("id")
            if chat_id:
                client.send_message(
                    token,
                    chat_id,
                    "Бот наразі налаштовується адміністратором.",
                )
        elif callback_query:
            cq_id = callback_query.get("id")
            if cq_id:
                client.answer_callback_query(
                    token,
                    cq_id,
                    text="Бот наразі налаштовується адміністратором.",
                )
        return

    # Extract user and chat info
    chat_id: int | None = None
    username: str = ""
    prompt: str = ""

    if callback_query:
        cq_id = callback_query.get("id", "")
        from_user = callback_query.get("from", {})
        username = from_user.get("username") or from_user.get("first_name") or ""
        msg = callback_query.get("message") or {}
        chat_id = msg.get("chat", {}).get("id")
        message_id = msg.get("message_id")
        data = callback_query.get("data", "")

        if not chat_id:
            return

        session, _ = TelegramChatSession.objects.get_or_create(
            bot=bot,
            telegram_chat_id=chat_id,
            defaults={"telegram_username": username},
        )
        if username and session.telegram_username != username:
            session.telegram_username = username
            session.save(update_fields=["telegram_username", "updated_at"])

        # 1. Feedback action: fb:<log_id>:<action>
        if data.startswith("fb:"):
            parts = data.split(":")
            action = ""
            if len(parts) == 3:
                _, log_id_str, action = parts
                try:
                    log_id = int(log_id_str)
                    log = WorkspaceChatLog.objects.filter(
                        id=log_id,
                        workspace=bot.workspace,
                    ).first()
                    if log:
                        if action in ("up", "down"):
                            apply_feedback_fields(log, {"feedback": action})
                        elif action == "handoff":
                            apply_feedback_fields(log, {"needs_handoff": True})
                        save_log_feedback(log)
                except (ValueError, TypeError) as exc:
                    logger.warning("Invalid log_id in callback: %s", exc)

            ans_text = "Запит передано фахівцю!" if action == "handoff" else "Дякуємо за відгук!"
            client.answer_callback_query(token, cq_id, text=ans_text)
            if message_id:
                client.edit_message_reply_markup(
                    token,
                    chat_id,
                    message_id,
                    reply_markup={"inline_keyboard": []},
                )
            return

        # 2. FAQ quick button: faq:<idx>
        if data.startswith("faq:"):
            client.answer_callback_query(token, cq_id)
            try:
                idx = int(data.split(":", 1)[1])
                faq_list = bot.workspace.embed_faq_questions or []
                if 0 <= idx < len(faq_list):
                    prompt = faq_list[idx]
                else:
                    return
            except (ValueError, IndexError):
                return
        else:
            client.answer_callback_query(token, cq_id)
            return

    elif message:
        from_user = message.get("from", {})
        username = from_user.get("username") or from_user.get("first_name") or ""
        chat_id = message.get("chat", {}).get("id")
        text = (message.get("text") or "").strip()

        if not chat_id or not text:
            return

        session, _ = TelegramChatSession.objects.get_or_create(
            bot=bot,
            telegram_chat_id=chat_id,
            defaults={"telegram_username": username},
        )
        if username and session.telegram_username != username:
            session.telegram_username = username
            session.save(update_fields=["telegram_username", "updated_at"])

        # Check commands: /start, /reset, /clear
        first_word = text.split()[0].lower()
        if first_word in ("/start", "/reset", "/clear") or first_word.startswith(
            ("/start@", "/reset@", "/clear@")
        ):
            session.messages = []
            session.save(update_fields=["messages", "updated_at"])

            greeting = (bot.workspace.embed_greeting or "").strip()
            if not greeting:
                greeting = f"Вітаю! Я помічник воркспейсу «{bot.workspace.name}». Поставте своє запитання."

            faq_list = bot.workspace.embed_faq_questions or []
            reply_markup = None
            if faq_list:
                inline_keyboard = [
                    [{"text": q[:64], "callback_data": f"faq:{i}"}]
                    for i, q in enumerate(faq_list[:10])
                ]
                reply_markup = {"inline_keyboard": inline_keyboard}

            client.send_message(token, chat_id, greeting, reply_markup=reply_markup)
            return

        prompt = text

    # Process prompt via run_chat
    if not prompt or not chat_id:
        return

    model_names = bot.workspace.model_names or []
    if not model_names or not model_names[0]:
        client.send_message(
            token,
            chat_id,
            "Бот наразі налаштовується адміністратором: модель не обрана.",
        )
        return

    model = model_names[0]
    client.send_chat_action(token, chat_id, action="typing")

    history = session.messages[-12:] if session.messages else []
    messages = [*history, {"role": "user", "content": prompt}]

    response = run_chat(
        model=model,
        messages=messages,
        stream=False,
        workspace=bot.workspace,
        user=None,
        prompt=prompt,
    )

    if response.status_code == 200:
        resp_data = response.data if hasattr(response, "data") else {}
        answer = extract_response_from_ollama_payload(resp_data)
        if not answer and isinstance(resp_data, dict):
            answer = (
                resp_data.get("response")
                or resp_data.get("message", {}).get("content", "")
                or ""
            )

        log_id = resp_data.get("log_id") if isinstance(resp_data, dict) else None

        new_messages = [
            *history,
            {"role": "user", "content": prompt},
            {"role": "assistant", "content": answer},
        ]
        session.messages = new_messages[-12:]
        session.save(update_fields=["messages", "updated_at"])

        reply_markup = None
        if log_id:
            reply_markup = {
                "inline_keyboard": [
                    [
                        {"text": "👍 Корисно", "callback_data": f"fb:{log_id}:up"},
                        {"text": "👎 Не допомогло", "callback_data": f"fb:{log_id}:down"},
                        {"text": "🙋 До людини", "callback_data": f"fb:{log_id}:handoff"},
                    ]
                ]
            }

        client.send_message(token, chat_id, answer, reply_markup=reply_markup)
    else:
        error_msg = "Вибачте, виникла помилка під час обробки вашого запиту."
        if (
            hasattr(response, "data")
            and isinstance(response.data, dict)
            and "error" in response.data
        ):
            error_msg = response.data["error"]
        client.send_message(token, chat_id, error_msg)
