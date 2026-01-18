"""
Retrieval Augmented Generation (RAG) utilities.

Provides tools for building RAG pipelines:
- Document chunking
- Context retrieval
- Conversation memory
- RAG chains
"""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import re

from django_matt.ai.base import CompletionResponse, LLMProvider, Message, Role
from django_matt.ai.vectorstore import Document, SearchResult, VectorStore


# =============================================================================
# Document Chunking
# =============================================================================


@dataclass
class Chunk:
    """A chunk of text with metadata."""
    text: str
    index: int
    metadata: Dict[str, Any] = field(default_factory=dict)


class TextSplitter:
    """
    Base class for text splitting strategies.

    Splits text into chunks suitable for embedding and retrieval.
    """

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        length_function: Callable[[str], int] = len,
    ):
        """
        Initialize text splitter.

        Args:
            chunk_size: Target size for each chunk
            chunk_overlap: Overlap between consecutive chunks
            length_function: Function to measure text length
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.length_function = length_function

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text into chunks."""
        raise NotImplementedError


class CharacterSplitter(TextSplitter):
    """
    Split text by character count.

    Simple but may split mid-word or mid-sentence.
    """

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text by character count."""
        chunks = []
        start = 0
        index = 0

        while start < len(text):
            end = start + self.chunk_size

            # Find a good break point (space, newline)
            if end < len(text):
                # Try to break at whitespace
                break_point = text.rfind(" ", start + self.chunk_overlap, end)
                if break_point > start:
                    end = break_point

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    index=index,
                    metadata={**(metadata or {}), "start": start, "end": end},
                ))
                index += 1

            start = end - self.chunk_overlap

        return chunks


class RecursiveSplitter(TextSplitter):
    """
    Recursively split text using multiple separators.

    Tries to split on paragraph boundaries first, then sentences,
    then words if needed.
    """

    def __init__(
        self,
        separators: Optional[List[str]] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.separators = separators or ["\n\n", "\n", ". ", " ", ""]

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Recursively split text."""
        return self._split_recursive(text, self.separators, metadata or {})

    def _split_recursive(
        self,
        text: str,
        separators: List[str],
        metadata: Dict[str, Any],
    ) -> List[Chunk]:
        chunks = []
        separator = separators[0]

        # Split by current separator
        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        good_splits = []
        current_chunk = ""

        for split in splits:
            test_chunk = current_chunk + (separator if current_chunk else "") + split

            if self.length_function(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    good_splits.append(current_chunk)
                current_chunk = split

        if current_chunk:
            good_splits.append(current_chunk)

        # Process splits
        for i, split in enumerate(good_splits):
            if self.length_function(split) <= self.chunk_size:
                chunks.append(Chunk(
                    text=split,
                    index=len(chunks),
                    metadata={**metadata},
                ))
            elif len(separators) > 1:
                # Recursively split with next separator
                sub_chunks = self._split_recursive(split, separators[1:], metadata)
                for chunk in sub_chunks:
                    chunk.index = len(chunks)
                    chunks.append(chunk)
            else:
                # Last resort: just truncate
                chunks.append(Chunk(
                    text=split[:self.chunk_size],
                    index=len(chunks),
                    metadata={**metadata},
                ))

        return chunks


class SentenceSplitter(TextSplitter):
    """
    Split text by sentences.

    Keeps sentences together and groups them into chunks.
    """

    SENTENCE_ENDINGS = re.compile(r'(?<=[.!?])\s+')

    def split(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> List[Chunk]:
        """Split text by sentences."""
        sentences = self.SENTENCE_ENDINGS.split(text)
        chunks = []
        current_chunk = ""
        index = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            test_chunk = current_chunk + (" " if current_chunk else "") + sentence

            if self.length_function(test_chunk) <= self.chunk_size:
                current_chunk = test_chunk
            else:
                if current_chunk:
                    chunks.append(Chunk(
                        text=current_chunk,
                        index=index,
                        metadata={**(metadata or {})},
                    ))
                    index += 1
                current_chunk = sentence

        if current_chunk:
            chunks.append(Chunk(
                text=current_chunk,
                index=index,
                metadata={**(metadata or {})},
            ))

        return chunks


# =============================================================================
# Conversation Memory
# =============================================================================


class ConversationMemory:
    """
    Manages conversation history for RAG applications.

    Supports window-based and summary-based memory strategies.

    Usage:
        memory = ConversationMemory(max_messages=10)
        memory.add_user("What is Python?")
        memory.add_assistant("Python is a programming language...")

        messages = memory.get_messages()
    """

    def __init__(
        self,
        max_messages: int = 20,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize conversation memory.

        Args:
            max_messages: Maximum messages to keep
            system_prompt: Optional system prompt to prepend
        """
        self.max_messages = max_messages
        self.system_prompt = system_prompt
        self._messages: List[Message] = []

    def add_user(self, content: str) -> None:
        """Add a user message."""
        self._messages.append(Message.user(content))
        self._trim()

    def add_assistant(self, content: str) -> None:
        """Add an assistant message."""
        self._messages.append(Message.assistant(content))
        self._trim()

    def add_message(self, message: Message) -> None:
        """Add any message."""
        self._messages.append(message)
        self._trim()

    def _trim(self) -> None:
        """Trim messages to max_messages."""
        if len(self._messages) > self.max_messages:
            self._messages = self._messages[-self.max_messages:]

    def get_messages(self) -> List[Message]:
        """Get all messages with optional system prompt."""
        messages = []
        if self.system_prompt:
            messages.append(Message.system(self.system_prompt))
        messages.extend(self._messages)
        return messages

    def clear(self) -> None:
        """Clear all messages."""
        self._messages.clear()

    @property
    def last_user_message(self) -> Optional[str]:
        """Get the last user message."""
        for msg in reversed(self._messages):
            if msg.role == Role.USER:
                return msg.content
        return None


class SummaryMemory(ConversationMemory):
    """
    Conversation memory that summarizes older messages.

    When the conversation exceeds max_messages, older messages
    are summarized using an LLM.
    """

    def __init__(
        self,
        llm: LLMProvider,
        max_messages: int = 10,
        summary_threshold: int = 20,
        **kwargs,
    ):
        """
        Initialize summary memory.

        Args:
            llm: LLM provider for summarization
            max_messages: Messages to keep after summarization
            summary_threshold: Trigger summarization at this count
        """
        super().__init__(max_messages=summary_threshold, **kwargs)
        self.llm = llm
        self.final_max = max_messages
        self._summary: Optional[str] = None

    async def _summarize(self) -> None:
        """Summarize older messages."""
        if len(self._messages) < self.max_messages:
            return

        # Take older messages to summarize
        to_summarize = self._messages[:-self.final_max]
        to_keep = self._messages[-self.final_max:]

        # Create summary prompt
        conversation = "\n".join(
            f"{msg.role.value}: {msg.content}" for msg in to_summarize
        )

        summary_prompt = Message.user(
            f"Summarize this conversation concisely, preserving key information:\n\n{conversation}"
        )

        response = await self.llm.complete([summary_prompt], temperature=0.3)
        self._summary = response.content
        self._messages = to_keep

    def get_messages(self) -> List[Message]:
        """Get messages with summary context."""
        messages = []

        if self.system_prompt:
            system = self.system_prompt
            if self._summary:
                system += f"\n\nPrevious conversation summary:\n{self._summary}"
            messages.append(Message.system(system))
        elif self._summary:
            messages.append(Message.system(f"Previous conversation summary:\n{self._summary}"))

        messages.extend(self._messages)
        return messages


# =============================================================================
# RAG Chain
# =============================================================================


@dataclass
class RAGResponse:
    """Response from a RAG query."""
    answer: str
    sources: List[SearchResult]
    messages: List[Message]
    raw_response: Optional[CompletionResponse] = None


class RAGChain:
    """
    Retrieval Augmented Generation chain.

    Combines vector search with LLM generation.

    Usage:
        from django_matt.ai import RAGChain, OpenAIProvider, InMemoryVectorStore

        store = InMemoryVectorStore(embedding_provider=embedder)
        await store.add_texts(documents)

        rag = RAGChain(
            llm=OpenAIProvider(),
            vector_store=store,
        )

        response = await rag.query("What is Python?")
        print(response.answer)
        print(response.sources)
    """

    DEFAULT_PROMPT = """Answer the question based on the following context.
If you cannot answer from the context, say so.

Context:
{context}

Question: {question}

Answer:"""

    def __init__(
        self,
        llm: LLMProvider,
        vector_store: VectorStore,
        prompt_template: Optional[str] = None,
        top_k: int = 5,
        memory: Optional[ConversationMemory] = None,
        include_sources: bool = True,
    ):
        """
        Initialize RAG chain.

        Args:
            llm: LLM provider for generation
            vector_store: Vector store for retrieval
            prompt_template: Custom prompt template (use {context} and {question})
            top_k: Number of documents to retrieve
            memory: Optional conversation memory
            include_sources: Include source references in response
        """
        self.llm = llm
        self.vector_store = vector_store
        self.prompt_template = prompt_template or self.DEFAULT_PROMPT
        self.top_k = top_k
        self.memory = memory
        self.include_sources = include_sources

    async def query(
        self,
        question: str,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> RAGResponse:
        """
        Query the RAG chain.

        Args:
            question: User question
            filter: Optional metadata filter for retrieval
            **kwargs: Additional LLM arguments

        Returns:
            RAGResponse with answer and sources
        """
        # Retrieve relevant documents
        results = await self.vector_store.search(
            question,
            top_k=self.top_k,
            filter=filter,
        )

        # Build context from results
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[{i}] {result.document.text}")
        context = "\n\n".join(context_parts)

        # Build prompt
        prompt = self.prompt_template.format(
            context=context,
            question=question,
        )

        # Build messages
        messages = []
        if self.memory:
            messages = self.memory.get_messages()
        messages.append(Message.user(prompt))

        # Generate response
        response = await self.llm.complete(messages, **kwargs)

        # Update memory
        if self.memory:
            self.memory.add_user(question)
            self.memory.add_assistant(response.content)

        return RAGResponse(
            answer=response.content,
            sources=results,
            messages=messages,
            raw_response=response,
        )

    async def query_with_history(
        self,
        question: str,
        history: List[tuple[str, str]],
        **kwargs,
    ) -> RAGResponse:
        """
        Query with explicit conversation history.

        Args:
            question: Current question
            history: List of (user_message, assistant_message) tuples
            **kwargs: Additional arguments
        """
        # Create temporary memory
        temp_memory = ConversationMemory()
        for user_msg, assistant_msg in history:
            temp_memory.add_user(user_msg)
            temp_memory.add_assistant(assistant_msg)

        original_memory = self.memory
        self.memory = temp_memory

        try:
            return await self.query(question, **kwargs)
        finally:
            self.memory = original_memory


class MultiQueryRAG(RAGChain):
    """
    RAG chain that generates multiple query variations.

    Improves retrieval by searching with query variations
    and combining results.
    """

    QUERY_GENERATION_PROMPT = """Generate {n} different versions of the following question
to retrieve relevant documents from a vector database.
Output only the questions, one per line.

Original question: {question}"""

    def __init__(
        self,
        num_queries: int = 3,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.num_queries = num_queries

    async def _generate_queries(self, question: str) -> List[str]:
        """Generate query variations."""
        prompt = self.QUERY_GENERATION_PROMPT.format(
            n=self.num_queries,
            question=question,
        )

        response = await self.llm.complete([Message.user(prompt)], temperature=0.7)
        queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
        return [question] + queries[:self.num_queries]

    async def query(
        self,
        question: str,
        filter: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> RAGResponse:
        """Query with multiple generated queries."""
        # Generate query variations
        queries = await self._generate_queries(question)

        # Search with all queries
        all_results: Dict[str, SearchResult] = {}
        for query in queries:
            results = await self.vector_store.search(query, top_k=self.top_k, filter=filter)
            for result in results:
                doc_id = result.document.id
                if doc_id not in all_results or result.score > all_results[doc_id].score:
                    all_results[doc_id] = result

        # Sort by score and take top_k
        sorted_results = sorted(all_results.values(), key=lambda x: x.score, reverse=True)
        top_results = sorted_results[:self.top_k]

        # Build context
        context_parts = []
        for i, result in enumerate(top_results, 1):
            context_parts.append(f"[{i}] {result.document.text}")
        context = "\n\n".join(context_parts)

        # Generate response
        prompt = self.prompt_template.format(context=context, question=question)
        messages = []
        if self.memory:
            messages = self.memory.get_messages()
        messages.append(Message.user(prompt))

        response = await self.llm.complete(messages, **kwargs)

        if self.memory:
            self.memory.add_user(question)
            self.memory.add_assistant(response.content)

        return RAGResponse(
            answer=response.content,
            sources=top_results,
            messages=messages,
            raw_response=response,
        )


__all__ = [
    # Chunking
    "Chunk",
    "TextSplitter",
    "CharacterSplitter",
    "RecursiveSplitter",
    "SentenceSplitter",
    # Memory
    "ConversationMemory",
    "SummaryMemory",
    # RAG
    "RAGResponse",
    "RAGChain",
    "MultiQueryRAG",
]
