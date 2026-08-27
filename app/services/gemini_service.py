from google import genai
from google.genai import types

from app.config import settings


class GeminiService:

    def __init__(self):

        if not settings.gemini_api_key:

            raise RuntimeError(
                "GEMINI_API_KEY is not configured."
            )

        self.client = genai.Client(
            api_key=settings.gemini_api_key
        )


    def generate(
        self,
        messages,
    ):

        contents = []

        for message in messages:

            role = (
                "user"
                if message["role"] == "user"
                else "model"
            )

            contents.append(
                types.Content(
                    role=role,
                    parts=[
                        types.Part.from_text(
                            text=message["content"]
                        )
                    ],
                )
            )

        response = (
            self.client
            .models
            .generate_content(
                model=settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are the AI assistant "
                        "inside a private desktop "
                        "application. "
                        "Answer clearly and helpfully."
                    )
                ),
            )
        )

        return response.text or ""