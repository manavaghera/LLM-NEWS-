import logging
from typing import AsyncIterator, Dict, List, Tuple
from urllib.parse import urlparse

from ..schemas.chat import ChatStreamRequest
from .llm_service import KNOWLEDGE_GRAPH, LLMService
from .news_service import NewsService

logger = logging.getLogger(__name__)

MAX_SOURCES = 25


class ChatService:
    def __init__(self, llm_service: LLMService, news_service: NewsService):
        self.llm_service = llm_service
        self.news_service = news_service

    def create_system_prompt(self, article_context: str, rag_context: str, sources_block: str) -> str:
        """System prompt: answer only from the supplied news data and cite it by number"""
        prompt = """You are the news assistant for NewsSense, an AI news site whose articles are written from public news reports.

RESPONSE STYLE:
- Be conversational, clear and short
- Answer only from the data below. If it doesn't contain the answer, say so instead of guessing.
- Cite the numbered sources in square brackets, like [1] or [2][3], right after the sentence they support. Only use numbers listed under SOURCES.
"""
        if article_context:
            prompt += f"\nCURRENT ARTICLE DATA:\n{article_context}\n"
        if rag_context:
            prompt += f"\nADDITIONAL RESEARCH DATA:\n{rag_context}\n"
        if sources_block:
            prompt += f"\nSOURCES:\n{sources_block}\n"
        return prompt

    def _article_context(self, group_id: str, date: str, question: str) -> Tuple[str, str, List[Dict]]:
        """Context for questions about one article; its sources are the article's original reports"""
        article = self.news_service.get_article(date, group_id) or {}
        urls = list(dict.fromkeys(
            str(url) for section in article.get("body", []) if isinstance(section, dict)
            for url in section.get("sources", []) or []
        ))[:MAX_SOURCES]
        sources = [{"label": str(i), "title": urlparse(url).netloc.removeprefix("www."), "url": url}
                   for i, url in enumerate(urls, 1)]
        return (
            self.news_service.get_article_context(group_id, date),
            self.news_service.get_rag_context(group_id, date, question),
            sources,
        )

    def _edition_context(self, date: str) -> Tuple[str, List[Dict]]:
        """Context for general questions: that day's stories, each citable by number"""
        stories = self.news_service.get_filtered_news(date)[:MAX_SOURCES]
        if not stories:
            return "", []
        lines = [f"[{i}] ({s['category']}) {s['headline']}: {s['summary']}" for i, s in enumerate(stories, 1)]
        sources = [{"label": str(i), "title": s["headline"], "url": f"/article/{date}/{s['group_id']}"}
                   for i, s in enumerate(stories, 1)]
        return f"STORIES PUBLISHED ON {date} (numbered as sources):\n" + "\n".join(lines), sources

    async def stream_chat(self, request: ChatStreamRequest) -> AsyncIterator[Dict]:
        """Yield {"type": "meta" | "delta"} events for a reply. History comes from the caller, never
        from shared server memory, so one visitor's conversation can't leak into another's."""
        question = request.message.strip()

        if request.model == KNOWLEDGE_GRAPH and self.llm_service.knowledge_graph_available:
            yield {"type": "meta", "provider": "Alibaba Knowledge Graph", "model": KNOWLEDGE_GRAPH, "sources": []}
            yield {"type": "delta", "text": await self.llm_service.ask_knowledge_graph(question)}
            return

        client_info = self.llm_service.pick_client(request.model)
        if not client_info:
            raise RuntimeError("No AI provider is configured. Add an API key to .env and restart the backend.")
        provider, client, model = client_info

        context = request.context
        rag_context = ""
        if context and context.currentGroupId and context.currentDate:
            article_context, rag_context, sources = self._article_context(
                context.currentGroupId, context.currentDate, question
            )
            sources_block = "\n".join(f"[{s['label']}] {s['title']}" for s in sources)
        else:
            date = (context.currentDate if context and context.currentDate else None) or self.news_service.get_most_recent_date()
            article_context, sources = self._edition_context(date)
            sources_block = "The numbered stories above."

        messages = [{"role": "system", "content": self.create_system_prompt(article_context, rag_context, sources_block)}]
        messages += [{"role": item.role, "content": item.content} for item in request.history]
        messages.append({"role": "user", "content": question})

        yield {"type": "meta", "provider": provider, "model": model, "sources": sources}
        async for text in client.stream(messages, model=model):
            yield {"type": "delta", "text": text}
