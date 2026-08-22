#!/usr/bin/env python
"""Extract local modeling materials into text, rendered pages, and manifests.

This script is intentionally conservative: it never edits source files, records
tool failures, and writes extraction artifacts under an output directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from xml.etree import ElementTree as ET


SUPPORTED = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".csv",
    ".txt",
    ".md",
    ".m",
    ".py",
    ".json",
}

NS_WORD = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
NS_PPT = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}


@dataclass
class Record:
    source_path: str
    source_name: str
    extension: str
    status: str = "started"
    text_path: str | None = None
    rendered_dir: str | None = None
    tables_dir: str | None = None
    pages: int | None = None
    slides: int | None = None
    chars: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_path": self.source_path,
            "source_name": self.source_name,
            "extension": self.extension,
            "status": self.status,
            "text_path": self.text_path,
            "rendered_dir": self.rendered_dir,
            "tables_dir": self.tables_dir,
            "pages": self.pages,
            "slides": self.slides,
            "chars": self.chars,
            "warnings": self.warnings,
        }


def safe_stem(path: Path) -> str:
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", path.stem, flags=re.UNICODE).strip("_")
    digest = hashlib.sha1(str(path).encode("utf-8", errors="ignore")).hexdigest()[:8]
    return f"{stem or 'source'}_{digest}"


def ensure_dirs(out_dir: Path) -> dict[str, Path]:
    dirs = {
        "texts": out_dir / "texts",
        "rendered": out_dir / "rendered",
        "tables": out_dir / "tables",
        "logs": out_dir / "logs",
    }
    for value in dirs.values():
        value.mkdir(parents=True, exist_ok=True)
    return dirs


def run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def read_plain(path: Path, dirs: dict[str, Path], record: Record) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gb18030", errors="replace")
        record.warnings.append("Read with gb18030 fallback.")
    out = dirs["texts"] / f"{safe_stem(path)}.txt"
    write_text(out, text)
    record.text_path = str(out)
    record.chars = len(text)
    record.status = "ok"


def extract_docx(path: Path, dirs: dict[str, Path], record: Record) -> None:
    lines: list[str] = [f"# {path.name}", "", f"- Source: {path}", ""]
    with zipfile.ZipFile(path) as zf:
        names = [
            name
            for name in zf.namelist()
            if name == "word/document.xml"
            or (name.startswith("word/header") and name.endswith(".xml"))
            or (name.startswith("word/footer") and name.endswith(".xml"))
        ]
        for name in names:
            root = ET.fromstring(zf.read(name))
            lines.append(f"## {name}")
            lines.append("")
            for para in root.findall(".//w:p", NS_WORD):
                chunks: list[str] = []
                for node in para.iter():
                    if node.tag == f"{{{NS_WORD['w']}}}t" and node.text:
                        chunks.append(node.text)
                    elif node.tag == f"{{{NS_WORD['w']}}}tab":
                        chunks.append("\t")
                    elif node.tag == f"{{{NS_WORD['w']}}}br":
                        chunks.append("\n")
                text = "".join(chunks).strip()
                if text:
                    lines.append(text)
            lines.append("")
    out = dirs["texts"] / f"{safe_stem(path)}.md"
    text = "\n".join(lines)
    write_text(out, text)
    record.text_path = str(out)
    record.chars = len(text)
    record.status = "ok"


def slide_number(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def extract_pptx(path: Path, dirs: dict[str, Path], record: Record) -> None:
    lines: list[str] = [f"# {path.name}", "", f"- Source: {path}", ""]
    slide_count = 0
    with zipfile.ZipFile(path) as zf:
        slide_names = sorted(
            [name for name in zf.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", name)],
            key=slide_number,
        )
        for idx, name in enumerate(slide_names, start=1):
            slide_count += 1
            root = ET.fromstring(zf.read(name))
            lines.append(f"## Slide {idx}")
            lines.append("")
            texts = [node.text for node in root.findall(".//a:t", NS_PPT) if node.text]
            if texts:
                lines.append("\n".join(texts))
                lines.append("")
    out = dirs["texts"] / f"{safe_stem(path)}.md"
    text = "\n".join(lines)
    write_text(out, text)
    record.text_path = str(out)
    record.slides = slide_count
    record.chars = len(text)
    record.status = "ok"


def pdf_pages(path: Path, record: Record) -> int | None:
    if not shutil.which("pdfinfo"):
        return None
    proc = run(["pdfinfo", str(path)], timeout=60)
    if proc.returncode != 0:
        record.warnings.append("pdfinfo failed: " + proc.stderr.strip()[:300])
        return None
    for line in proc.stdout.splitlines():
        if line.lower().startswith("pages:"):
            try:
                return int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
    return None


def extract_pdf_text(path: Path, record: Record) -> str:
    chunks: list[str] = []
    try:
        import pdfplumber  # type: ignore

        with pdfplumber.open(str(path)) as pdf:
            record.pages = record.pages or len(pdf.pages)
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                chunks.append(f"\n\n## Page {i}\n\n{text}")
    except Exception as exc:
        record.warnings.append(f"pdfplumber failed: {exc}")

    text = "".join(chunks).strip()
    if text:
        return text

    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        record.pages = record.pages or len(reader.pages)
        for i, page in enumerate(reader.pages, start=1):
            chunks.append(f"\n\n## Page {i}\n\n{page.extract_text() or ''}")
    except Exception as exc:
        record.warnings.append(f"pypdf failed: {exc}")

    text = "".join(chunks).strip()
    if text:
        return text

    if shutil.which("pdftotext"):
        with subprocess.TemporaryDirectory() if False else _null_context():
            temp_txt = path.with_suffix(path.suffix + ".pdftotext.tmp.txt")
            proc = run(["pdftotext", "-layout", str(path), str(temp_txt)], timeout=120)
            if proc.returncode == 0 and temp_txt.exists():
                text = temp_txt.read_text(encoding="utf-8", errors="replace")
                temp_txt.unlink(missing_ok=True)
                return text
            record.warnings.append("pdftotext failed: " + proc.stderr.strip()[:300])
            temp_txt.unlink(missing_ok=True)
    return ""


class _null_context:
    def __enter__(self):
        return None

    def __exit__(self, *_args):
        return False


def extract_pdf(path: Path, dirs: dict[str, Path], record: Record, args: argparse.Namespace) -> None:
    record.pages = pdf_pages(path, record)
    text = extract_pdf_text(path, record)
    out = dirs["texts"] / f"{safe_stem(path)}.md"
    header = f"# {path.name}\n\n- Source: {path}\n- Pages: {record.pages or 'unknown'}\n\n"
    write_text(out, header + (text or "[No text extracted. Use rendered pages for visual reading.]\n"))
    record.text_path = str(out)
    record.chars = len(text)

    if args.render_pdf:
        if shutil.which("pdftoppm"):
            render_dir = dirs["rendered"] / safe_stem(path)
            render_dir.mkdir(parents=True, exist_ok=True)
            prefix = render_dir / "page"
            cmd = ["pdftoppm", "-png"]
            if args.max_render_pages and args.max_render_pages > 0:
                cmd += ["-f", "1", "-l", str(args.max_render_pages)]
            cmd += [str(path), str(prefix)]
            proc = run(cmd, timeout=args.render_timeout)
            if proc.returncode == 0:
                record.rendered_dir = str(render_dir)
            else:
                record.warnings.append("pdftoppm failed: " + proc.stderr.strip()[:500])
        else:
            record.warnings.append("pdftoppm not found; no PDF pages rendered.")
    record.status = "ok" if text or record.rendered_dir else "partial"


def extract_xlsx(path: Path, dirs: dict[str, Path], record: Record) -> None:
    try:
        import openpyxl  # type: ignore
    except Exception as exc:
        record.status = "partial"
        record.warnings.append(f"openpyxl unavailable: {exc}")
        return

    tables_dir = dirs["tables"] / safe_stem(path)
    tables_dir.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    lines = [f"# {path.name}", "", f"- Source: {path}", "", "## Sheets", ""]
    for ws in wb.worksheets:
        sheet_name = re.sub(r"[^\w.-]+", "_", ws.title, flags=re.UNICODE).strip("_") or "sheet"
        csv_path = tables_dir / f"{sheet_name}.csv"
        rows_written = 0
        with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            for row in ws.iter_rows(values_only=True):
                writer.writerow(["" if cell is None else cell for cell in row])
                rows_written += 1
        lines.append(f"- {ws.title}: {rows_written} rows -> {csv_path.name}")
    out = dirs["texts"] / f"{safe_stem(path)}.md"
    text = "\n".join(lines)
    write_text(out, text)
    record.text_path = str(out)
    record.tables_dir = str(tables_dir)
    record.chars = len(text)
    record.status = "ok"


def extract_csv(path: Path, dirs: dict[str, Path], record: Record) -> None:
    tables_dir = dirs["tables"] / safe_stem(path)
    tables_dir.mkdir(parents=True, exist_ok=True)
    target = tables_dir / path.name
    shutil.copy2(path, target)
    preview_lines: list[str] = []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for idx, row in enumerate(csv.reader(f)):
                if idx >= 20:
                    break
                preview_lines.append(", ".join(row))
    except UnicodeDecodeError:
        with path.open("r", encoding="gb18030", errors="replace", newline="") as f:
            for idx, row in enumerate(csv.reader(f)):
                if idx >= 20:
                    break
                preview_lines.append(", ".join(row))
        record.warnings.append("CSV preview used gb18030 fallback.")
    text = f"# {path.name}\n\n- Source: {path}\n- Copied table: {target}\n\n## Preview\n\n" + "\n".join(preview_lines)
    out = dirs["texts"] / f"{safe_stem(path)}.md"
    write_text(out, text)
    record.text_path = str(out)
    record.tables_dir = str(tables_dir)
    record.chars = len(text)
    record.status = "ok"


def extract_legacy_office(path: Path, dirs: dict[str, Path], record: Record, args: argparse.Namespace) -> None:
    script = Path(__file__).with_name("extract_office_legacy.ps1")
    if not script.exists():
        raise FileNotFoundError(f"Missing helper script: {script}")
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-InputPath",
        str(path),
        "-OutputDir",
        str(dirs["texts"].parent),
        "-RenderSlides",
        "true" if args.render_office else "false",
    ]
    proc = run(cmd, timeout=args.office_timeout)
    if proc.returncode != 0:
        record.status = "failed"
        record.warnings.append("Office COM extraction failed: " + (proc.stderr or proc.stdout).strip()[:1000])
        return
    manifest_path: Path | None = None
    for line in proc.stdout.splitlines():
        if line.startswith("MANIFEST\t"):
            manifest_path = Path(line.split("\t", 1)[1])
            break
    if not manifest_path or not manifest_path.exists():
        record.status = "partial"
        record.warnings.append("Office COM helper returned no manifest.")
        return
    helper = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    record.status = helper.get("status", "ok")
    record.text_path = helper.get("text_path")
    record.rendered_dir = helper.get("rendered_dir")
    record.slides = helper.get("slides")
    record.chars = int(helper.get("chars") or 0)
    record.warnings.extend(helper.get("warnings") or [])


def dispatch(path: Path, dirs: dict[str, Path], args: argparse.Namespace) -> Record:
    record = Record(str(path), path.name, path.suffix.lower())
    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            extract_pdf(path, dirs, record, args)
        elif ext == ".docx":
            extract_docx(path, dirs, record)
        elif ext == ".pptx":
            if args.office_com_for_modern:
                extract_legacy_office(path, dirs, record, args)
            else:
                extract_pptx(path, dirs, record)
        elif ext in {".doc", ".ppt"}:
            extract_legacy_office(path, dirs, record, args)
        elif ext == ".xlsx":
            extract_xlsx(path, dirs, record)
        elif ext == ".xls":
            extract_legacy_office(path, dirs, record, args)
        elif ext == ".csv":
            extract_csv(path, dirs, record)
        elif ext in {".txt", ".md", ".m", ".py", ".json"}:
            read_plain(path, dirs, record)
        else:
            record.status = "skipped"
            record.warnings.append(f"Unsupported extension: {ext}")
    except Exception as exc:
        record.status = "failed"
        record.warnings.append(f"{type(exc).__name__}: {exc}")
    return record


def iter_sources(paths: list[str], recursive: bool) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            iterator = path.rglob("*") if recursive else path.iterdir()
            for item in iterator:
                if item.is_file() and item.suffix.lower() in SUPPORTED:
                    yield item
        elif path.is_file():
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract modeling materials for Mira.")
    parser.add_argument("sources", nargs="+", help="Files or folders to extract.")
    parser.add_argument("--output-dir", default=None, help="Output directory. Defaults to materials/extracted/material-extraction/<timestamp>.")
    parser.add_argument("--recursive", action="store_true", help="Recurse into source directories.")
    parser.add_argument("--render-pdf", action="store_true", help="Render PDF pages to PNG with pdftoppm when available.")
    parser.add_argument("--max-render-pages", type=int, default=20, help="Maximum PDF pages to render; 0 means all.")
    parser.add_argument("--render-timeout", type=int, default=180)
    parser.add_argument("--render-office", action="store_true", default=True, help="Render PowerPoint slides through Office COM.")
    parser.add_argument("--no-render-office", dest="render_office", action="store_false")
    parser.add_argument("--office-com-for-modern", action="store_true", help="Use Office COM for docx/pptx instead of zip XML parsing.")
    parser.add_argument("--office-timeout", type=int, default=240)
    args = parser.parse_args()

    if args.output_dir:
        out_dir = Path(args.output_dir)
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = Path("materials") / "extracted" / "material-extraction" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    dirs = ensure_dirs(out_dir)

    sources = list(iter_sources(args.sources, args.recursive))
    records = [dispatch(path, dirs, args).to_dict() for path in sources]
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(out_dir),
        "source_count": len(records),
        "records": records,
    }
    manifest_path = out_dir / "extraction_manifest.json"
    write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Wrote manifest: {manifest_path}")
    failed = sum(1 for item in records if item["status"] == "failed")
    partial = sum(1 for item in records if item["status"] == "partial")
    print(f"Extracted {len(records)} files; failed={failed}; partial={partial}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
