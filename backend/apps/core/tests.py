from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings


@override_settings(DEBUG=True)
class MediaStreamingTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.media_root = Path(self._tmpdir.name)
        track_dir = self.media_root / "music" / "tracks"
        track_dir.mkdir(parents=True, exist_ok=True)
        self.payload = b"abcdefghijklmnopqrstuvwxyz"
        (track_dir / "sample.mp3").write_bytes(self.payload)

    def test_media_request_returns_full_file(self) -> None:
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get("/media/music/tracks/sample.mp3")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(response["Content-Length"], str(len(self.payload)))
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    def test_media_request_honors_byte_range(self) -> None:
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get(
                "/media/music/tracks/sample.mp3",
                HTTP_RANGE="bytes=5-9",
            )

        self.assertEqual(response.status_code, 206)
        self.assertEqual(response["Accept-Ranges"], "bytes")
        self.assertEqual(
            response["Content-Range"],
            f"bytes 5-9/{len(self.payload)}",
        )
        self.assertEqual(response["Content-Length"], "5")
        self.assertEqual(b"".join(response.streaming_content), self.payload[5:10])
