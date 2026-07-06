#!/usr/bin/env python3

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional


PDF_MAGIC = b"%PDF"
PDF_EOF = b"%%EOF"
BASE64_RE = re.compile(r"^[A-Za-z0-9+/=]+$")
PDF_HINT_RE = re.compile(r"JVBER[A-Za-z0-9+/=\s]{40,}")


@dataclass
class CandidateResult:
    source: str
    sequence: str
    component_count: int
    status: str = "FAIL"
    sha256: Optional[str] = None
    bytes_length: int = 0
    pdf_bytes: Optional[bytes] = None
    message: str = ""
    warnings: List[str] = field(default_factory=list)


@dataclass
class FileResult:
    path: str
    status: str
    message: str
    candidates: List[CandidateResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    pdf_hashes: List[str] = field(default_factory=list)


def get_all_content_blocks(file_path: Path) -> List[str]:
    text = file_path.read_text(errors="ignore")

    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [text]

    contents = [elem.text for elem in root.iter() if elem.tag == "content" and elem.text]
    return contents or [text]


def parse_obx_line(line: str) -> Optional[dict]:
    if not line.startswith("OBX|"):
        return None

    fields = line.rstrip("\r\n").split("|")
    if len(fields) <= 5:
        return None

    return {
        "sequence": fields[1].strip(),
        "value_type": fields[2].strip(),
        "obx3": fields[3].strip() if len(fields) > 3 else "",
        "obx4": fields[4].strip() if len(fields) > 4 else "",
        "value": fields[5].strip(),
        "raw": line.rstrip("\r\n"),
    }


def extract_ed_records(file_path: Path) -> List[dict]:
    records = []
    for content in get_all_content_blocks(file_path):
        for line in content.splitlines():
            parsed = parse_obx_line(line.strip())
            if parsed and parsed["value_type"] == "ED":
                records.append(parsed)
    return records


def looks_like_base64(value: str) -> bool:
    compact = re.sub(r"\s+", "", value)
    return bool(compact) and len(compact) % 4 == 0 and bool(BASE64_RE.fullmatch(compact))


def normalize_component(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def extract_payload_from_components(components: List[str]) -> tuple[Optional[str], List[str]]:
    warnings = []
    if len(components) < 5:
        warnings.append("ED components < 5")

    standard_payload = normalize_component(components[4]) if len(components) >= 5 else ""
    encoding = components[3].strip().upper() if len(components) >= 4 else ""
    subtype = components[2].strip().lower() if len(components) >= 3 else ""
    type_of_data = components[1].strip().lower() if len(components) >= 2 else ""

    if subtype and subtype not in {"pdf", "application/pdf"}:
        warnings.append(f"Unexpected ED subtype: {components[2].strip()}")
    if not subtype:
        warnings.append("Missing ED subtype")
    if type_of_data and type_of_data not in {"application", "multipart", "ap", "document"}:
        warnings.append(f"Unexpected ED type: {components[1].strip()}")
    if encoding and encoding not in {"BASE64", "A"}:
        warnings.append(f"Unexpected ED encoding: {components[3].strip()}")
    if not encoding:
        warnings.append("Missing ED encoding")

    if standard_payload and looks_like_base64(standard_payload):
        return standard_payload, warnings

    for index, part in enumerate(components):
        cleaned = normalize_component(part)
        if cleaned.startswith("JVBER") and looks_like_base64(cleaned):
            warnings.append(f"Recovered payload from ED component {index + 1}")
            return cleaned, warnings

    joined = "^".join(components)
    match = PDF_HINT_RE.search(joined)
    if match:
        payload = normalize_component(match.group(0))
        if looks_like_base64(payload):
            warnings.append("Recovered payload from fuzzy ED scan")
            return payload, warnings

    return None, warnings


def group_records_for_reassembly(records: List[dict]) -> List[dict]:
    groups = []
    current = None

    for record in records:
        components = record["value"].split("^")
        payload, warnings = extract_payload_from_components(components)
        key = (record["obx3"], record["obx4"])

        if payload:
            groups.append(
                {
                    "source": "single",
                    "sequence": record["sequence"],
                    "payload": payload,
                    "warnings": warnings,
                    "component_count": len(components),
                }
            )
            current = None
            continue

        candidate_segment = normalize_component(components[-1] if components else record["value"])
        if not candidate_segment:
            current = None
            continue

        if current and current["key"] == key:
            current["segments"].append(candidate_segment)
            current["sequences"].append(record["sequence"])
        else:
            if current:
                groups.append(finalize_group(current))
            current = {
                "key": key,
                "segments": [candidate_segment],
                "sequences": [record["sequence"]],
                "warnings": warnings + ["Attempted multi-OBX reassembly"],
                "component_count": len(components),
            }

    if current:
        groups.append(finalize_group(current))

    return groups


def finalize_group(group: dict) -> dict:
    return {
        "source": "multi",
        "sequence": ",".join(group["sequences"]),
        "payload": "".join(group["segments"]),
        "warnings": group["warnings"],
        "component_count": group["component_count"],
    }


def validate_pdf_parser(pdf_bytes: bytes) -> tuple[bool, List[str]]:
    warnings = []

    if shutil.which("qpdf"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
            temp_path = Path(handle.name)
            handle.write(pdf_bytes)
        try:
            result = subprocess.run(
                ["qpdf", "--check", str(temp_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                return False, [result.stderr.strip() or result.stdout.strip() or "qpdf check failed"]
            return True, warnings
        finally:
            temp_path.unlink(missing_ok=True)

    warnings.append("qpdf not available; parser validation skipped")
    return True, warnings


def validate_candidate(candidate: dict) -> CandidateResult:
    result = CandidateResult(
        source=candidate["source"],
        sequence=candidate["sequence"],
        component_count=candidate["component_count"],
        warnings=list(candidate["warnings"]),
    )
    payload = candidate["payload"]

    try:
        pdf_bytes = base64.b64decode(payload, validate=True)
    except Exception as exc:
        result.message = f"Base64 decode failed: {exc}"
        return result

    result.bytes_length = len(pdf_bytes)

    if not pdf_bytes.startswith(PDF_MAGIC):
        result.message = "Decoded bytes do not start with %PDF"
        return result

    if not pdf_bytes.rstrip().endswith(PDF_EOF):
        result.warnings.append("PDF missing %%EOF trailer")

    parser_ok, parser_messages = validate_pdf_parser(pdf_bytes)
    if not parser_ok:
        result.message = f"PDF parser validation failed: {'; '.join(msg for msg in parser_messages if msg)}"
        return result
    result.warnings.extend(msg for msg in parser_messages if msg)

    result.sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    result.pdf_bytes = pdf_bytes
    result.status = "PASS" if not result.warnings else "WARNING"
    result.message = "Valid PDF payload"
    return result


def inspect_file(file_path: Path) -> FileResult:
    records = extract_ed_records(file_path)
    if not records:
        return FileResult(path=str(file_path), status="FAIL", message="No ED OBX records found")

    grouped_candidates = group_records_for_reassembly(records)
    if not grouped_candidates:
        return FileResult(path=str(file_path), status="FAIL", message="No PDF-like payload candidates found")

    candidates = [validate_candidate(candidate) for candidate in grouped_candidates]
    valid_hashes = [candidate.sha256 for candidate in candidates if candidate.sha256]

    if valid_hashes:
        status = "PASS"
        if any(candidate.status == "WARNING" for candidate in candidates if candidate.sha256):
            status = "WARNING"
        warnings = []
        for candidate in candidates:
            warnings.extend(candidate.warnings)
        return FileResult(
            path=str(file_path),
            status=status,
            message=f"Found {len(valid_hashes)} valid PDF payload(s)",
            candidates=candidates,
            warnings=sorted(set(warnings)),
            pdf_hashes=valid_hashes,
        )

    return FileResult(
        path=str(file_path),
        status="FAIL",
        message="ED records found but no valid PDF payload",
        candidates=candidates,
    )


def summarize_results(results: Iterable[FileResult]) -> dict:
    results = list(results)
    groups = {}
    counts = {"PASS": 0, "WARNING": 0, "FAIL": 0}
    candidate_counts = {"PASS": 0, "WARNING": 0, "FAIL": 0}

    for result in results:
        counts[result.status] += 1
        for candidate in result.candidates:
            candidate_counts[candidate.status] += 1
        for pdf_hash in result.pdf_hashes:
            groups.setdefault(pdf_hash, []).append(result.path)

    all_valid_hashes = sorted(groups.keys())
    identical = len(all_valid_hashes) <= 1 and bool(all_valid_hashes)

    return {
        "scanned_files": len(results),
        "counts": counts,
        "candidate_counts": candidate_counts,
        "identical_valid_pdfs": identical,
        "hash_groups": groups,
    }


def render_text_report(results: List[FileResult], summary: dict) -> str:
    lines = []
    lines.append(f"Scanned {summary['scanned_files']} XML file(s)")
    lines.append(f"File tests passed: {summary['counts']['PASS']}")
    lines.append(f"File tests passed with warnings: {summary['counts']['WARNING']}")
    lines.append(f"File tests failed: {summary['counts']['FAIL']}")
    lines.append(f"PDF payload tests passed: {summary['candidate_counts']['PASS']}")
    lines.append(f"PDF payload tests passed with warnings: {summary['candidate_counts']['WARNING']}")
    lines.append(f"PDF payload tests failed: {summary['candidate_counts']['FAIL']}")
    if summary["hash_groups"]:
        lines.append(
            "All valid PDFs identical: "
            + ("YES" if summary["identical_valid_pdfs"] else "NO")
        )
    else:
        lines.append("All valid PDFs identical: N/A")

    return "\n".join(lines)


def scan_directory(directory: Path) -> List[FileResult]:
    xml_files = sorted(directory.glob("*.xml"))
    return [inspect_file(path) for path in xml_files]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan XML files for HL7 OBX ED PDF payloads and compare decoded PDF content."
    )
    parser.add_argument("input", nargs="?", help="Optional XML file to inspect. If omitted, scans current folder.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON report.")
    return parser


def write_and_open_valid_pdfs(results: List[FileResult], output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=True)
    opened = 0

    for result in results:
        base_name = Path(result.path).stem
        valid_candidates = [candidate for candidate in result.candidates if candidate.pdf_bytes]
        for index, candidate in enumerate(valid_candidates, start=1):
            output_path = output_dir / f"{base_name}_candidate_{index}.pdf"
            output_path.write_bytes(candidate.pdf_bytes)
            open_pdf(output_path)
            opened += 1

    return opened


def open_pdf(path: Path) -> None:
    if sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", str(path)], check=False)
    elif sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif os.name == "nt":
        os.startfile(str(path))


def result_to_json_dict(result: FileResult) -> dict:
    payload = asdict(result)
    for candidate in payload["candidates"]:
        candidate["pdf_bytes"] = None
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Input file not found: {path}", file=sys.stderr)
            return 1
        results = [inspect_file(path)]
    else:
        results = scan_directory(Path.cwd())
        if not results:
            print("No XML files found in current directory.", file=sys.stderr)
            return 1

    summary = summarize_results(results)

    if args.as_json:
        payload = {
            "results": [result_to_json_dict(result) for result in results],
            "summary": summary,
        }
        print(json.dumps(payload, indent=2))
    else:
        opened = write_and_open_valid_pdfs(results, Path.cwd() / "extracted_pdfs")
        print(render_text_report(results, summary))
        if opened:
            print(f"Opened {opened} PDF file(s) from extracted_pdfs/")

    return 0 if summary["counts"]["FAIL"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
