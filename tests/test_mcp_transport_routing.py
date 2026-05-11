import asyncio

from mcp_server import MergedMcpEndpoint


def test_post_sse_uses_streamable_http_manager():
    calls = []

    async def fake_classic(scope, receive, send):
        calls.append(("classic", scope["method"]))

    async def fake_streamable(scope, receive, send):
        calls.append(("streamable", scope["method"]))

    endpoint = MergedMcpEndpoint(
        classic_sse_handler=fake_classic,
        streamable_http_handler=fake_streamable,
    )

    asyncio.run(endpoint({"type": "http", "method": "POST"}, None, None))

    assert calls == [("streamable", "POST")]


def test_get_sse_preserves_classic_sse_transport():
    calls = []

    async def fake_classic(scope, receive, send):
        calls.append(("classic", scope["method"]))

    async def fake_streamable(scope, receive, send):
        calls.append(("streamable", scope["method"]))

    endpoint = MergedMcpEndpoint(
        classic_sse_handler=fake_classic,
        streamable_http_handler=fake_streamable,
    )

    asyncio.run(endpoint({"type": "http", "method": "GET"}, None, None))

    assert calls == [("classic", "GET")]


def test_get_sse_with_mcp_session_id_uses_streamable_http_manager():
    calls = []

    async def fake_classic(scope, receive, send):
        calls.append(("classic", scope["method"]))

    async def fake_streamable(scope, receive, send):
        calls.append(("streamable", scope["method"]))

    endpoint = MergedMcpEndpoint(
        classic_sse_handler=fake_classic,
        streamable_http_handler=fake_streamable,
    )

    asyncio.run(
        endpoint(
            {
                "type": "http",
                "method": "GET",
                "headers": [(b"mcp-session-id", b"session-1")],
            },
            None,
            None,
        )
    )

    assert calls == [("streamable", "GET")]
