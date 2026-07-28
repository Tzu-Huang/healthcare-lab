"""Safe WADO-RS retrieval of a single DICOM instance."""

from __future__ import annotations

import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from email import policy
from email.parser import BytesParser
from typing import Any

from backend.clients.dcm4chee import open_secured
from backend.domain.validation import require_http_url

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_BYTES = 32 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024
_UID_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)+$")


class WadoRsError(RuntimeError):
    """Base class for safe, typed WADO-RS failures."""

    category = "upstream"


class WadoRsTimeoutError(WadoRsError):
    """The archive did not respond within the configured timeout."""

    category = "timeout"


class WadoRsUpstreamHttpError(WadoRsError):
    """The archive returned a non-successful HTTP response."""

    def __init__(self, status: int):
        self.status = status
        self.http_status = status
        super().__init__(f"WADO-RS returned HTTP {status}.")


class WadoRsSizeError(WadoRsError):
    """The response exceeded the configured byte limit."""

    category = "size"


class WadoRsMediaTypeError(WadoRsError):
    """The archive returned an unsupported media type."""

    category = "media-type"


class WadoRsMultipartError(WadoRsError):
    """A multipart WADO-RS response was malformed or not single-part."""

    category = "multipart"


def retrieve_dicom_instance(
    profile: dict[str, Any],
    *,
    study_instance_uid: str,
    series_instance_uid: str,
    sop_instance_uid: str,
    timeout: float | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
) -> bytes:
    """Retrieve one instance using identifiers supplied by a trusted repository."""
    resolved_timeout = float(
        profile.get("timeoutSeconds", DEFAULT_TIMEOUT_SECONDS)
        if timeout is None
        else timeout
    )
    if resolved_timeout <= 0:
        raise ValueError("timeout must be positive.")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive.")

    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(
        dicomweb.get("wadoRsUrl") or dicomweb.get("baseUrl"), "dicomweb.wadoRsUrl"
    ).rstrip("/")
    identifiers = (
        _validated_uid(study_instance_uid),
        _validated_uid(series_instance_uid),
        _validated_uid(sop_instance_uid),
    )
    url = (
        f"{base_url}/studies/{urllib.parse.quote(identifiers[0], safe='')}"
        f"/series/{urllib.parse.quote(identifiers[1], safe='')}"
        f"/instances/{urllib.parse.quote(identifiers[2], safe='')}"
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": 'multipart/related; type="application/dicom", application/dicom'},
        method="GET",
    )

    try:
        with open_secured(request, profile, timeout=resolved_timeout) as response:
            content_type = response.headers.get("Content-Type", "")
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > max_bytes:
                        raise WadoRsSizeError("WADO-RS response exceeded the byte limit.")
                except ValueError:
                    pass
            body = _bounded_read(response, max_bytes)
    except WadoRsError:
        raise
    except urllib.error.HTTPError as exc:
        raise WadoRsUpstreamHttpError(exc.code) from exc
    except (socket.timeout, TimeoutError) as exc:
        raise WadoRsTimeoutError("WADO-RS request timed out.") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, (socket.timeout, TimeoutError)):
            raise WadoRsTimeoutError("WADO-RS request timed out.") from exc
        raise WadoRsError("WADO-RS transport failed.") from exc
    except (OSError, ValueError) as exc:
        raise WadoRsError("WADO-RS transport failed.") from exc

    return _extract_dicom(content_type, body)


def _validated_uid(value: str) -> str:
    normalized = str(value or "").strip()
    if (
        len(normalized) > 64
        or not _UID_PATTERN.fullmatch(normalized)
        or any(part != "0" and part.startswith("0") for part in normalized.split("."))
    ):
        raise ValueError("Invalid DICOM UID.")
    return normalized


def _bounded_read(response: Any, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = response.read(min(_READ_CHUNK_BYTES, max_bytes - total + 1))
        if not chunk:
            return b"".join(chunks)
        total += len(chunk)
        if total > max_bytes:
            raise WadoRsSizeError("WADO-RS response exceeded the byte limit.")
        chunks.append(chunk)


def _extract_dicom(content_type: str, body: bytes) -> bytes:
    header = BytesParser(policy=policy.default).parsebytes(
        b"Content-Type: " + content_type.encode("ascii", errors="replace") + b"\r\n\r\n"
    )
    media_type = header.get_content_type().lower()
    if media_type == "application/dicom":
        if not body:
            raise WadoRsMultipartError("WADO-RS DICOM response was empty.")
        return body
    if media_type != "multipart/related":
        raise WadoRsMediaTypeError("WADO-RS response was not DICOM media.")
    related_type = header.get_param("type", header="content-type")
    if not isinstance(related_type, str) or related_type.lower() != "application/dicom":
        raise WadoRsMediaTypeError("WADO-RS multipart type was not application/dicom.")
    if not header.get_boundary():
        raise WadoRsMultipartError("WADO-RS multipart response had no boundary.")

    message = BytesParser(policy=policy.default).parsebytes(
        b"MIME-Version: 1.0\r\nContent-Type: "
        + content_type.encode("ascii", errors="replace")
        + b"\r\n\r\n"
        + body
    )
    if message.defects or not message.is_multipart():
        raise WadoRsMultipartError("WADO-RS multipart response was malformed.")
    parts = list(message.iter_parts())
    if len(parts) != 1:
        raise WadoRsMultipartError("WADO-RS multipart response must contain one part.")
    part = parts[0]
    if part.defects:
        raise WadoRsMultipartError("WADO-RS multipart part was malformed.")
    if part.get_content_type().lower() != "application/dicom":
        raise WadoRsMediaTypeError("WADO-RS multipart part was not application/dicom.")
    payload = part.get_payload(decode=True)
    if not isinstance(payload, bytes) or not payload:
        raise WadoRsMultipartError("WADO-RS multipart part had no binary payload.")
    return payload
