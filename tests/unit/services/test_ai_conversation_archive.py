from services.ai_gateway import conversation_archive
from services.ai_gateway.conversation_archive import ConversationArchiveRequest
import pytest


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


def test_conversation_archive_memory_context_and_clear(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))

    conversation_archive.archive_conversation(
        ConversationArchiveRequest(
            session_id="session-memory",
            title="Water workflow",
            messages=[
                {"role": "user", "content": "Remember this water extraction approach."},
                {"role": "assistant", "content": "Use MNDWI and then clean the mask."},
            ],
        )
    )

    memory = conversation_archive.build_archive_memory_context(limit=3)
    result = conversation_archive.clear_conversation_archives()

    assert "Conversation Archive Memory" in memory
    assert "Water workflow" in memory
    assert result["deleted"] == 1
    assert conversation_archive.list_conversation_archives() == []


def test_conversation_archive_rejects_empty_messages(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))

    try:
        conversation_archive.archive_conversation(ConversationArchiveRequest(messages=[]))
    except ValueError as exc:
        assert "requires at least one message" in str(exc)
    else:
        raise AssertionError("Expected ValueError")


def test_conversation_archive_preserves_generated_artifact_exports(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))
    artifact_id = "a" * 32

    summary = conversation_archive.archive_conversation(
        ConversationArchiveRequest(
            messages=[
                {"role": "user", "content": "Create a table"},
                {
                    "role": "assistant",
                    "content": "Done",
                    "artifacts": [
                        {
                            "artifact_id": artifact_id,
                            "name": "results.xlsx",
                            "kind": "table",
                            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "size": 512,
                            "row_count": 2,
                            "column_count": 3,
                            "download_url": "https://untrusted.example/file",
                        }
                    ],
                },
            ]
        )
    )

    loaded = conversation_archive.get_conversation_archive(summary["archive_id"])
    [artifact] = loaded["messages"][1]["artifacts"]
    assert artifact["name"] == "results.xlsx"
    assert artifact["download_url"] == f"/ai/artifacts/{artifact_id}/download"
    assert artifact["preview_url"] == f"/ai/artifacts/{artifact_id}"


def test_autosave_updates_one_record_and_preserves_creation_time(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))
    payload = dict(archive_id="b" * 32, session_id="session-auto", messages=[{"role": "user", "content": "task"}])
    first = conversation_archive.archive_conversation(ConversationArchiveRequest(**payload))
    payload["messages"].append({"role": "assistant", "content": "done"})
    updated = conversation_archive.archive_conversation(ConversationArchiveRequest(**payload))
    assert first["archive_id"] == updated["archive_id"]
    assert first["created_at"] == updated["created_at"]
    assert updated["message_count"] == 2
    assert len(conversation_archive.list_conversation_archives()) == 1
    with pytest.raises(ValueError, match="another session"):
        conversation_archive.archive_conversation(ConversationArchiveRequest(**{**payload, "session_id": "other"}))
    assert not list(tmp_path.glob("*.tmp"))


def test_history_keeps_more_than_twenty_turns(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_archive, "ARCHIVE_DIR", str(tmp_path))
    messages = [{"role": "user" if i % 2 == 0 else "assistant", "content": str(i)} for i in range(60)]
    summary = conversation_archive.archive_conversation(ConversationArchiveRequest(messages=messages))
    assert conversation_archive.get_conversation_archive(summary["archive_id"])["messages"] == messages
