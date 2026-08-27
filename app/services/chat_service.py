from app.repositories import (
    get_chat_messages,
    add_message,
)

from app.services.gemini_service import (
    GeminiService,
)


class ChatService:

    def __init__(self):

        self.gemini = GeminiService()


    def send_message(
        self,
        user_id: int,
        chat_id: int,
        text: str,
    ):

        text = text.strip()

        if not text:
            return ""

        add_message(
            chat_id=chat_id,
            user_id=user_id,
            role="user",
            content=text,
        )

        messages = get_chat_messages(
            chat_id=chat_id,
            user_id=user_id,
        )

        history = []

        for message in messages:

            history.append(
                {
                    "role": message.role,
                    "content": message.content,
                }
            )

        answer = self.gemini.generate(
            history
        )

        add_message(
            chat_id=chat_id,
            user_id=user_id,
            role="model",
            content=answer,
        )

        return answer