"""Resource subscription support in the stdio MCP server.

Covers:
- ``initialize`` advertises ``resources.subscribe: true`` and
  ``resources.listChanged: true`` capabilities
- ``resources/subscribe`` / ``resources/unsubscribe`` methods accept a
  URI and update the subscription set
- ``notify_resource_updated(uri)`` only writes when the URI is subscribed
- ``notify_resources_list_changed()`` always writes
"""

from __future__ import annotations

import json

import pytest

from src.sop_mcp.utils.stdiomcp import StdioMCP


@pytest.fixture
def mcp():
    server = StdioMCP("test-mcp")

    @server.resource("sop://example", name="example", mime_type="text/markdown")
    def _read() -> str:
        return "hello"

    return server


class TestInitializeCapabilities:
    def test_advertises_subscribe_and_list_changed(self, mcp: StdioMCP):
        response = mcp._handle_request("initialize", {}, 1)
        caps = response["result"]["capabilities"]["resources"]
        assert caps["subscribe"] is True
        assert caps["listChanged"] is True


class TestSubscribeUnsubscribe:
    def test_subscribe_adds_uri_to_set(self, mcp: StdioMCP):
        response = mcp._handle_request("resources/subscribe", {"uri": "sop://example"}, 1)
        assert response["result"] == {}
        assert "sop://example" in mcp._subscriptions

    def test_unsubscribe_removes_uri(self, mcp: StdioMCP):
        mcp._subscriptions.add("sop://example")
        response = mcp._handle_request("resources/unsubscribe", {"uri": "sop://example"}, 1)
        assert response["result"] == {}
        assert "sop://example" not in mcp._subscriptions

    def test_subscribe_rejects_missing_uri(self, mcp: StdioMCP):
        response = mcp._handle_request("resources/subscribe", {}, 1)
        assert "error" in response

    def test_subscribe_allows_uri_not_yet_registered(self, mcp: StdioMCP):
        """Clients may subscribe to URIs that don't exist yet — typical
        when the SOP hasn't been published at subscription time."""
        response = mcp._handle_request("resources/subscribe", {"uri": "sop://future_sop"}, 1)
        assert response["result"] == {}
        assert "sop://future_sop" in mcp._subscriptions


class TestUpdatedNotification:
    def test_suppressed_when_unsubscribed(self, mcp: StdioMCP, capsys):
        mcp.notify_resource_updated("sop://example")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_emitted_when_subscribed(self, mcp: StdioMCP, capsys):
        mcp._subscriptions.add("sop://example")
        mcp.notify_resource_updated("sop://example")
        out = capsys.readouterr().out.strip()
        assert out, "Expected a notification on stdout"

        payload = json.loads(out)
        assert payload["method"] == "notifications/resources/updated"
        assert payload["params"]["uri"] == "sop://example"

    def test_list_changed_always_emitted(self, mcp: StdioMCP, capsys):
        mcp.notify_resources_list_changed()
        out = capsys.readouterr().out.strip()
        payload = json.loads(out)
        assert payload["method"] == "notifications/resources/list_changed"


class TestPublishEmitsUpdated:
    def test_published_sop_triggers_updated_notification(self, tmp_path, monkeypatch, capsys):
        """End-to-end: subscribing to an SOP URI and publishing an update
        yields a ``notifications/resources/updated`` notification.
        """
        import src.sop_mcp.server as server_module
        import src.sop_mcp.tools.publish_sop as publish_module
        from src.sop_mcp.utils.storage import LocalFilesystemBackend

        backend = LocalFilesystemBackend(base_dir=tmp_path, is_ephemeral=False)
        mcp_server = StdioMCP("test-mcp")
        mcp_server._subscriptions.add("sop://subbed_sop")

        monkeypatch.setattr(publish_module, "backend", backend)
        monkeypatch.setattr(server_module, "backend", backend)
        monkeypatch.setattr(server_module, "mcp", mcp_server)

        # Drain any prior output before we publish.
        capsys.readouterr()

        content = (
            "---\n"
            "name: subbed_sop\n"
            "version: 1\n"
            "owner: tests\n"
            "stage: preprod\n"
            "---\n\n"
            "# Subbed SOP\n\n"
            "## Overview\n\nContent that changes.\n\n"
            "### Step 1: Do\n\nAction. **Time Estimate:** 1 minute\n"
        )
        result = publish_module.handler(content, stage="preprod")
        assert result["success"] is True

        output = capsys.readouterr().out
        updates = [
            line
            for line in output.splitlines()
            if '"notifications/resources/updated"' in line and '"sop://subbed_sop"' in line
        ]
        assert updates, f"No resources/updated notification in:\n{output}"
