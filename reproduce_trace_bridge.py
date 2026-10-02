#!/usr/bin/env python3
"""Run the owned Java deserialization observation-gap study offline.

This runner is deliberately separate from ``reproduce.py`` so the archived
seven scientific JSON files and five deterministic files remain immutable.
It accepts no serialized input, downloads nothing, uses one process at a time,
and writes only to a fresh output directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
if sys.version_info < (3, 9):
    raise RuntimeError("Python 3.9 or newer is required")
sys.path.insert(0, str(ROOT / "src"))

from checker import Checker
from java_trace_bridge import BLOCKING_FEATURES, map_observation
from oracle import exact

RUN_ENV_OVERRIDES = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "JAVA_TOOL_OPTIONS": "",
}
JVM_OPTIONS = ["-XX:ActiveProcessorCount=1", "-XX:+UseSerialGC", "-Xmx256m"]
JAVAC_OPTIONS = ["-proc:none"]
EXPECTED = {
    "plain-safe": "MAPPED",
    "plain-unsafe": "MAPPED",
    "shared-alias": "MAPPED",
    "cycle-callback-order": "UNKNOWN",
    "early-external-escape": "UNKNOWN",
    "read-resolve-external-alias": "UNKNOWN",
    "type-shape-mismatch": "UNKNOWN",
    "resolve-object-field-write-gap": "UNKNOWN",
    "failure-closed": "UNKNOWN",
    "failure-after-external-escape": "UNKNOWN",
    "missing-field": "UNKNOWN",
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def portable_command(command: list[str]) -> list[str]:
    """Normalize environment-specific executable and temporary paths in records."""
    normalized: list[str] = []
    for item in command:
        if item == sys.executable:
            normalized.append("python3")
            continue
        path = Path(item)
        if path.is_absolute():
            try:
                normalized.append(path.relative_to(ROOT).as_posix())
                continue
            except ValueError:
                parts = path.parts
                marker = next((i for i, part in enumerate(parts)
                               if part.startswith("java-trace-bridge-")), None)
                if marker is not None:
                    suffix = Path(*parts[marker + 1:]).as_posix()
                    normalized.append("<temporary>" + ("/" + suffix if suffix else ""))
                    continue
        normalized.append(item)
    return normalized


def require_fresh(path: Path) -> None:
    if path.exists() and any(path.iterdir()):
        raise ValueError("--out must not exist or must be empty")
    path.mkdir(parents=True, exist_ok=True)


def run(command: list[str], *, cwd: Path, stdout: Path | None = None,
        timeout: int = 60, combine_stderr: bool = False) -> dict[str, object]:
    env = {**os.environ, **RUN_ENV_OVERRIDES}
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=env,
    )
    if stdout is not None:
        # Some tools (notably unittest) write normal progress to stderr.  Keep
        # JSONL observation files stdout-only, but allow a caller to request a
        # combined durable diagnostic log.
        stdout.write_text(proc.stdout + (proc.stderr if combine_stderr else ""), encoding="utf-8")
    record = {
        "command": portable_command(command),
        "cwd": "." if cwd.resolve() == ROOT else cwd.name,
        "returncode": proc.returncode,
        "stdout_file": stdout.name if stdout is not None else None,
        "stderr": proc.stderr,
    }
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(command)}\n{proc.stderr}")
    return record


def probe(command: list[str]) -> dict[str, object]:
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=10,
            check=False,
            env={**os.environ, **RUN_ENV_OVERRIDES},
        )
        return {"available": True, "returncode": proc.returncode, "output": proc.stdout.strip()}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


def selected_java_properties(output: str) -> dict[str, str]:
    wanted = {
        "java.vendor", "java.version", "java.runtime.version", "java.vm.name",
        "java.vm.vendor", "java.vm.version", "java.specification.version", "os.arch",
    }
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" not in line:
            continue
        key, value = (piece.strip() for piece in line.split("=", 1))
        if key in wanted:
            values[key] = value
    return values


def compact_probe(probe_result: dict[str, object]) -> dict[str, object]:
    """Retain exact version identifiers without cwd/home/temp path disclosure."""
    if not probe_result.get("available"):
        return dict(probe_result)
    lines: list[str] = []
    for line in str(probe_result.get("output", "")).splitlines():
        stripped = line.strip()
        if (stripped.startswith("openjdk version") or stripped.startswith("java version") or
                stripped.startswith("OpenJDK Runtime Environment") or
                stripped.startswith("OpenJDK 64-Bit Server VM") or
                stripped.startswith("javac ")):
            lines.append(stripped)
    return {"available": True, "returncode": probe_result.get("returncode"),
            "version_output": "\n".join(lines)}


def os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        key, value = line.split("=", 1)
        if key in {"ID", "NAME", "VERSION", "VERSION_ID"}:
            values[key] = value.strip().strip('"')
    return values


def aggregate_summary(paths: list[Path]) -> dict[str, object]:
    digest = hashlib.sha256()
    names: list[str] = []
    total = 0
    for path in sorted(set(paths)):
        relative = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        names.append(relative)
        total += len(content)
        digest.update(relative.encode("utf-8")); digest.update(b"\0")
        digest.update(content); digest.update(b"\0")
    return {"files": names, "file_count": len(names), "bytes": total, "sha256": digest.hexdigest()}


def environment_record() -> dict[str, object]:
    java = probe(["java", "-XshowSettings:properties", "-version"])
    javac = probe(["javac", "-version"])
    code = list((ROOT / "src").glob("*.py")) + list((ROOT / "bridge_tests").glob("*.py"))
    code += list((ROOT / "java").rglob("*.java")) + [Path(__file__).resolve()]
    return {
        "schema": "java-trace-bridge-environment-v1",
        "record_scope": "this trace-bridge run only; not a reconstruction of any earlier environment",
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "platform": {
            "system": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "pointer_bits": 8 * struct.calcsize("P"),
            "sys_platform": sys.platform, "os_release": os_release(),
        },
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(), "version_string": sys.version,
            "minimum_required": "3.9",
        },
        "java": {
            "version_probe": compact_probe(java),
            "selected_properties": selected_java_properties(str(java.get("output", ""))),
            "javac_probe": compact_probe(javac),
        },
        "execution": {
            "workers": 1, "java_children_sequential": True,
            "jvm_options": JVM_OPTIONS, "javac_options": JAVAC_OPTIONS,
            "environment_overrides": RUN_ENV_OVERRIDES,
            "network_used": False, "external_serialized_input": False,
        },
        "code_input_summary": aggregate_summary(code),
    }


def missing_field_observation(raw: dict[str, object]) -> dict[str, object]:
    if raw != {
        "case": "missing-field", "success": True, "defaulted_next": True,
        "value": 7, "next_is_null": True,
    }:
        raise AssertionError(f"unexpected class-evolution observation: {raw}")
    features = {name: False for name in BLOCKING_FEATURES}
    features["missing_field"] = True
    return {
        "case": "missing-field",
        "success": True,
        "exception": None,
        "events": ["ObjectInputStream.GetField.defaulted(next)=true"],
        "constructor_calls_during_read": None,
        "features": features,
        "snapshot": None,
        "facts": {
            "defaulted_next": True,
            "value": 7,
            "next_is_null": True,
            "class_evolution": "v1 stream read by v2 class with same serialVersionUID",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    require_fresh(out)

    for binary in ("java", "javac"):
        if shutil.which(binary) is None:
            raise RuntimeError(f"{binary} is required; nothing is downloaded")

    write_json(out / "environment.json", environment_record())
    command_records: list[dict[str, object]] = []

    with tempfile.TemporaryDirectory(prefix="java-trace-bridge-") as temporary:
        temp = Path(temporary)
        main_classes = temp / "main-classes"; main_classes.mkdir()
        command_records.append(run(
            ["javac", *["-J" + flag for flag in JVM_OPTIONS], *JAVAC_OPTIONS,
             "-d", str(main_classes), str(ROOT / "java" / "DeserializationTraceHarness.java")],
            cwd=ROOT, stdout=out / "java-main-compile.txt",
        ))
        command_records.append(run(
            ["java", *JVM_OPTIONS, "-cp", str(main_classes), "DeserializationTraceHarness"],
            cwd=ROOT, stdout=out / "java-main-observations.jsonl",
        ))

        old_classes = temp / "old-classes"; old_classes.mkdir()
        new_classes = temp / "new-classes"; new_classes.mkdir()
        stream = temp / "evolving-node.ser"
        command_records.append(run(
            ["javac", *["-J" + flag for flag in JVM_OPTIONS], *JAVAC_OPTIONS,
             "-d", str(old_classes),
             str(ROOT / "java" / "evolution" / "v1" / "evolution" / "EvolvingNode.java"),
             str(ROOT / "java" / "evolution" / "v1" / "WriteOld.java")],
            cwd=ROOT, stdout=out / "java-evolution-v1-compile.txt",
        ))
        command_records.append(run(
            ["java", *JVM_OPTIONS, "-cp", str(old_classes), "WriteOld", str(stream)],
            cwd=ROOT, stdout=out / "java-evolution-write.txt",
        ))
        command_records.append(run(
            ["javac", *["-J" + flag for flag in JVM_OPTIONS], *JAVAC_OPTIONS,
             "-d", str(new_classes),
             str(ROOT / "java" / "evolution" / "v2" / "evolution" / "EvolvingNode.java"),
             str(ROOT / "java" / "evolution" / "v2" / "ReadNew.java")],
            cwd=ROOT, stdout=out / "java-evolution-v2-compile.txt",
        ))
        command_records.append(run(
            ["java", *JVM_OPTIONS, "-cp", str(new_classes), "ReadNew", str(stream)],
            cwd=ROOT, stdout=out / "java-evolution-observation.jsonl",
        ))

    base = [json.loads(line) for line in (out / "java-main-observations.jsonl").read_text().splitlines()]
    raw_missing = json.loads((out / "java-evolution-observation.jsonl").read_text())
    observations = base + [missing_field_observation(raw_missing)]
    cases = [item["case"] for item in observations]
    if cases != list(EXPECTED):
        raise AssertionError(f"case order changed: {cases}")

    with (out / "java-traces.jsonl").open("w", encoding="utf-8") as stream:
        for item in observations:
            stream.write(json.dumps(item, sort_keys=True) + "\n")

    results: list[dict[str, object]] = []
    mapped = unknown = safe = unsafe = 0
    for observation in observations:
        case = observation["case"]
        bridge = map_observation(observation)
        if bridge.status != EXPECTED[case]:
            raise AssertionError(f"{case}: expected {EXPECTED[case]}, got {bridge.status}")
        entry: dict[str, object] = {"case": case, "bridge": bridge.as_json()}
        if bridge.status == "MAPPED":
            mapped += 1
            assert bridge.heap is not None and bridge.roots is not None
            truth, live, _ = exact(bridge.heap, bridge.roots)
            try:
                Checker(bridge.heap, list(bridge.roots))
                admitted = True
            except ValueError:
                admitted = False
            if admitted != truth:
                raise AssertionError(f"{case}: checker admission disagrees with independent dense oracle")
            if truth: safe += 1
            else: unsafe += 1
            entry.update({"dense_oracle_safe": truth, "reachable": sorted(live),
                          "checker_initial_admission": "ACCEPT" if admitted else "REJECT"})
        else:
            unknown += 1
        results.append(entry)

    facts = {item["case"]: item["facts"] for item in observations}
    if any(item["constructor_calls_during_read"] != 0 for item in base):
        raise AssertionError("a serializable fixture constructor ran during read")
    required = {
        "shared-alias": facts["shared-alias"].get("alias_preserved") is True,
        "cycle-callback-order": facts["cycle-callback-order"].get("peer_seen_before_callback_exit") is True,
        "early-external-escape": facts["early-external-escape"].get("escaped_alias_is_returned_root") is True,
        "read-resolve-external-alias": facts["read-resolve-external-alias"].get("returned_preexisting_canonical") is True,
        "type-shape-mismatch": observations[6]["features"]["type_shape_mismatch"] is True,
        "resolve-object-field-write-gap": facts["resolve-object-field-write-gap"].get("field_write_events_observed") == 0,
        "failure-closed": facts["failure-closed"].get("external_alias_after_failure") is False,
        "failure-after-external-escape": facts["failure-after-external-escape"].get("external_alias_after_failure") is True,
        "missing-field": facts["missing-field"].get("defaulted_next") is True,
    }
    if not all(required.values()):
        raise AssertionError(f"negative control failed: {required}")

    write_json(out / "bridge-results.json", results)
    summary = {
        "schema": "java-trace-bridge-summary-v1",
        "route": "negative-result technical report",
        "cases": len(observations),
        "mapped": mapped,
        "unknown": unknown,
        "mapped_safe": safe,
        "mapped_unsafe": unsafe,
        "constructor_calls_during_read": sum(item["constructor_calls_during_read"] or 0 for item in base),
        "negative_controls": required,
        "all_expected_statuses_matched": True,
        "interpretation": (
            "MAPPED is a partial data translation for owned final snapshots. "
            "UNKNOWN marks traces for which passive ObjectInputStream observations do not establish "
            "the complete root/write premise. No JVM enforcement or constructor attestation is claimed."
        ),
    }
    write_json(out / "bridge-summary.json", summary)

    test_log = out / "bridge-unit-tests.txt"
    test_record = run(
        [sys.executable, "-m", "unittest", "discover", "-s", "bridge_tests", "-v"],
        cwd=ROOT, stdout=test_log, combine_stderr=True,
    )
    command_records.append(test_record)
    test_text = test_log.read_text(encoding="utf-8")
    match = re.search(r"Ran (\d+) tests?", test_text)
    test_count = int(match.group(1)) if match else None
    write_json(out / "bridge-unit-summary.json", {
        "schema": "java-trace-bridge-unit-summary-v1",
        "returncode": test_record["returncode"],
        "tests_run": test_count,
        "result": "PASS" if test_record["returncode"] == 0 and "OK" in test_text else "UNKNOWN",
        "log": test_log.name,
    })
    write_json(out / "commands.json", command_records)
    print(json.dumps({"status": "PASS", **summary}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, AssertionError, subprocess.TimeoutExpired) as exc:
        print(f"FAILED/UNKNOWN: {exc}", file=sys.stderr)
        raise SystemExit(2)
