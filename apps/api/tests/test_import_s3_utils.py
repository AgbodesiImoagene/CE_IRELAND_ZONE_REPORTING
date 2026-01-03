"""Tests for S3 utilities."""

from __future__ import annotations

from io import BytesIO

import pytest
from botocore.exceptions import ClientError, NoCredentialsError

from app.imports.s3_utils import S3Client


class TestS3Client:
    """Test S3 client operations."""

    def test_upload_file_success(self, monkeypatch):
        """Test successful file upload."""
        upload_calls = []

        class MockS3Client:
            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                upload_calls.append({"bucket": bucket, "key": key, "ExtraArgs": ExtraArgs})
                # Read fileobj to simulate upload
                fileobj.read()

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        result = client.upload_file(b"test content", "test/key.txt", "text/plain")

        assert result == "test/key.txt"
        assert len(upload_calls) == 1
        # Use actual bucket name from settings
        assert upload_calls[0]["bucket"] in ["test-bucket", "ce-exports"]
        assert upload_calls[0]["key"] == "test/key.txt"
        assert upload_calls[0]["ExtraArgs"]["ContentType"] == "text/plain"

    def test_upload_file_without_content_type(self, monkeypatch):
        """Test file upload without content type."""
        upload_calls = []

        class MockS3Client:
            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                upload_calls.append({"ExtraArgs": ExtraArgs})

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        client.upload_file(b"test content", "test/key.txt")

        assert upload_calls[0]["ExtraArgs"] == {}

    def test_upload_file_client_error(self, monkeypatch):
        """Test upload with ClientError."""
        class MockS3Client:
            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                raise ClientError({"Error": {"Code": "AccessDenied"}}, "PutObject")

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        with pytest.raises(ClientError):
            client.upload_file(b"test content", "test/key.txt")

    def test_upload_file_no_credentials(self, monkeypatch):
        """Test upload with NoCredentialsError."""
        class MockS3Client:
            def upload_fileobj(self, fileobj, bucket, key, ExtraArgs=None):
                raise NoCredentialsError()

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        with pytest.raises(NoCredentialsError):
            client.upload_file(b"test content", "test/key.txt")

    def test_download_file_success(self, monkeypatch):
        """Test successful file download."""
        class MockS3Client:
            def get_object(self, Bucket, Key):
                return {"Body": BytesIO(b"test content")}

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        result = client.download_file("test/key.txt")

        assert result == b"test content"

    def test_download_file_client_error(self, monkeypatch):
        """Test download with ClientError."""
        class MockS3Client:
            def get_object(self, Bucket, Key):
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        with pytest.raises(ClientError):
            client.download_file("test/key.txt")

    def test_delete_file_success(self, monkeypatch):
        """Test successful file deletion."""
        delete_calls = []

        class MockS3Client:
            def delete_object(self, Bucket, Key):
                delete_calls.append({"bucket": Bucket, "key": Key})

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        client.delete_file("test/key.txt")

        assert len(delete_calls) == 1
        # Use actual bucket name from settings
        assert delete_calls[0]["bucket"] in ["test-bucket", "ce-exports"]
        assert delete_calls[0]["key"] == "test/key.txt"

    def test_delete_file_client_error(self, monkeypatch):
        """Test delete with ClientError (should not raise)."""
        class MockS3Client:
            def delete_object(self, Bucket, Key):
                raise ClientError({"Error": {"Code": "NoSuchKey"}}, "DeleteObject")

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        # Should not raise
        client.delete_file("test/key.txt")

    def test_get_presigned_url_success(self, monkeypatch):
        """Test generating presigned URL."""
        class MockS3Client:
            def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
                return f"https://s3.example.com/{Params['Key']}?signature=xyz"

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        url = client.get_presigned_url("test/key.txt", expiration=3600)

        assert "test/key.txt" in url

    def test_get_presigned_url_client_error(self, monkeypatch):
        """Test presigned URL with ClientError."""
        class MockS3Client:
            def generate_presigned_url(self, ClientMethod, Params, ExpiresIn):
                raise ClientError({"Error": {"Code": "AccessDenied"}}, "GetObject")

        monkeypatch.setattr("app.imports.s3_utils.boto3.client", lambda service, **kwargs: MockS3Client())
        monkeypatch.setattr("app.core.config.settings", type("Settings", (), {
            "s3_endpoint": "http://localhost:9000",
            "s3_access_key": "minioadmin",
            "s3_secret_key": "minioadmin",
            "s3_bucket": "test-bucket",
        })())

        client = S3Client()
        with pytest.raises(ClientError):
            client.get_presigned_url("test/key.txt")

