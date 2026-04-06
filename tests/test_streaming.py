from __future__ import annotations

import asyncio

import orjson
import pytest

from django_matt.streaming import (
    SSEEvent,
    event,
    format_sse_event,
    heartbeat,
    sse_endpoint,
    sse_response,
    stream_json,
    stream_response,
    stream_text,
    streaming,
    with_heartbeat,
)


class TestSSEEventFormat:
    def test_data_only(self) -> None:
        ev = SSEEvent(data="hello")
        result = format_sse_event(ev)
        assert result == b"data: hello\n\n"

    def test_named_event(self) -> None:
        ev = SSEEvent(data="world", event="greeting")
        result = format_sse_event(ev)
        assert b"event: greeting\n" in result
        assert b"data: world\n" in result

    def test_event_id(self) -> None:
        ev = SSEEvent(data="x", id="42")
        result = format_sse_event(ev)
        assert b"id: 42\n" in result

    def test_retry(self) -> None:
        ev = SSEEvent(data="x", retry=3000)
        result = format_sse_event(ev)
        assert b"retry: 3000\n" in result

    def test_comment_only(self) -> None:
        ev = SSEEvent(comment="keepalive")
        result = format_sse_event(ev)
        assert result == b": keepalive\n\n"

    def test_dict_data_serialized_as_json(self) -> None:
        ev = SSEEvent(data={"key": "value", "num": 1})
        result = format_sse_event(ev)
        assert b"data: " in result
        data_line = [line for line in result.split(b"\n") if line.startswith(b"data: ")][0]
        payload = data_line[len(b"data: ") :]
        parsed = orjson.loads(payload)
        assert parsed == {"key": "value", "num": 1}

    def test_list_data_serialized_as_json(self) -> None:
        ev = SSEEvent(data=[1, 2, 3])
        result = format_sse_event(ev)
        data_line = [line for line in result.split(b"\n") if line.startswith(b"data: ")][0]
        parsed = orjson.loads(data_line[len(b"data: ") :])
        assert parsed == [1, 2, 3]

    def test_multiline_data(self) -> None:
        ev = SSEEvent(data="line1\nline2\nline3")
        result = format_sse_event(ev)
        assert result.count(b"data: ") == 3

    def test_multiline_comment(self) -> None:
        ev = SSEEvent(comment="line1\nline2")
        result = format_sse_event(ev)
        assert result.count(b": ") == 2

    def test_bytes_data(self) -> None:
        ev = SSEEvent(data=b"raw bytes")
        result = format_sse_event(ev)
        assert b"data: raw bytes\n" in result

    def test_full_event_field_order(self) -> None:
        ev = SSEEvent(
            data="payload",
            event="update",
            id="99",
            retry=5000,
            comment="debug",
        )
        result = format_sse_event(ev)
        lines = result.decode().strip().split("\n")
        assert lines[0].startswith(": debug")
        assert lines[1].startswith("retry: ")
        assert lines[2].startswith("id: ")
        assert lines[3].startswith("event: ")
        assert lines[4].startswith("data: ")

    def test_empty_event(self) -> None:
        ev = SSEEvent()
        result = format_sse_event(ev)
        assert result == b"\n"


class TestSSEResponse:
    @pytest.mark.asyncio
    async def test_sse_response_headers(self) -> None:
        async def gen():
            yield SSEEvent(data="test")

        response = sse_response(gen())
        assert response["Content-Type"] == "text/event-stream"
        assert response["Cache-Control"] == "no-cache"
        assert response["Connection"] == "keep-alive"
        assert response["X-Accel-Buffering"] == "no"
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sse_response_custom_status(self) -> None:
        async def gen():
            yield SSEEvent(data="test")

        response = sse_response(gen(), status=201)
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_sse_response_custom_headers(self) -> None:
        async def gen():
            yield SSEEvent(data="test")

        response = sse_response(gen(), headers={"X-Custom": "yes"})
        assert response["X-Custom"] == "yes"

    @pytest.mark.asyncio
    async def test_sse_response_streams_events(self) -> None:
        async def gen():
            yield SSEEvent(data="first")
            yield SSEEvent(data="second", event="update")

        response = sse_response(gen())
        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)

        assert len(chunks) == 2
        assert b"data: first\n" in chunks[0]
        assert b"event: update\n" in chunks[1]
        assert b"data: second\n" in chunks[1]


class TestStreamResponse:
    @pytest.mark.asyncio
    async def test_stream_response_basic(self) -> None:
        async def gen():
            yield b"chunk1"
            yield b"chunk2"

        response = stream_response(gen())
        assert response["Content-Type"] == "application/octet-stream"
        assert response["Cache-Control"] == "no-cache"

        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)
        assert chunks == [b"chunk1", b"chunk2"]

    @pytest.mark.asyncio
    async def test_stream_json_ndjson(self) -> None:
        async def gen():
            yield {"a": 1}
            yield {"b": 2}

        response = stream_json(gen())
        assert response["Content-Type"] == "application/x-ndjson"

        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)

        assert orjson.loads(chunks[0]) == {"a": 1}
        assert orjson.loads(chunks[1]) == {"b": 2}
        assert all(c.endswith(b"\n") for c in chunks)

    @pytest.mark.asyncio
    async def test_stream_text(self) -> None:
        async def gen():
            yield "hello "
            yield "world"

        response = stream_text(gen())
        assert response["Content-Type"] == "text/plain; charset=utf-8"

        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)
        assert chunks == [b"hello ", b"world"]

    @pytest.mark.asyncio
    async def test_stream_text_bytes_passthrough(self) -> None:
        async def gen():
            yield b"raw"

        response = stream_text(gen())
        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)
        assert chunks == [b"raw"]


class TestHelpers:
    def test_event_convenience(self) -> None:
        ev = event("hi", event_type="msg", id="1", retry=1000, comment="debug")
        assert ev.data == "hi"
        assert ev.event == "msg"
        assert ev.id == "1"
        assert ev.retry == 1000
        assert ev.comment == "debug"

    def test_event_minimal(self) -> None:
        ev = event("simple")
        assert ev.data == "simple"
        assert ev.event is None
        assert ev.id is None

    @pytest.mark.asyncio
    async def test_heartbeat_yields_comments(self) -> None:
        gen = heartbeat(interval=0.01)
        ev = await gen.__anext__()
        assert ev.comment == "heartbeat"
        assert ev.data is None
        await gen.aclose()

    @pytest.mark.asyncio
    async def test_with_heartbeat_passes_events(self) -> None:
        async def source():
            yield SSEEvent(data="a")
            yield SSEEvent(data="b")

        results = []
        async for ev in with_heartbeat(source(), interval=100):
            results.append(ev)
            if len(results) >= 2:
                break

        data_events = [e for e in results if e.data is not None]
        assert len(data_events) == 2
        assert data_events[0].data == "a"
        assert data_events[1].data == "b"

    @pytest.mark.asyncio
    async def test_with_heartbeat_emits_heartbeats(self) -> None:
        async def slow_source():
            await asyncio.sleep(0.05)
            yield SSEEvent(data="done")

        results = []
        async for ev in with_heartbeat(slow_source(), interval=0.01):
            results.append(ev)

        heartbeats = [e for e in results if e.comment == "heartbeat"]
        assert len(heartbeats) >= 1


class TestDecorators:
    @pytest.mark.asyncio
    async def test_sse_endpoint_wraps_generator(self) -> None:
        @sse_endpoint
        async def my_view():
            yield SSEEvent(data="test")

        response = await my_view()
        assert response["Content-Type"] == "text/event-stream"
        assert response.status_code == 200

        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)
        assert b"data: test\n" in chunks[0]

    @pytest.mark.asyncio
    async def test_sse_endpoint_preserves_name(self) -> None:
        @sse_endpoint
        async def named_view():
            yield SSEEvent(data="x")

        assert named_view.__name__ == "named_view"

    @pytest.mark.asyncio
    async def test_sse_endpoint_marker(self) -> None:
        @sse_endpoint
        async def marked():
            yield SSEEvent(data="x")

        assert marked._is_sse_endpoint is True

    @pytest.mark.asyncio
    async def test_streaming_decorator(self) -> None:
        @streaming(content_type="text/csv")
        async def csv_view():
            yield b"a,b,c\n"
            yield b"1,2,3\n"

        response = await csv_view()
        assert response["Content-Type"] == "text/csv"

        chunks = []
        async for chunk in response.streaming_content:
            chunks.append(chunk)
        assert chunks == [b"a,b,c\n", b"1,2,3\n"]

    @pytest.mark.asyncio
    async def test_streaming_marker(self) -> None:
        @streaming()
        async def marked():
            yield b"x"

        assert marked._is_streaming_endpoint is True
