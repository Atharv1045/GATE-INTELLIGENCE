#!/usr/bin/env python3
"""
Local Windows GATE Paper Verification & Diagnostic Report Generator (`scripts/verify_local_papers.py`).

Run from `D:\Projects\GATE-INTELLIGENCE`:
    $env:PYTHONPATH = "$PWD\backend;$PWD"
    .\.venv\Scripts\python.exe .\scripts\verify_local_papers.py

For every uploaded paper in `storage/gate_intelligence.db` (or any PDF path passed on the command line),
this script runs the 16-stage extraction pipeline and prints the complete 11-point diagnostic report:
1. Number of PDF pages
2. Number of pages processed by digital text extraction
3. Number of pages processed by OCR (and OCR engine used)
4. Total extracted questions
5. Number of valid questions (`extraction_status == 'valid'`)
6. Number of uncertain questions (`extraction_status == 'uncertain'`)
7. Number of rejected false-positive blocks (instructions, range headers, footers)
8. Intra-paper duplicate candidates
9. Original question-number sequence (`Q.1`..`Q.65` and any missing/colliding numbers)
10. Page references (`source_page_start`..`source_page_end`)
11. Extraction warnings and errors
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.database.session import get_db_connection, init_database
from app.pipelines.pdf_pipeline import PdfIngestionPipeline


def analyze_pdf_file(pdf_path: Path, paper_code: str = "CS", year: int = 2012) -> dict:
    pipe = PdfIngestionPipeline()
    pdf_bytes = pdf_path.read_bytes()
    page_info = pipe.extract_pages_from_pdf(pdf_bytes, pdf_path.name)
    pages = page_info["pages"]

    total_pages = page_info["page_count"]
    ocr_pages = sum(1 for p in pages if p.get("ocr_used"))
    digital_pages = total_pages - ocr_pages

    full_stream, char_spans, marks_map, page_flags = pipe._clean_pages_and_build_stream(pages)
    anchors = pipe._find_question_anchors(full_stream)
    extracted = pipe.segment_and_extract_questions(pages, paper_code, year)

    valid_qs = [q for q in extracted if q.get("extraction_status") == "valid"]
    uncertain_qs = [q for q in extracted if q.get("extraction_status") == "uncertain"]
    rejected_count = max(0, len(anchors) - len(extracted))

    q_nums = [q["question_number"] for q in extracted]
    q_labels = [q["source_question_label"] for q in extracted]
    expected_65 = set(range(1, 66))
    missing_from_65 = sorted(expected_65 - set(q_nums))

    print("=" * 88)
    print(f"PAPER DIAGNOSTIC REPORT: {pdf_path.name} (GATE {paper_code} {year})")
    print("=" * 88)
    print(f" 1. Number of PDF pages                  : {total_pages}")
    print(f" 2. Pages processed by digital text      : {digital_pages}")
    print(f" 3. Pages processed by OCR               : {ocr_pages} (Scanned pages detected: {page_info.get('scanned_pages_count', 0)})")
    print(f" 4. Number of extracted questions        : {len(extracted)}")
    print(f" 5. Valid questions ('valid')            : {len(valid_qs)}")
    print(f" 6. Uncertain questions ('uncertain')    : {len(uncertain_qs)}")
    print(f" 7. Rejected non-question blocks         : {rejected_count} (plus cover/banner lines stripped)")
    print(f" 8. Unknown/Duplicate number collisions  : {sum(1 for lbl in q_labels if lbl == 'UNKNOWN')}")
    print(f" 9. Original question-number sequence    : {', '.join(q_labels[:15])}{' ... ' + ', '.join(q_labels[-5:]) if len(q_labels) > 15 else ''}")
    if len(extracted) > 0:
        print(f"    Missing numbers relative to 1..65    : {missing_from_65 if missing_from_65 else 'None (Complete 1..65 sequence!)'}")
        page_spans = [
            f"{q['source_question_label']}:p.{q['source_page_start']}"
            + (f"-{q['source_page_end']}" if q["source_page_end"] != q["source_page_start"] else "")
            for q in extracted[:12]
        ]
        print(f"10. Sample page references               : {', '.join(page_spans)} ...")
    print(f"11. Extraction errors                    : {page_info['extraction_errors'] or 'None'}")
    print("=" * 88)
    return {
        "total_pages": total_pages,
        "digital_pages": digital_pages,
        "ocr_pages": ocr_pages,
        "extracted_count": len(extracted),
        "valid_count": len(valid_qs),
        "uncertain_count": len(uncertain_qs),
        "missing_from_65": missing_from_65,
    }


def main() -> None:
    init_database()
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            p = Path(arg)
            if p.exists():
                analyze_pdf_file(p)
            else:
                print(f"[WARN] File not found: {p}")
        return

    conn = get_db_connection()
    try:
        papers = conn.execute(
            "SELECT id, title, paper_code, examination_year, file_path, processing_status, total_extracted_questions FROM question_papers ORDER BY examination_year ASC"
        ).fetchall()
        if not papers:
            print("No uploaded papers found in storage/gate_intelligence.db.")
            return
        for row in papers:
            fp = Path(row["file_path"])
            if fp.exists():
                analyze_pdf_file(fp, row["paper_code"], int(row["examination_year"]))
            else:
                print(f"[WARN] Stored paper '{row['title']}' file missing at {fp}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
