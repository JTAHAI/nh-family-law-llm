"""Acquire one hash-pinned build input under dist, never in the installed app."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 256 * 1024 * 1024


class BuildInputError(ValueError):
    pass


def _check_path(path: Path) -> None:
    if not path.is_relative_to(ROOT / 'dist') or path == ROOT / 'dist':
        raise BuildInputError('build_input_outside_owned_dist')
    for part in (path, *path.parents):
        try:
            value = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(value.st_mode) or getattr(value, 'st_file_attributes', 0) & 0x400:
            raise BuildInputError('linked_build_input_refused')
        if part == path and not stat.S_ISREG(value.st_mode):
            raise BuildInputError('nonregular_build_input_refused')


def _digest(path: Path) -> str:
    _check_path(path)
    digest = hashlib.sha256()
    count = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):
            count += len(chunk)
            if count > MAX_BYTES:
                raise BuildInputError('build_input_size_limit')
            digest.update(chunk)
    return digest.hexdigest()


class HTTPSOnlyRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise BuildInputError('insecure_build_input_redirect')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(url: str, destination: Path, expected_sha256: str, *, attempts: int = 3) -> None:
    if not re.fullmatch('[0-9a-f]{64}', expected_sha256):
        raise BuildInputError('invalid_build_input_digest')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise BuildInputError('https_build_input_required')
    if type(attempts) is not int or not 1 <= attempts <= 4:
        raise BuildInputError('invalid_build_input_attempts')
    destination = Path(os.path.abspath(destination))
    _check_path(destination)
    if destination.exists():
        if _digest(destination) != expected_sha256:
            raise BuildInputError('existing_build_input_digest_mismatch')
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    opener = build_opener(HTTPSOnlyRedirect())
    for attempt in range(attempts):
        descriptor, name = tempfile.mkstemp(prefix='.pinned-input-', dir=destination.parent)
        temporary = Path(name)
        try:
            digest = hashlib.sha256()
            count = 0
            with os.fdopen(descriptor, 'wb') as output:
                request = Request(url, headers={'User-Agent': 'NHFL-Verified-Build/1.0'})
                with opener.open(request, timeout=90) as response:
                    if urlsplit(response.geturl()).scheme != 'https':
                        raise BuildInputError('insecure_build_input_response')
                    while chunk := response.read(1024 * 1024):
                        count += len(chunk)
                        if count > MAX_BYTES:
                            raise BuildInputError('build_input_size_limit')
                        digest.update(chunk)
                        output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != expected_sha256:
                raise BuildInputError('downloaded_build_input_digest_mismatch')
            _check_path(destination)
            try:
                # The completed candidate becomes visible in one no-clobber step.
                os.link(temporary, destination)
            except FileExistsError:
                if _digest(destination) != expected_sha256:
                    raise BuildInputError('concurrent_build_input_conflict') from None
            return
        except (HTTPError, URLError, TimeoutError, ConnectionError) as exc:
            retryable = not isinstance(exc, HTTPError) or exc.code in {408, 429, 500, 502, 503, 504}
            if not retryable or attempt + 1 == attempts:
                raise BuildInputError('build_input_download_unavailable') from None
            time.sleep(2 * (attempt + 1))
        finally:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        acquire(args.url, args.destination, args.sha256)
    except (BuildInputError, OSError) as exc:
        print(str(exc) if isinstance(exc, BuildInputError) else 'build_input_io_unavailable')
        return 1
    print('Pinned build input verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
