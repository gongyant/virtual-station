from __future__ import annotations

import argparse
import io
import json
import time
import urllib.request
import zipfile
from collections import OrderedDict
from pathlib import Path


DEFAULT_URL = (
    "https://zenodo.org/api/records/5643392/files/SWORD_shp_v2.zip/content"
)


class HttpRangeReader(io.RawIOBase):
    """Seekable, block-cached reader for a large remote ZIP archive."""

    def __init__(self, url: str, block_size: int = 8 * 1024 * 1024) -> None:
        self.url = url
        self.block_size = block_size
        self.position = 0
        self.cache: OrderedDict[int, bytes] = OrderedDict()
        request = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(request, timeout=60) as response:
            self.size = int(response.headers["Content-Length"])

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.position

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.position + offset
        elif whence == io.SEEK_END:
            position = self.size + offset
        else:
            raise ValueError(f"Unsupported whence: {whence}")
        self.position = max(0, min(position, self.size))
        return self.position

    def _get_block(self, block_index: int) -> bytes:
        if block_index in self.cache:
            value = self.cache.pop(block_index)
            self.cache[block_index] = value
            return value
        start = block_index * self.block_size
        end = min(start + self.block_size, self.size) - 1
        request = urllib.request.Request(
            self.url, headers={"Range": f"bytes={start}-{end}"}
        )
        last_error: Exception | None = None
        for attempt in range(5):
            try:
                with urllib.request.urlopen(request, timeout=120) as response:
                    if response.status != 206:
                        raise OSError(f"Server ignored range request: {response.status}")
                    value = response.read()
                break
            except Exception as error:  # network retry only
                last_error = error
                time.sleep(2 ** attempt)
        else:
            raise OSError(f"Range request failed: {last_error}")
        self.cache[block_index] = value
        while len(self.cache) > 6:
            self.cache.popitem(last=False)
        return value

    def read(self, size: int = -1) -> bytes:
        if self.position >= self.size:
            return b""
        if size is None or size < 0:
            size = self.size - self.position
        size = min(size, self.size - self.position)
        parts: list[bytes] = []
        remaining = size
        while remaining:
            block_index = self.position // self.block_size
            within = self.position % self.block_size
            block = self._get_block(block_index)
            take = min(remaining, len(block) - within)
            parts.append(block[within : within + take])
            self.position += take
            remaining -= take
        return b"".join(parts)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List or extract selected SWORD v2 shapefile archive members via HTTP ranges."
    )
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--contains", default="as_sword_reaches")
    parser.add_argument(
        "--suffix",
        default="",
        help="Optional archive-member suffix, for example .dbf.",
    )
    parser.add_argument("--extract", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/sword_v2"))
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/processed/natural_width/sword_archive_members.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    reader = HttpRangeReader(args.url)
    with zipfile.ZipFile(reader) as archive:
        matches = [
            item
            for item in archive.infolist()
            if args.contains in item.filename
            and (not args.suffix or item.filename.lower().endswith(args.suffix.lower()))
        ]
        manifest = {
            "source_url": args.url,
            "archive_size_bytes": reader.size,
            "filter": args.contains,
            "suffix": args.suffix,
            "matches": [
                {
                    "filename": item.filename,
                    "compressed_bytes": item.compress_size,
                    "uncompressed_bytes": item.file_size,
                    "crc": item.CRC,
                }
                for item in matches
            ],
        }
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if args.extract:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            for item in matches:
                target = args.output_dir / Path(item.filename).name
                with archive.open(item) as source, target.open("wb") as destination:
                    while block := source.read(1024 * 1024):
                        destination.write(block)
                print(f"extracted {target} ({item.file_size} bytes)")
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
