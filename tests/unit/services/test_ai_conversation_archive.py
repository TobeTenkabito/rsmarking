from services.ai_gateway import conversation_archive
from services.ai_gateway.conversation_archive import ConversationArchiveRequest


def test_conversation_archive_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))

    summary = conversation_archive.archive_conversation(
        ConversationArchiveRequest(
            session_id="session-1",
            messages=[
                {"role": "user", "content": "Make a water mask"},
                {"role": "assistant", "content": "Done", "steps": [{"name": "run_script_sandbox"}]},
            ],
        )
    )

    archives = conversation_archive.list_conversation_archives()
    loaded = conversation_archive.get_conversation_archive(summary["archive_id"])

    assert len(archives) == 1
    assert archives[0]["title"] == "Make a water mask"
    assert loaded["session_id"] == "session-1"
    assert loaded["messages"][1]["steps"][0]["name"] == "run_script_sandbox"


def test_conversation_archive_rejects_empty_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))

    try:
        conversation_archive.archive_conversation(ConversationArchiveRequest(messages=[]))
    except ValueError as exc:
        assert "requires at least one message" in str(exc)
    else:
        raise AssertionError("Expected ValueError")
