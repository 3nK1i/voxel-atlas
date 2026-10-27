"""6J-C2: isolated, task-pinned MRI model-asset qualification; no inference."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from hashlib import sha256
import json
import importlib.util
import os
from pathlib import Path
import re
import subprocess
from typing import Callable

from .mri_runtime_qualification import MRIRuntimeQualifier

PROVIDER_VERSION = "2.18.0"
MRI_TASK = "total_mr"
# TotalSegmentator v2.18.0 map_tasks_config.py and totalseg_download_weights.py.
MRI_DATASETS = {
    850: "Dataset850_TotalSegMRI_part1_organs_1088subj",
    851: "Dataset851_TotalSegMRI_part2_muscles_1088subj",
    852: "Dataset852_TotalSegMRI_total_3mm_1088subj",
    853: "Dataset853_TotalSegMRI_total_6mm_1088subj",
}
MRI_DOWNLOAD_TASKS = ("total_mr", "total_fast_mr")
MAX_ASSET_FILES = 10000
MAX_MANIFEST_BYTES = 4 * 1024 * 1024
MAX_PROBE_BYTES = 4096
_FILE_DIGEST = re.compile(r"^[a-f0-9]{64}$")


class MRIAssetError(ValueError):
    """Non-sensitive, fail-closed MRI weight qualification failure."""


@dataclass(frozen=True)
class MRIAssetPaths:
    root: Path
    home: Path
    weights: Path
    config: Path
    manifest: Path


def paths_for(data_dir: Path) -> MRIAssetPaths:
    if not isinstance(data_dir, Path) or data_dir.is_symlink() or not data_dir.is_dir():
        raise MRIAssetError("VoxelAtlas data root is unavailable or unsafe")
    root = data_dir.resolve() / "segmentation" / "providers" / "totalsegmentator-mri" / PROVIDER_VERSION
    return MRIAssetPaths(root, root / "home", root / "weights", root / "home" / "config.json", root / "weights-manifest.json")


def _regular(path: Path) -> bool:
    return not path.is_symlink() and path.is_file()


def _canonical(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("utf-8")


# Isolated child: imports only task maps from the user's installed pinned version,
# never calls download or segmentation code. No raw paths or exceptions are emitted.
_INSTALLED_MAP_PROBE = r'''
import importlib.metadata as metadata
import json
from totalsegmentator.map_tasks_config import TASK_CONFIGS, TASK_ID_WEIGHTS_CONFIGS
from pathlib import Path
import ast
import importlib.util
expected = {
  850: "Dataset850_TotalSegMRI_part1_organs_1088subj",
  851: "Dataset851_TotalSegMRI_part2_muscles_1088subj",
  852: "Dataset852_TotalSegMRI_total_3mm_1088subj",
  853: "Dataset853_TotalSegMRI_total_6mm_1088subj",
}
mode = TASK_CONFIGS["total_mr"]["sub_modes"]
actual = (tuple(mode["default"]["task_id"]), mode["fast"]["task_id"], mode["fastest"]["task_id"])
folders_match = all(TASK_ID_WEIGHTS_CONFIGS[key].get("foldername") == folder and
                    TASK_ID_WEIGHTS_CONFIGS[key].get("version") == "v2.5.0-weights"
                    for key, folder in expected.items())
spec = importlib.util.find_spec("totalsegmentator.bin.totalseg_download_weights")
cli_ids = None
if spec is not None and spec.origin is not None:
    for statement in ast.parse(Path(spec.origin).read_text(encoding="utf-8")).body:
        if (isinstance(statement, ast.Assign) and
                any(isinstance(target, ast.Name) and target.id == "TASK_TO_ID"
                    for target in statement.targets)):
            cli_ids = ast.literal_eval(statement.value)
            break
print(json.dumps({"schema": 1, "version": metadata.version("TotalSegmentator"),
  "mode_ids": [list(actual[0]), actual[1], actual[2]], "folders_match": folders_match,
  "download_ids_match": cli_ids is not None and cli_ids.get("total_mr") == [850, 851] and
  cli_ids.get("total_fast_mr") == [852, 853]},
  separators=(",", ":")))
'''.strip()


def qualify_installed_mri_mapping(python_executable: str, *, runner: Callable[..., object] = subprocess.run) -> bool:
    if (not isinstance(python_executable, str) or not python_executable.strip() or
            len(python_executable) > 4096 or any(ord(c) < 32 for c in python_executable)):
        return False
    try:
        result = runner([python_executable, "-I", "-c", _INSTALLED_MAP_PROBE],
                        check=False, shell=False, capture_output=True, text=True, timeout=40)
        if result.returncode != 0 or not isinstance(result.stdout, str) or len(result.stdout.encode("utf-8")) > MAX_PROBE_BYTES:
            return False
        lines = result.stdout.strip().splitlines()
        payload = json.loads(lines[-1])
        return (type(payload) is dict and type(payload.get("schema")) is int and
                payload["schema"] == 1 and payload.get("version") == PROVIDER_VERSION and
                payload.get("mode_ids") == [[850, 851], 852, 853] and
                payload.get("folders_match") is True and payload.get("download_ids_match") is True)
    except (OSError, subprocess.SubprocessError, IndexError, ValueError, TypeError, UnicodeError):
        return False


def require_mri_runtime_and_mapping(python_executable: str) -> None:
    report = MRIRuntimeQualifier().qualify(python_executable)
    if not report.runtime_qualified or report.execution_ready or not qualify_installed_mri_mapping(python_executable):
        raise MRIAssetError("MRI runtime or installed model-task mapping is unqualified")


def _guard_hierarchy(paths: MRIAssetPaths) -> None:
    for item in (paths.root.parent.parent.parent, paths.root.parent.parent, paths.root.parent,
                 paths.root, paths.home, paths.weights):
        if item.is_symlink() or (item.exists() and not item.is_dir()):
            raise MRIAssetError("MRI asset directory hierarchy is unsafe")


def _require_no_links(path: Path, root: Path) -> None:
    if path.is_symlink() or (path.exists() and path.is_file() and path == root):
        raise MRIAssetError("MRI asset location is unsafe")
    relative = path.relative_to(root)
    cursor = root
    if cursor.is_symlink():
        raise MRIAssetError("MRI asset location is unsafe")
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise MRIAssetError("MRI asset location is unsafe")


def prepare_mri_root(paths: MRIAssetPaths) -> None:
    # Keep MRI weights isolated from the CT 'totalsegmentator/2.18.0' directory.
    _guard_hierarchy(paths)
    for location in (paths.root.parent.parent.parent, paths.root.parent.parent, paths.root.parent,
                     paths.root, paths.home, paths.weights):
        if location.is_symlink() or (location.exists() and not location.is_dir()):
            raise MRIAssetError("MRI asset location is unsafe")
        location.mkdir(mode=0o700, parents=False, exist_ok=True)
    for location in (paths.root, paths.home, paths.weights):
        os.chmod(location, 0o700)
    if paths.config.is_symlink() or (paths.config.exists() and not paths.config.is_file()):
        raise MRIAssetError("MRI provider configuration path is unsafe")
    if not paths.config.exists():
        content = _canonical({"totalseg_id": "voxelatlas-mri-controlled", "send_usage_stats": False,
                              "prediction_counter": 0, "statistics_disclaimer_shown": True}) + b"\n"
        descriptor = os.open(paths.config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)


def mri_environment(paths: MRIAssetPaths) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update({"TOTALSEG_HOME_DIR": str(paths.home),
                        "TOTALSEG_WEIGHTS_PATH": str(paths.weights),
                        "nnUNet_results": str(paths.weights),
                        "nnUNet_raw": str(paths.root / "nnunet-raw"),
                        "nnUNet_preprocessed": str(paths.root / "nnunet-preprocessed"),
                        "PYTHONNOUSERSITE": "1"})
    return environment


def download_commands(python_executable: str) -> tuple[tuple[str, ...], ...]:
    if not isinstance(python_executable, str) or not python_executable.strip() or any(ord(c) < 32 for c in python_executable):
        raise MRIAssetError("MRI runtime Python is invalid")
    return tuple((python_executable, "-I", "-m", "totalsegmentator.bin.totalseg_download_weights",
                  "--task", task) for task in MRI_DOWNLOAD_TASKS)


def _inventory(paths: MRIAssetPaths) -> dict[str, object]:
    _guard_hierarchy(paths)
    root = paths.weights
    if not root.is_dir() or root.is_symlink() or paths.root.is_symlink():
        raise MRIAssetError("MRI weights are unavailable or unsafe")
    expected = set(MRI_DATASETS.values())
    actual = set()
    try:
        children = sorted(root.iterdir())
        for folder in children:
            if folder.is_symlink() or not folder.is_dir() or folder.name not in expected:
                raise MRIAssetError("MRI weight directory inventory differs from the pinned task")
            actual.add(folder.name)
        if actual != expected:
            raise MRIAssetError("MRI weight datasets are incomplete")
        files = []
        total = 0
        for folder in children:
            _require_no_links(folder, root)
            present = set()
            for entry in sorted(folder.rglob("*"), key=lambda item: item.as_posix()):
                _require_no_links(entry, root)
                if entry.is_dir():
                    continue
                if not entry.is_file():
                    raise MRIAssetError("MRI weight archive has unsupported entries")
                rel = entry.relative_to(root).as_posix()
                if len(rel) > 1024 or len(files) >= MAX_ASSET_FILES:
                    raise MRIAssetError("MRI weight inventory exceeds limits")
                size = entry.stat().st_size
                if size <= 0:
                    raise MRIAssetError("MRI weight artifact is empty")
                digest = sha256()
                with entry.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        digest.update(chunk)
                files.append({"path": rel, "size": size, "sha256": digest.hexdigest()})
                total += size
                present.add(entry.name)
            if not {"dataset.json", "plans.json", "checkpoint_final.pth"}.issubset(present):
                raise MRIAssetError("MRI weight dataset lacks required nnU-Net artifacts")
    except OSError as exc:
        raise MRIAssetError("MRI weight inventory cannot be read") from exc
    return {"schema": 1, "provider": "TotalSegmentator", "version": PROVIDER_VERSION,
            "task": MRI_TASK, "mode_ids": {"default": [850, 851], "fast": [852], "fastest": [853]},
            "datasets": [MRI_DATASETS[key] for key in sorted(MRI_DATASETS)],
            "files": sorted(files, key=lambda item: item["path"]), "total_bytes": total}


def _manifest_content(body: dict[str, object]) -> dict[str, object]:
    return {**body, "manifest_sha256": sha256(_canonical(body)).hexdigest()}


def seal_mri_weights(paths: MRIAssetPaths) -> dict[str, object]:
    """Explicit post-acquisition operation; never silently reseals changed assets."""
    body = _inventory(paths)
    payload = _manifest_content(body)
    encoded = _canonical(payload) + b"\n"
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise MRIAssetError("MRI weight inventory manifest exceeds limits")
    if paths.manifest.is_symlink():
        raise MRIAssetError("MRI weight manifest path is unsafe")
    if paths.manifest.exists():
        if verify_mri_weights(paths) != payload:
            raise MRIAssetError("Previously sealed MRI weights differ")
        return payload
    temporary = paths.manifest.with_name("weights-manifest.json.tmp")
    if temporary.exists() or temporary.is_symlink():
        raise MRIAssetError("MRI weight manifest temporary path is unsafe")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        # Atomic visibility and exclusive first seal; never overwrite a manifest.
        os.link(temporary, paths.manifest, follow_symlinks=False)
    except OSError as exc:
        raise MRIAssetError("MRI weight manifest could not be sealed") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return payload


def verify_mri_weights(paths: MRIAssetPaths) -> dict[str, object]:
    """Read-only verification of all sealed file hashes before later execution."""
    _guard_hierarchy(paths)
    if not _regular(paths.manifest) or paths.manifest.stat().st_size > MAX_MANIFEST_BYTES:
        raise MRIAssetError("Sealed MRI weight manifest is unavailable")
    try:
        sealed = json.loads(paths.manifest.read_bytes())
    except (OSError, ValueError, UnicodeError) as exc:
        raise MRIAssetError("Sealed MRI weight manifest is unreadable") from exc
    body = _inventory(paths)
    expected = _manifest_content(body)
    if type(sealed) is not dict or sealed != expected:
        raise MRIAssetError("MRI weights changed after sealing or manifest was modified")
    return expected
