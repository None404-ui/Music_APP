from pathlib import Path
import shutil
import struct
import unittest
import wave
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from .models import AdUnit, Profile


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

    def test_media_invalid_abr_ignored(self) -> None:
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get("/media/music/tracks/sample.mp3?crates_abr=9999")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    def test_media_transcode_fallback_on_bad_source(self) -> None:
        """Невалидный «mp3»: ffmpeg не даёт данных — отдаём оригинал."""
        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get("/media/music/tracks/sample.mp3?crates_abr=128")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), self.payload)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_media_transcode_wav_returns_mpeg(self) -> None:
        wav_path = self.media_root / "music" / "tracks" / "tone.wav"
        with wave.open(str(wav_path), "w") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(struct.pack("<h", 0) * 800)

        with override_settings(MEDIA_ROOT=self.media_root):
            response = self.client.get("/media/music/tracks/tone.wav?crates_abr=128")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        body = b"".join(response.streaming_content)
        self.assertGreater(len(body), 400)
        self.assertTrue(body.startswith(b"ID3") or body[:2] == b"\xff\xfb")


@override_settings(DEBUG=True)
class AdsViewTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self._tmpdir = TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.media_root = Path(self._tmpdir.name)
        self._media_override = override_settings(MEDIA_ROOT=self.media_root)
        self._media_override.enable()
        self.addCleanup(self._media_override.disable)
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="free@example.com",
            email="free@example.com",
            password="password123",
        )
        self.premium_user = user_model.objects.create_user(
            username="premium@example.com",
            email="premium@example.com",
            password="password123",
        )
        self.staff_user = user_model.objects.create_user(
            username="staff@example.com",
            email="staff@example.com",
            password="password123",
            is_staff=True,
        )
        Profile.objects.create(user=self.user, nickname="free")
        Profile.objects.create(
            user=self.premium_user,
            nickname="premium",
            is_premium=True,
        )
        Profile.objects.create(user=self.staff_user, nickname="staff")

    def _create_ad(self, *, active: bool = True) -> AdUnit:
        ad = AdUnit.objects.create(
            placement="app_top_banner",
            is_active=active,
            config_json="{}",
        )
        ad.banner_image.save("banner.png", ContentFile(b"fake image"), save=True)
        return ad

    def test_free_user_receives_active_banner(self) -> None:
        self._create_ad()
        self.client.force_login(self.user)

        response = self.client.get("/api/ads/?placement=app_top_banner&limit=1")

        self.assertEqual(response.status_code, 200)
        ads = response.json()["ads"]
        self.assertEqual(len(ads), 1)
        self.assertEqual(ads[0]["placement"], "app_top_banner")
        self.assertIn("/media/ads/banners/banner", ads[0]["image_url"])

    def test_premium_user_receives_no_ads(self) -> None:
        self._create_ad()
        self.client.force_login(self.premium_user)

        response = self.client.get("/api/ads/?placement=app_top_banner&limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ads": []})

    def test_staff_user_receives_no_ads(self) -> None:
        self._create_ad()
        self.client.force_login(self.staff_user)

        response = self.client.get("/api/ads/?placement=app_top_banner&limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ads": []})

    def test_inactive_banner_is_not_returned(self) -> None:
        self._create_ad(active=False)
        self.client.force_login(self.user)

        response = self.client.get("/api/ads/?placement=app_top_banner&limit=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ads": []})


class AuthRegistrationTests(TestCase):
    def test_registration_creates_profile_with_nickname(self) -> None:
        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com",
                "password": "password123",
                "nickname": "NewUser",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        profile = Profile.objects.get(user__username="new@example.com")
        self.assertEqual(profile.nickname, "NewUser")

    def test_registration_requires_unique_nickname(self) -> None:
        user_model = get_user_model()
        user = user_model.objects.create_user(
            username="old@example.com",
            email="old@example.com",
            password="password123",
        )
        Profile.objects.create(user=user, nickname="TakenName")

        response = self.client.post(
            "/api/auth/register/",
            {
                "email": "new@example.com",
                "password": "password123",
                "nickname": "takenname",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
