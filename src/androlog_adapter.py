"""Fail-closed adapter from AndroLog-style raw probe logs to count reports.

This independently authored adapter recognizes the public AndroLog probe labels
(`STATEMENT`, `METHOD`, `CLASS`, `ACTIVITY`, `SERVICE`,
`BROADCASTRECEIVER`, and `CONTENTPROVIDER`).  One input file is one bounded
execution session.  A user-supplied exact probe map translates normalized probe
keys to event indices in the declared finite model.  The adapter preserves
order and repetition inside a session, rejects unknown or malformed probes,
and deduplicates identical complete normalized event traces before constructing distinct-trace counts.

It does not instrument APKs, authenticate logcat, infer trigger semantics, or
claim that the supplied synthetic fixtures came from Android execution.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path
import io
import json
import os
import re
import stat
from typing import Iterable, Mapping, Sequence

MAX_SESSION_BYTES = 4 * 1024 * 1024
MAX_SESSION_FILES = 4096
MAX_TOTAL_SESSION_BYTES = 64 * 1024 * 1024
MAX_CONFIG_BYTES = 4 * 1024 * 1024

from .checker import InvalidCertificate, validate_model
from .producer import advance, enumerate_model, initial, signature

PROBE_TYPES = (
    "STATEMENT",
    "METHOD",
    "CLASS",
    "ACTIVITY",
    "SERVICE",
    "BROADCASTRECEIVER",
    "CONTENTPROVIDER",
)
_TYPE_RE = re.compile(r"\b([A-Z][A-Z0-9_]*)=")


class InvalidLog(ValueError):
    pass


def _validate_model(model: dict) -> None:
    try:
        validate_model(model)
    except InvalidCertificate as exc:
        raise InvalidLog(f"invalid trigger model: {exc}") from exc


def _validate_log_identifier(log_identifier: str) -> None:
    if (not isinstance(log_identifier, str) or not log_identifier or len(log_identifier) > 256
            or "\x00" in log_identifier or "\n" in log_identifier or "\r" in log_identifier):
        raise InvalidLog("invalid log identifier")


def _open_regular_binary(path: Path, *, max_bytes: int, label: str):
    """Open a bounded regular file without following links or blocking on FIFOs.

    On POSIX, ``O_NONBLOCK`` makes a no-writer FIFO open return immediately; the
    descriptor-level ``fstat`` then rejects it. ``O_NOFOLLOW`` and the same
    ``fstat`` retain final-component symlink and replacement-race protection.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise InvalidLog(f"invalid {label} size limit")
    flags = os.O_RDONLY
    if hasattr(os, "O_NONBLOCK"):
        flags |= os.O_NONBLOCK
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    elif path.is_symlink():
        raise InvalidLog(f"{label} must be a regular, non-symlink file")
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise InvalidLog(f"cannot open {label}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise InvalidLog(f"{label} must be a regular, non-symlink file")
        if info.st_size > max_bytes:
            raise InvalidLog(f"{label} exceeds {max_bytes} bytes")
        return descriptor, info.st_size
    except Exception:
        os.close(descriptor)
        raise


def _validate_probe_map(probe_map: Mapping[str, int], event_count: int) -> None:
    """Validate the serialized map without asserting its semantic faithfulness."""
    if not isinstance(probe_map, Mapping):
        raise InvalidLog("probe map must be a mapping")
    values: list[int] = []
    for key, value in probe_map.items():
        if not isinstance(key, str) or "=" not in key or "\x00" in key or "\n" in key or "\r" in key:
            raise InvalidLog("probe map keys must be normalized text assignments")
        probe_type, payload = key.split("=", 1)
        if probe_type not in PROBE_TYPES or not payload or len(payload) > 8192:
            raise InvalidLog("probe map contains an unsupported or invalid key")
        if probe_type == "STATEMENT" and "|" in payload:
            raise InvalidLog("statement probe-map keys must exclude pipe metadata")
        if type(value) is not int or not 0 <= value < event_count:
            raise InvalidLog("probe map values must name declared events")
        values.append(value)
    if len(set(values)) != len(values):
        raise InvalidLog("probe map must be injective")


def _normalize_probe(line: str, log_identifier: str) -> str | None:
    """Return one canonical probe key, or None for an unrelated line.

    This mirrors the public parser's distinction for statements: metadata after
    the first pipe is not part of the statement identity.  For all other probe
    types the suffix is retained after surrounding whitespace is removed.
    """
    if not isinstance(line, str) or "\x00" in line:
        raise InvalidLog("non-text or NUL-containing line")
    if log_identifier not in line:
        return None
    identifier_at = line.find(log_identifier)
    match = _TYPE_RE.search(line, identifier_at + len(log_identifier))
    if match is None:
        raise InvalidLog("identifier-bearing line has no probe assignment")
    probe_type = match.group(1)
    if probe_type not in PROBE_TYPES:
        raise InvalidLog("unsupported probe type: " + probe_type)
    value = line[match.end():].strip()
    if probe_type == "STATEMENT":
        value = value.split("|", 1)[0].strip()
    if not value or len(value) > 8192 or "\n" in value or "\r" in value:
        raise InvalidLog("invalid probe payload")
    return f"{probe_type}={value}"


def parse_session(lines: Iterable[str], log_identifier: str, probe_map: Mapping[str, int]) -> tuple[int, ...]:
    _validate_log_identifier(log_identifier)
    trace: list[int] = []
    for line_number, line in enumerate(lines, start=1):
        key = _normalize_probe(line.rstrip("\n"), log_identifier)
        if key is None:
            continue
        if key not in probe_map:
            raise InvalidLog(f"unknown probe at line {line_number}: {key}")
        index = probe_map[key]
        if type(index) is not int or index < 0:
            raise InvalidLog("probe map values must be nonnegative integers")
        trace.append(index)
    return tuple(trace)


def _parse_session_file_with_size(
    path: Path, log_identifier: str, probe_map: Mapping[str, int], *,
    max_bytes: int = MAX_SESSION_BYTES,
) -> tuple[tuple[int, ...], int]:
    descriptor, _ = _open_regular_binary(path, max_bytes=max_bytes, label="session file")
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            payload = handle.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise InvalidLog(f"session file exceeds {max_bytes} bytes")
        lines = io.StringIO(payload.decode("utf-8", errors="strict"), newline=None)
        return parse_session(lines, log_identifier, probe_map), len(payload)
    except (OSError, UnicodeError) as exc:
        raise InvalidLog(f"cannot read session file as strict UTF-8: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def parse_session_file(path: Path, log_identifier: str, probe_map: Mapping[str, int]) -> tuple[int, ...]:
    trace, _ = _parse_session_file_with_size(path, log_identifier, probe_map)
    return trace


def _evaluate_trace(model: dict, trace: Sequence[int]) -> tuple[tuple[int, ...], tuple[int, int]]:
    if len(trace) > model["horizon"] or len(trace) < model["min_length"]:
        raise InvalidLog("session length outside declared model")
    state = initial(model)
    for position, index in enumerate(trace):
        if type(index) is not int or not 0 <= index < len(model["events"]):
            raise InvalidLog(f"event index outside alphabet at position {position}")
        nxt = advance(model, state, model["events"][index])
        if nxt is None:
            raise InvalidLog("session violates within-trace context lock")
        state = nxt
    bucket = (state[1], len(trace) % model["report_modulus"])
    return signature(model, state), bucket


def adapt_sessions(
    model: dict,
    sessions: Sequence[Sequence[int]],
) -> dict:
    """Construct a distinct-trace report and exact class allocation."""
    _validate_model(model)
    try:
        dag = enumerate_model(model)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidLog(f"model enumeration rejected: {exc}") from exc
    class_index = {tuple(value): i for i, value in enumerate(dag["classes"])}
    bucket_index = {tuple(value): i for i, value in enumerate(dag["buckets"])}
    canonical = [tuple(trace) for trace in sessions]
    distinct = sorted(set(canonical), key=lambda word: (len(word), word))
    allocation = [[0 for _ in dag["classes"]] for _ in dag["buckets"]]
    for trace in distinct:
        semantic, bucket = _evaluate_trace(model, trace)
        if semantic not in class_index or bucket not in bucket_index:
            raise InvalidLog("session is not represented by source enumeration")
        y = bucket_index[bucket]
        c = class_index[semantic]
        allocation[y][c] += 1
        if allocation[y][c] > dag["capacity"][y][c]:
            raise InvalidLog("distinct sessions exceed source cell capacity")
    counts = [sum(row) for row in allocation]
    duplicate_occurrences = sum(multiplicity - 1 for multiplicity in Counter(canonical).values())
    return {
        "input_sessions": len(canonical),
        "distinct_traces": len(distinct),
        "duplicate_sessions_removed": duplicate_occurrences,
        "distinct_words": [list(trace) for trace in distinct],
        "buckets": dag["buckets"],
        "classes": dag["classes"],
        "count_report": counts,
        "allocation": allocation,
        "capacity": dag["capacity"],
    }


def adapt_directory(
    model: dict,
    directory: Path,
    log_identifier: str,
    probe_map: Mapping[str, int],
    *,
    max_session_bytes: int = MAX_SESSION_BYTES,
    max_session_files: int = MAX_SESSION_FILES,
    max_total_session_bytes: int = MAX_TOTAL_SESSION_BYTES,
) -> dict:
    _validate_model(model)
    _validate_log_identifier(log_identifier)
    _validate_probe_map(probe_map, len(model["events"]))
    for limit_name, limit in (("per-file byte", max_session_bytes),
                              ("file-count", max_session_files),
                              ("aggregate byte", max_total_session_bytes)):
        if type(limit) is not int or limit <= 0:
            raise InvalidLog(f"invalid {limit_name} limit")
    if not directory.is_dir() or directory.is_symlink():
        raise InvalidLog("session directory missing or is a symlink")
    try:
        entries = sorted(directory.iterdir())
    except OSError as exc:
        raise InvalidLog(f"cannot enumerate session directory: {exc}") from exc
    if not entries or len(entries) > max_session_files:
        raise InvalidLog(f"session directory must contain 1..{max_session_files} entries")
    sessions: list[tuple[int, ...]] = []
    total_bytes = 0
    for path in entries:
        trace, size = _parse_session_file_with_size(
            path, log_identifier, probe_map, max_bytes=max_session_bytes
        )
        total_bytes += size
        if total_bytes > max_total_session_bytes:
            raise InvalidLog(
                f"session directory aggregate input exceeds {max_total_session_bytes} bytes"
            )
        sessions.append(trace)
    result = adapt_sessions(model, sessions)
    result["files"] = [path.name for path in entries]
    result["input_bytes"] = total_bytes
    return result



def _load_json_object(path: Path, label: str) -> dict:
    descriptor, _ = _open_regular_binary(path, max_bytes=MAX_CONFIG_BYTES, label=label)
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = -1
            payload = handle.read(MAX_CONFIG_BYTES + 1)
        if len(payload) > MAX_CONFIG_BYTES:
            raise InvalidLog(f"{label} exceeds {MAX_CONFIG_BYTES} bytes")
        value = json.loads(payload.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidLog(f"cannot read {label}: {exc}") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if type(value) is not dict:
        raise InvalidLog(f"{label} must be a JSON object")
    return value


def _cli() -> int:
    """Small offline converter for authored or lawfully acquired session logs."""
    import argparse
    from .checker import check
    from .producer import certify

    parser = argparse.ArgumentParser(
        description="Convert bounded AndroLog-style session files into a bound count report and certificate."
    )
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--probe-map", type=Path, required=True)
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--log-identifier", default="ANDROLOG")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise SystemExit("output must not already exist or be a symlink")
    model = _load_json_object(args.model, "model")
    probe_map = _load_json_object(args.probe_map, "probe map")
    adapted = adapt_directory(model, args.sessions, args.log_identifier, probe_map)
    certificate = certify(model, adapted["count_report"])
    replay = check(model, adapted["count_report"], certificate)
    payload = {
        "provenance": {
            "contract": "one input file is one bounded session; identical complete normalized event traces are deduplicated",
            "log_identifier": args.log_identifier,
            "session_files": adapted["files"],
            "authentication": "not established by this adapter",
        },
        "adapted_report": adapted,
        "certificate": certificate,
        "checker_result": replay,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    except OSError as exc:
        raise SystemExit(f"cannot create output: {exc}") from exc
    print(json.dumps({
        "output": str(args.output),
        "distinct_traces": adapted["distinct_traces"],
        "count_report": adapted["count_report"],
        "spectrum": replay["spectrum"],
        "verdict": replay["verdict"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
