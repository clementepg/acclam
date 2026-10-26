"""Resolve repository evidence and explicitly allowlisted, hash-pinned private sources.

ACCLAM_SOURCE_ROOT is a local attachment only. Never serialize its value into
the register, projection, reports, or URLs.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

QUEST = Path(__file__).resolve().parents[1]
WORKSPACE = QUEST.parents[1]


class SourceError(ValueError):
    pass


class MissingExternalSource(SourceError):
    pass


class SourceHashMismatch(SourceError):
    pass


def relative_path(value):
    if (not isinstance(value, str) or not value or '\\' in value or '\x00' in value
            or PurePosixPath(value).is_absolute() or PureWindowsPath(value).drive
            or any(part in ('', '.', '..') for part in value.split('/'))):
        raise SourceError(f'Path escapes workspace or is not a canonical relative path: {value!r}')
    return value


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class SourceResolver:
    def __init__(self, workspace=WORKSPACE, manifest=None, external_root=None):
        self.workspace = Path(workspace).resolve()
        self.external_root = (Path(external_root).resolve() if external_root else None)
        self._hashes = {}
        manifest = Path(manifest) if manifest else self.workspace / 'work/launch-quest/EXTERNAL_SOURCES.json'
        self.external = {}
        if manifest.exists():
            data = json.loads(manifest.read_text(encoding='utf-8-sig'))
            if data.get('schemaVersion') != 1 or not isinstance(data.get('files'), list):
                raise SourceError('Unsupported external source manifest')
            for entry in data['files']:
                key = relative_path(entry['path'])
                if key in self.external or not re.fullmatch('[0-9a-f]{64}', entry.get('sha256', '')):
                    raise SourceError(f'Invalid or duplicate external source metadata: {key}')
                if entry.get('reason') != 'private_client_source':
                    raise SourceError(f'Unsupported external source reason: {key}')
                self.external[key] = entry['sha256']

    @staticmethod
    def inside(base, relative):
        target = (base / relative).resolve()
        if not target.is_relative_to(base):
            raise SourceError(f'Path escapes workspace via symbolic link: {relative}')
        return target

    def resolve(self, relative):
        relative_path(relative)
        target = self.inside(self.workspace, relative)
        if not target.is_file():
            if relative not in self.external:
                raise SourceError(f'Missing file: {relative}')
            if not self.external_root:
                raise MissingExternalSource(f'Private dependency unavailable: {relative}; attach ACCLAM_SOURCE_ROOT for strict evidence validation')
            target = self.inside(self.external_root, relative)
            if not target.is_file():
                raise MissingExternalSource(f'Private dependency unavailable: {relative}; attached source root does not contain this file')
        if relative in self.external:
            stat = target.stat()
            fingerprint = (str(target), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            actual = self._hashes.get(fingerprint)
            if actual is None:
                actual = self._hashes[fingerprint] = digest(target)
            if actual != self.external[relative]:
                raise SourceHashMismatch(f'Private source hash mismatch: {relative}; preserve the pinned source before proceeding')
        return target


def configured_resolver():
    return SourceResolver(external_root=os.environ.get('ACCLAM_SOURCE_ROOT'))
