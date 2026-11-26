"""A generated benchmark project: 50 findings and 20 images of up to 500 KB (NFR-01..03)."""

from __future__ import annotations

import random
import struct
import zlib
from pathlib import Path

import pytest

FINDINGS = 50
IMAGES = 20
MAX_IMAGE_BYTES = 500 * 1024
SEVERITY_VECTORS = (
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
    "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N",
    "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N",
    "CVSS:3.1/AV:P/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
)


def _png(width: int, height: int, rng: random.Random) -> bytes:
    """A noisy RGB PNG (noise keeps it from compressing to almost nothing)."""

    def chunk(kind: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(kind + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc)

    rows = b"".join(b"\x00" + rng.randbytes(width * 3) for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows, 1))
        + chunk(b"IEND", b"")
    )


def _finding(index: int, image: str | None) -> str:
    evidence = f"""      - type: http
        caption: "Request and response {index}"
        content: |
          POST /api/v1/item/{index} HTTP/1.1
          Host: app.example.test
          Authorization: Bearer token{index:04d}abcdef
          Content-Type: application/json

          {{"id":{index},"password":"secret{index}","email":"user{index}@example.test"}}

          HTTP/1.1 200 OK
          Set-Cookie: session=cookie{index:04d}; Path=/; HttpOnly
"""
    if image:
        evidence += f"""      - type: image
        caption: "Screenshot {index}"
        path: {image}
"""
    return f"""  - id: PT-{index:03d}
    title: "Benchmark finding number {index}"
    cvss_vector: "{SEVERITY_VECTORS[index % len(SEVERITY_VECTORS)]}"
    cwe: [{79 + index}]
    affected_assets:
      - "https://app.example.test/api/v1/item/{index}"
    description: |
      The `item` endpoint number {index} trusts user input. **Details** follow in the
      evidence, including a [reference](https://owasp.org/) and `inline code`.
    impact: "An attacker can read and modify records belonging to other users."
    steps_to_reproduce:
      - "Log in as any user and send the request in Evidence 1."
      - "Change the `id` value and observe another user's record."
    evidence:
{evidence}    remediation: "Check object ownership on every request before returning data."
    references:
      - "https://owasp.org/Top10/A01_2021-Broken_Access_Control/"
"""


@pytest.fixture(scope="session")
def bench_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A project directory with findings.yaml (50 findings) and 20 evidence images."""
    root = tmp_path_factory.mktemp("bench")
    (root / "evidence").mkdir()
    rng = random.Random(20261126)  # noqa: S311 - test image noise, not security; fixed seed
    images = []
    for number in range(IMAGES):
        name = f"evidence/shot-{number:02d}.png"
        data = _png(400, 300, rng)  # about 360 KB of noise
        assert len(data) <= MAX_IMAGE_BYTES
        (root / name).write_bytes(data)
        images.append(name)
    findings = "".join(
        _finding(i, images[i - 1] if i <= IMAGES else None) for i in range(1, FINDINGS + 1)
    )
    (root / "findings.yaml").write_text(
        f"""schema_version: 1
engagement:
  title: "Benchmark Engagement With Fifty Findings"
  client:
    name: "Example Corp"
  testers:
    - name: "Alex Tester"
  start_date: 2026-11-02
  end_date: 2026-11-13
  report_date: 2026-11-20
  scope:
    in_scope:
      - asset: "https://app.example.test"
        type: url
  methodology: "Grey-box testing following the OWASP Web Security Testing Guide."
findings:
{findings}""",
        encoding="utf-8",
    )
    return root
