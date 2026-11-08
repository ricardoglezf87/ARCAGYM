import json
import os
import tempfile
from pathlib import Path, PurePosixPath
from pathlib import PureWindowsPath
from urllib.parse import urlsplit
from urllib.error import URLError
from urllib.request import Request, urlopen


MANIFEST_PATH = Path(__file__).resolve().parents[1] / "app" / "seed" / "exercise_images.json"
IMAGE_URL_PREFIX = "/static/img/exercises/"


def _image_destination(project_root: Path, image_url: str) -> Path:
    if not image_url.startswith(IMAGE_URL_PREFIX):
        raise ValueError(f"Ruta de imagen no permitida: {image_url}")

    relative_path = PurePosixPath(image_url.lstrip("/"))
    filename = relative_path.name
    if (
        len(relative_path.parts) != 4
        or relative_path.parts[:3] != ("static", "img", "exercises")
        or filename in {".", ".."}
        or PureWindowsPath(filename).name != filename
    ):
        raise ValueError(f"Ruta de imagen no permitida: {image_url}")

    return project_root / "app" / Path(*relative_path.parts)


def _download_image(source_url: str, destination: Path) -> None:
    parsed_url = urlsplit(source_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise ValueError(f"URL de origen no permitida: {source_url}")

    request = Request(source_url, headers={"User-Agent": "ARCA-Gym image downloader"})
    with urlopen(request, timeout=30) as response:
        image_data = response.read()
    if not image_data:
        raise OSError("La respuesta no contiene datos")

    temporary_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f"{destination.name}.",
            suffix=".part",
            delete=False,
        ) as temporary_file:
            temporary_path = temporary_file.name
            temporary_file.write(image_data)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def download_missing_images(
    project_root: Path,
    manifest_path: Path = MANIFEST_PATH,
) -> tuple[int, int]:
    with manifest_path.open("r", encoding="utf-8-sig") as manifest_file:
        manifest = json.load(manifest_file)

    entries = manifest.get("images", []) if isinstance(manifest, dict) else manifest
    pending: dict[Path, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        image_url = entry.get("image_url")
        source_url = entry.get("source_url")
        if not isinstance(image_url, str) or not isinstance(source_url, str):
            continue

        destination = _image_destination(project_root, image_url)
        if destination.exists() and destination.stat().st_size > 0:
            continue
        previous_source = pending.get(destination)
        if previous_source and previous_source != source_url:
            raise ValueError(f"Hay varias fuentes para la misma imagen: {image_url}")
        pending[destination] = source_url

    downloaded = 0
    failed = 0
    for destination, source_url in pending.items():
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            _download_image(source_url, destination)
            print(f"Descargada: {destination.relative_to(project_root)}")
            downloaded += 1
        except (OSError, URLError, ValueError) as error:
            print(f"No se pudo descargar {destination.name}: {error}")
            failed += 1

    print(f"Fotos descargadas: {downloaded}; pendientes con error: {failed}.")
    return downloaded, failed


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    _, failed = download_missing_images(project_root)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
