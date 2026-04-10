import json

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from app.core.config import settings


class MockChatModel(BaseChatModel):
    @property
    def _llm_type(self) -> str:
        return "mock-chat"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        content = messages[-1].content if messages else ""
        if "JSON" in str(content).upper():
            payload = {
                "summary": "Mock summary",
                "required_skills": ["Python", "LLM", "Communication"],
                "risks": ["Skill gaps unclear"],
                "revised_content": "Mock revised resume content",
                "rationale": "Optimized for JD keywords and impact.",
            }
            text = json.dumps(payload, ensure_ascii=False)
        else:
            text = "Mock response"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def get_chat_model() -> BaseChatModel:
    api_key = settings.deepseek_api_key or settings.openai_api_key
    if not api_key:
        return MockChatModel()
    return ChatOpenAI(
        model=settings.deepseek_model,
        api_key=api_key,
        base_url=settings.deepseek_base_url,
        timeout=settings.llm_timeout,
        temperature=0.2,
    )
