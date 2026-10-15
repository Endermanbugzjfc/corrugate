"""Bounded subprocess rendering keeps failures away from the TUI event loop."""

from __future__ import annotations

import base64
import io
import os
import re
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

from .store import Board

RENDER_TIMEOUT = 20
MAX_PIXELS = 25_000_000


def rasterize(source: bytes, mime: str) -> bytes:
    from PIL import Image, ImageOps

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if mime == "text/x-latex":
        text = source.decode("utf-8")
        # This is an equation renderer, not a general-purpose TeX execution service.
        if re.search(r"\\(?:input|include|openin|openout|read|write|usepackage|documentclass)\b", text):
            raise ValueError("Math bodies cannot load files, packages, or perform file I/O")
        document = (
            "\\documentclass{article}\n\\usepackage{amsmath,amssymb}\n"
            "\\pagestyle{empty}\n\\begin{document}\n\\[\n"
            + text + "\n\\]\n\\end{document}\n"
        )
        with tempfile.TemporaryDirectory(prefix="corrugate-tex-") as directory:
            root = Path(directory)
            (root / "math.tex").write_text(document)
            env = dict(os.environ, openin_any="p", openout_any="p")
            for command in (
                ["latex", "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error", "math.tex"],
                ["dvipng", "-D", "160", "-T", "tight", "-bg", "White", "-o", "math.png", "math.dvi"],
            ):
                result = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=15)
                if result.returncode:
                    diagnostic = (result.stdout + result.stderr).decode(errors="replace")
                    raise ValueError(diagnostic[-1800:])
            source = (root / "math.png").read_bytes()
    elif mime == "image/svg+xml":
        from cairosvg.surface import PNGSurface
        from defusedxml import ElementTree

        ElementTree.fromstring(source)

        def embedded_only(url: str, resource_type: str) -> bytes:
            if not url.startswith("data:"):
                raise ValueError("SVG must be self-contained: external resources are unsupported")
            header, data = url.split(",", 1)
            if ";base64" not in header or not header.startswith("data:image/"):
                raise ValueError("SVG embedded images must use base64 image data URLs")
            return base64.b64decode(data, validate=True)

        source = PNGSurface.convert(bytestring=source, url_fetcher=embedded_only)
    with Image.open(io.BytesIO(source)) as original:
        if getattr(original, "n_frames", 1) != 1:
            raise ValueError("Animated images are unsupported; publish a static frame")
        if original.width * original.height > MAX_PIXELS:
            raise ValueError("Image exceeds the 25 megapixel limit")
        normalized = ImageOps.exif_transpose(original).convert("RGBA")
        output = io.BytesIO()
        normalized.save(output, format="PNG")
        return output.getvalue()


def render_item(board: Board, item_id: str) -> None:
    item = board.item(item_id)
    if item.render_status != "pending":
        return
    command = [sys.executable, "-m", "corrugate.render", str(board.path), item_id, str(item.revision)]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
    )
    try:
        _, error = process.communicate(timeout=RENDER_TIMEOUT)
        if process.returncode:
            board.finish_render(item_id, item.revision, None, error.decode(errors="replace")[-1800:]
                                or "Renderer exited without a preview")
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        board.finish_render(item_id, item.revision, None, "Rendering timed out after 20 seconds")


def worker() -> None:
    import resource

    resource.setrlimit(resource.RLIMIT_CPU, (18, 18))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    board = Board(Path(sys.argv[1]))
    item_id, revision = sys.argv[2], int(sys.argv[3])
    source, mime, current = board.source(item_id)
    if current != revision:
        return
    try:
        board.finish_render(item_id, revision, rasterize(source, mime))
    except Exception as exc:
        board.finish_render(item_id, revision, None, str(exc))


if __name__ == "__main__":
    worker()
