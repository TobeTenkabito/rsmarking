import asyncio
import io
import zipfile
from unittest.mock import Mock

import fiona
import pytest
from fastapi import FastAPI, File, UploadFile
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile as StoredUpload

from services.annotation_service.utils import shapefile_importer as importer
from services.annotation_service.upload_limits import ShapefileUploadLimitMiddleware


@pytest.fixture
def components(tmp_path):
    path = tmp_path / "points.shp"
    with fiona.open(path, "w", driver="ESRI Shapefile", crs="EPSG:4326", encoding="utf-8",
                    schema={"geometry": "Point", "properties": {"name": "str"}}) as sink:
        for index in range(2):
            sink.write({"geometry": {"type": "Point", "coordinates": (index, index)}, "properties": {"name": f"point-{index}"}})
    return {item.name: item.read_bytes() for item in tmp_path.iterdir() if item.suffix in importer.SHAPEFILE_EXTENSIONS}


def zipped(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def test_valid_shapefile_and_nested_zip_are_still_supported(components):
    features, fields = importer.parse_shapefile_bytes(components)
    zip_features, zip_fields = importer.parse_shapefile_zip(zipped({f"dataset/{name}": data for name, data in components.items()}))
    assert len(features) == len(zip_features) == 2
    assert features[0].properties["name"] == "point-0"
    assert fields == zip_fields


@pytest.mark.parametrize("names", [
    ["../data.shp", "../data.shx", "../data.dbf"],
    ["data.shp", "data.shx", "data.dbf", "payload.py"],
    ["data.shp", "data.shx", "other.dbf"],
    ["data.shp", "data.shx", "data.dbf", "data.SHP"],
    ["C:\\data.shp", "C:\\data.shx", "C:\\data.dbf"],
])
def test_invalid_components_rejected_before_disk_writes(names, monkeypatch):
    temporary = Mock()
    monkeypatch.setattr(importer.tempfile, "TemporaryDirectory", temporary)
    with pytest.raises(ValueError):
        importer.parse_shapefile_bytes({name: b"x" for name in names})
    temporary.assert_not_called()


def test_byte_limit_checked_before_fiona_reads(components, monkeypatch):
    monkeypatch.setattr(importer, "MAX_SHAPEFILE_BYTES", 16)
    open_dataset = Mock()
    monkeypatch.setattr(importer.fiona, "open", open_dataset)
    with pytest.raises(importer.ShapefileLimitError):
        importer.parse_shapefile_bytes(components)
    open_dataset.assert_not_called()


def test_multipart_read_is_bounded_and_counts_all_components(monkeypatch):
    monkeypatch.setattr(importer, "MAX_SHAPEFILE_BYTES", 16)
    uploads = [StoredUpload(filename=f"data{ext}", file=io.BytesIO(b"x" * 8)) for ext in (".shp", ".shx", ".dbf")]
    with pytest.raises(importer.ShapefileLimitError):
        asyncio.run(importer.read_shapefile_uploads(uploads))
    assert sum(upload.file.tell() for upload in uploads) == 17


def test_zip_bomb_rejected_from_member_sizes_before_decompression(monkeypatch):
    archive = zipped({"data.shp": b"x" * 4096, "data.shx": b"x", "data.dbf": b"x"})
    monkeypatch.setattr(importer, "MAX_SHAPEFILE_BYTES", 1024)
    read_member = Mock()
    monkeypatch.setattr(zipfile.ZipFile, "open", read_member)
    with pytest.raises(importer.ShapefileLimitError, match="Decompressed"):
        importer.parse_shapefile_zip(archive)
    read_member.assert_not_called()


def test_zip_member_count_bounded_before_content_reads(monkeypatch):
    archive = zipped({f"readme-{i}.txt": b"x" for i in range(5)})
    monkeypatch.setattr(importer, "MAX_ZIP_MEMBERS", 4)
    with pytest.raises(importer.ShapefileLimitError, match="members"):
        importer.parse_shapefile_zip(archive)


def test_feature_limit_rejects_instead_of_partially_importing(components, monkeypatch):
    monkeypatch.setattr(importer, "MAX_SHAPEFILE_FEATURES", 1)
    with pytest.raises(importer.ShapefileLimitError, match="feature"):
        importer.parse_shapefile_bytes(components)


def test_invalid_zip_is_a_controlled_validation_error():
    with pytest.raises(ValueError, match="Invalid"):
        importer.parse_shapefile_zip(b"not a zip")


@pytest.mark.parametrize("declared", [False, True])
def test_request_body_limit_covers_declared_and_chunked_uploads(declared):
    app = FastAPI()
    app.add_middleware(ShapefileUploadLimitMiddleware, max_bytes=128)
    called = Mock()

    @app.post("/layers/test/import/shapefile")
    async def endpoint(files: list[UploadFile] = File(...)):
        called()
        return {"ok": True}

    body = (b'--boundary\r\nContent-Disposition: form-data; name="files"; filename="data.shp"\r\n\r\n'
            + b"x" * 256 + b"\r\n--boundary--\r\n")
    headers = {"Content-Type": "multipart/form-data; boundary=boundary"}
    if declared:
        headers["Content-Length"] = str(len(body))
    with TestClient(app) as client:
        content = body if declared else iter([body[:100], body[100:]])
        response = client.post("/layers/test/import/shapefile", content=content, headers=headers)
    assert response.status_code == 413
    called.assert_not_called()


def test_http_import_returns_413_without_database_changes(monkeypatch):
    from services.annotation_service.router.layers_router import router
    from services.annotation_service.database import get_db

    monkeypatch.setattr(importer, "MAX_SHAPEFILE_BYTES", 16)
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = lambda: object()
    with TestClient(app) as client:
        response = client.post("/layers/76467ec3-bcef-43d5-9428-f66883b6b151/import/shapefile", files=[
            ("files", (f"data{ext}", b"x" * 8)) for ext in (".shp", ".shx", ".dbf")
        ])
    assert response.status_code == 413


def test_stream_limit_closes_partially_spooled_uploads(monkeypatch):
    import starlette.formparsers as parsers

    app = FastAPI()
    app.add_middleware(ShapefileUploadLimitMiddleware, max_bytes=128)
    uploads = []
    original_spool = parsers.SpooledTemporaryFile

    def capture_spool(*args, **kwargs):
        upload = original_spool(*args, **kwargs)
        uploads.append(upload)
        return upload

    monkeypatch.setattr(parsers, "SpooledTemporaryFile", capture_spool)

    @app.post("/layers/test/import/shapefile")
    async def endpoint(files: list[UploadFile] = File(...)):
        pytest.fail("Oversized multipart upload reached the endpoint")

    scope = {
        "type": "http", "method": "POST", "path": "/layers/test/import/shapefile",
        "query_string": b"", "scheme": "http", "http_version": "1.1",
        "headers": [(b"content-type", b"multipart/form-data; boundary=boundary")],
        "server": ("testserver", 80), "client": ("testclient", 1), "root_path": "",
    }
    chunks = [
        b'--boundary\r\nContent-Disposition: form-data; name="files"; filename="data.shp"\r\n\r\nx',
        b"x" * 256 + b"\r\n--boundary--\r\n",
    ]
    messages = []

    async def receive():
        chunk = chunks.pop(0)
        return {"type": "http.request", "body": chunk, "more_body": bool(chunks)}

    async def send(message):
        messages.append(message)

    asyncio.run(app(scope, receive, send))
    assert messages[0]["status"] == 413
    assert uploads and all(upload.closed for upload in uploads)
