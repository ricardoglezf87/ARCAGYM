import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from scripts.descargar_fotos_ejercicios import download_missing_images


class DownloadMissingExerciseImagesTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.project_root = Path(self.temporary_directory.name)
        self.manifest_path = self.project_root / "manifest.json"

    def tearDown(self):
        self.temporary_directory.cleanup()

    def _write_manifest(self, entries):
        self.manifest_path.write_text(json.dumps({"images": entries}), encoding="utf-8")

    @patch("scripts.descargar_fotos_ejercicios.urlopen")
    def test_downloads_only_missing_images(self, mocked_urlopen):
        existing_image = self.project_root / "app" / "static" / "img" / "exercises" / "already.jpg"
        existing_image.parent.mkdir(parents=True)
        existing_image.write_bytes(b"existing")
        self._write_manifest(
            [
                {
                    "image_url": "/static/img/exercises/already.jpg",
                    "source_url": "https://example.com/already.jpg",
                },
                {
                    "image_url": "/static/img/exercises/missing.jpg",
                    "source_url": "https://example.com/missing.jpg",
                },
            ]
        )
        mocked_urlopen.return_value = io.BytesIO(b"new image")

        self.assertEqual(download_missing_images(self.project_root, self.manifest_path), (1, 0))

        self.assertEqual(existing_image.read_bytes(), b"existing")
        self.assertEqual(
            (existing_image.parent / "missing.jpg").read_bytes(),
            b"new image",
        )
        mocked_urlopen.assert_called_once()

    @patch("scripts.descargar_fotos_ejercicios.urlopen", side_effect=URLError("sin conexion"))
    def test_reports_failed_download_without_creating_file(self, _mocked_urlopen):
        self._write_manifest(
            [
                {
                    "image_url": "/static/img/exercises/missing.jpg",
                    "source_url": "https://example.com/missing.jpg",
                }
            ]
        )

        self.assertEqual(download_missing_images(self.project_root, self.manifest_path), (0, 1))
        self.assertFalse(
            (self.project_root / "app" / "static" / "img" / "exercises" / "missing.jpg").exists()
        )

    def test_rejects_paths_outside_the_exercise_image_directory(self):
        self._write_manifest(
            [
                {
                    "image_url": "/static/img/exercises/..\\\\secret.jpg",
                    "source_url": "https://example.com/secret.txt",
                }
            ]
        )

        with self.assertRaises(ValueError):
            download_missing_images(self.project_root, self.manifest_path)


if __name__ == "__main__":
    unittest.main()
