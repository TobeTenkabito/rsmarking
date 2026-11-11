import copy

import pytest
from pydantic import ValidationError

from services.ai_gateway import conversation_archive as archive


@pytest.fixture
def source(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ARCHIVE_DIR", str(tmp_path))
    return archive.archive_conversation(archive.ConversationArchiveRequest(
        session_id="source-session", title="Source chat", messages=[
            {"role": "user", "content": "First question"},
            {"role": "assistant", "content": "First answer", "steps": [{"name": "example_tool"}]},
            {"role": "user", "content": "Later question"},
            {"role": "assistant", "content": "Later answer"},
        ],
    ))


def test_pin_order_survives_autosave_and_unpins_without_changing_recency(source, monkeypatch):
    pinned = archive.pin_conversation(source["archive_id"], True)
    monkeypatch.setattr(archive, "_timestamp", lambda: "2099-01-01T00:00:00Z")
    other = archive.archive_conversation(archive.ConversationArchiveRequest(messages=[{"role": "user", "content": "Newer"}]))
    assert archive.list_conversation_archives()[0]["archive_id"] == source["archive_id"]
    original = archive.get_conversation_archive(source["archive_id"])
    saved = archive.archive_conversation(archive.ConversationArchiveRequest(
        archive_id=source["archive_id"], session_id=source["session_id"], messages=original["messages"],
    ))
    assert saved["pinned"] is True
    assert saved["pinned_at"] == pinned["pinned_at"]
    archive.pin_conversation(source["archive_id"], True)
    assert archive.get_conversation_archive(source["archive_id"])["pinned_at"] == pinned["pinned_at"]
    unpinned = archive.pin_conversation(source["archive_id"], False)
    assert unpinned["pinned"] is False
    assert unpinned["pinned_at"] is None
    assert unpinned["updated_at"] == saved["updated_at"]
    assert len(archive.list_conversation_archives()) == 2


def test_export_import_keeps_content_but_creates_new_ids(source):
    archive.update_conversation_details(source["archive_id"], archive.ConversationDetailsRequest(title="Edited title", note="My note\nSecond line"))
    archive.pin_conversation(source["archive_id"], True)
    original = copy.deepcopy(archive.get_conversation_archive(source["archive_id"]))
    exported = archive.export_conversation(source["archive_id"])
    assert "archive_id" not in exported["conversation"]
    assert "session_id" not in exported["conversation"]
    expected_export = copy.deepcopy(exported)
    # Hand-edited identity fields cannot overwrite existing archives/sessions.
    exported["conversation"].update(archive_id=source["archive_id"], session_id=source["session_id"])
    imported = archive.import_conversation(archive.ConversationImportRequest.model_validate(exported))
    assert imported["archive_id"] != source["archive_id"]
    assert imported["session_id"] != source["session_id"]
    assert imported["title"] == "Edited title"
    assert imported["note"] == "My note\nSecond line"
    assert imported["pinned"] is True
    assert archive.export_conversation(imported["archive_id"]) == expected_export
    loaded = archive.get_conversation_archive(imported["archive_id"])
    assert [m["content"] for m in loaded["messages"]] == [m["content"] for m in original["messages"]]
    assert loaded["messages"][1]["steps"] == original["messages"][1]["steps"]
    assert archive.get_conversation_archive(source["archive_id"]) == original


def test_branch_copies_prefix_and_remains_independent(source):
    archive.pin_conversation(source["archive_id"], True)
    original = copy.deepcopy(archive.get_conversation_archive(source["archive_id"]))
    branch = archive.branch_conversation(source["archive_id"], archive.ConversationBranchRequest(message_index=1))
    record = archive.get_conversation_archive(branch["archive_id"])
    assert branch["session_id"] != source["session_id"]
    assert branch["pinned"] is False
    assert record["messages"] == original["messages"][:2]
    assert record["metadata"] == {"parent_archive_id": source["archive_id"], "branch_message_index": 1}
    record["messages"].append({"role": "user", "content": "A different direction"})
    saved = archive.archive_conversation(archive.ConversationArchiveRequest(
        archive_id=branch["archive_id"], session_id=branch["session_id"], messages=record["messages"], metadata={"autosaved": True},
    ))
    assert saved["metadata"]["parent_archive_id"] == source["archive_id"]
    assert archive.get_conversation_archive(source["archive_id"]) == original
    full = archive.branch_conversation(source["archive_id"], archive.ConversationBranchRequest())
    assert full["message_count"] == 4
    with pytest.raises(ValueError):
        archive.branch_conversation(source["archive_id"], archive.ConversationBranchRequest(message_index=10))
    assert len(archive.list_conversation_archives()) == 3


def test_import_validation_size_and_unsafe_attachment_urls(source, monkeypatch):
    exported = archive.export_conversation(source["archive_id"])
    for role in ("system", "tool"):
        invalid = copy.deepcopy(exported)
        invalid["conversation"]["messages"][0]["role"] = role
        with pytest.raises(ValidationError):
            archive.ConversationImportRequest.model_validate(invalid)
    for version in (0, 2):
        with pytest.raises(ValidationError):
            archive.ConversationImportRequest.model_validate({**exported, "version": version})
    invalid = copy.deepcopy(exported)
    invalid["conversation"]["messages"] = []
    with pytest.raises(ValidationError):
        archive.ConversationImportRequest.model_validate(invalid)
    exported["conversation"]["messages"][0]["attachments"] = [
        {"name": "remote", "image_data_url": "https://tracker.invalid/pixel"},
        {"name": "svg", "image_data_url": "data:image/svg+xml;base64,AAAA"},
        {"name": "png", "image_data_url": "data:image/png;base64,AAAA"},
    ]
    payload = archive.ConversationImportRequest.model_validate(exported)
    imported = archive.import_conversation(payload)
    attachments = archive.get_conversation_archive(imported["archive_id"])["messages"][0]["attachments"]
    assert "image_data_url" not in attachments[0]
    assert "image_data_url" not in attachments[1]
    assert attachments[2]["image_data_url"] == "data:image/png;base64,AAAA"
    monkeypatch.setattr(archive, "MAX_TRANSFER_BYTES", 10)
    with pytest.raises(ValueError, match="20 MB"):
        archive.import_conversation(payload)
    assert len(archive.list_conversation_archives()) == 2


def test_transfer_http_endpoints_restore_independent_branch(source):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from services.ai_gateway.router import router
    from services.ai_gateway.agent_session import get_session_messages, clear_session

    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as client:
        path = f"/ai/conversations/{source['archive_id']}"
        assert client.patch(path + "/pin", json={"pinned": True}).json()["conversation"]["pinned"] is True
        assert client.patch(path + "/pin", json={"pinned": "yes"}).status_code == 422
        exported = client.get(path + "/export")
        assert exported.status_code == 200
        imported = client.post("/ai/conversations/import", json=exported.json())
        assert imported.status_code == 200
        assert imported.json()["conversation"]["archive_id"] != source["archive_id"]
        branched = client.post(path + "/branch", json={"message_index": 0})
        assert branched.status_code == 200
        branch = branched.json()["conversation"]
        assert branch["message_count"] == 1
        restored = client.post(f"/ai/conversations/{branch['archive_id']}/restore", json={})
        assert restored.status_code == 200
        assert get_session_messages(branch["session_id"]) == [{"role": "user", "content": "First question"}]
        clear_session(branch["session_id"])
        assert client.post(path + "/branch", json={"message_index": 499}).status_code == 400
        assert client.post("/ai/conversations/import", json={"format": "unknown"}).status_code == 422
        missing = "/ai/conversations/" + "f" * 32
        assert client.get(missing + "/export").status_code == 404
        assert client.patch(missing + "/pin", json={"pinned": False}).status_code == 404
        assert client.post(missing + "/branch", json={}).status_code == 404
