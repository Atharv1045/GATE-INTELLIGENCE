"""
Safe, Transactional Database Cleanup & Visual Asset Migration Script.
- Replaces the 88 duplicated/uncertain questions in storage/gate_intelligence.db
  with the 65 verified questions, 256 options, and 65 answer keys.
- Runs VisualPipeline to extract vector and raster diagrams from 2012_CS.pdf
  and populates question_visual_assets.
- Corrects 2007-2010 question paper statuses from 'completed' to 'needs_review'
  (since they have 0 questions extracted).
- Validates foreign key constraints with PRAGMA foreign_key_check.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.config import settings
from app.pipelines.visual_pipeline import VisualPipeline
from app.database.session import new_uuid, utcnow_iso


def reconcile_database(dry_run: bool = False) -> None:
    db_path = settings.SQLITE_DB_PATH
    val_db_path = REPO_ROOT / "validation" / "database" / "phase8_test.db"

    print(f"Target Production Database: {db_path}")
    print(f"Verified Reference Database: {val_db_path}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE MIGRATION'}")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")

    val_conn = sqlite3.connect(str(val_db_path))
    val_conn.row_factory = sqlite3.Row

    try:
        # 1. Inspect existing 2012 paper
        prod_2012 = conn.execute(
            "SELECT id, paper_code, examination_year FROM question_papers WHERE examination_year = 2012 AND paper_code = 'CS'"
        ).fetchone()
        if not prod_2012:
            raise RuntimeError("2012 CS paper not found in production database!")

        prod_paper_id = prod_2012["id"]
        old_q_count = conn.execute(
            "SELECT count(*) FROM questions WHERE question_paper_id = ?", (prod_paper_id,)
        ).fetchone()[0]
        print(f"Current questions in 2012 CS ({prod_paper_id}): {old_q_count}")

        # 2. Read verified 65 questions, options, and answer keys from validation DB
        val_questions = val_conn.execute(
            "SELECT * FROM questions ORDER BY question_number"
        ).fetchall()
        val_options = val_conn.execute("SELECT * FROM question_options").fetchall()
        val_keys = val_conn.execute("SELECT * FROM answer_keys").fetchall()
        print(f"Verified dataset: {len(val_questions)} questions, {len(val_options)} options, {len(val_keys)} answer keys")

        if dry_run:
            print("Dry run completed successfully. No changes written.")
            return

        # Start transaction
        conn.execute("BEGIN TRANSACTION;")

        # Delete existing 88 questions for 2012 CS (foreign keys CASCADE deletes options, answer_keys, etc.)
        conn.execute("DELETE FROM questions WHERE question_paper_id = ?", (prod_paper_id,))
        print(f"Deleted old questions for paper {prod_paper_id}")

        # Map old validation question_id -> same question_id or new
        # We can keep the same question IDs from validation db to keep options and keys intact
        for q in val_questions:
            q_dict = dict(q)
            q_dict["question_paper_id"] = prod_paper_id
            keys = list(q_dict.keys())
            placeholders = ", ".join(["?"] * len(keys))
            col_names = ", ".join(keys)
            conn.execute(
                f"INSERT INTO questions ({col_names}) VALUES ({placeholders})",
                [q_dict[k] for k in keys],
            )

        for opt in val_options:
            o_dict = dict(opt)
            keys = list(o_dict.keys())
            placeholders = ", ".join(["?"] * len(keys))
            col_names = ", ".join(keys)
            conn.execute(
                f"INSERT INTO question_options ({col_names}) VALUES ({placeholders})",
                [o_dict[k] for k in keys],
            )

        for ak in val_keys:
            ak_dict = dict(ak)
            keys = list(ak_dict.keys())
            placeholders = ", ".join(["?"] * len(keys))
            col_names = ", ".join(keys)
            conn.execute(
                f"INSERT INTO answer_keys ({col_names}) VALUES ({placeholders})",
                [ak_dict[k] for k in keys],
            )

        # 3. Extract and link visual assets for 2012 CS
        pdf_path = REPO_ROOT / "validation" / "uploads" / "2012_CS.pdf"
        if not pdf_path.exists():
            pdf_path = REPO_ROOT / "storage" / "uploads" / "shared" / f"{prod_paper_id}_2012_CS.pdf"

        if pdf_path.exists():
            print(f"Extracting visual assets from {pdf_path}...")
            vpipe = VisualPipeline()
            pdf_bytes = pdf_path.read_bytes()
            q_rows = [dict(r) for r in conn.execute(
                "SELECT id, question_number, source_page_start, source_page_end FROM questions WHERE question_paper_id = ?",
                (prod_paper_id,),
            ).fetchall()]

            assets = vpipe.extract_and_map_visual_assets(
                pdf_bytes=pdf_bytes,
                paper_id=prod_paper_id,
                questions=q_rows,
                paper_code="CS",
                exam_year=2012,
            )
            print(f"Extracted {len(assets)} visual asset diagram files.")
            inserted_assets = vpipe.persist_visual_assets_to_db(conn, assets)
            print(f"Persisted {inserted_assets} visual asset records into database.")

        # 4. Update status of 2012 CS to 'completed'
        now = utcnow_iso()
        conn.execute(
            """
            UPDATE question_papers
            SET processing_status = 'completed',
                total_extracted_questions = 65,
                updated_at = ?
            WHERE id = ?
            """,
            (now, prod_paper_id),
        )

        # 5. Fix empty 2007-2010 papers
        empty_papers = conn.execute(
            """
            SELECT qp.id, qp.examination_year
            FROM question_papers qp
            WHERE qp.examination_year BETWEEN 2007 AND 2010
              AND (SELECT COUNT(*) FROM questions q WHERE q.question_paper_id = qp.id) = 0
            """
        ).fetchall()

        for ep in empty_papers:
            conn.execute(
                """
                UPDATE question_papers
                SET processing_status = 'needs_review',
                    total_extracted_questions = 0,
                    updated_at = ?
                WHERE id = ?
                """,
                (now, ep["id"]),
            )
            print(f"Updated empty paper GATE CS {ep['examination_year']} status to 'needs_review'.")

        # 6. Verify foreign key constraints
        fk_errors = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if fk_errors:
            raise RuntimeError(f"Foreign key violations detected: {fk_errors}")

        conn.commit()
        print("DATABASE RECONCILIATION COMMITTED SUCCESSFULLY!")

        # Post-migration sanity checks
        new_q_count = conn.execute(
            "SELECT count(*) FROM questions WHERE question_paper_id = ?", (prod_paper_id,)
        ).fetchone()[0]
        new_opt_count = conn.execute(
            "SELECT count(*) FROM question_options WHERE question_id IN (SELECT id FROM questions WHERE question_paper_id = ?)",
            (prod_paper_id,),
        ).fetchone()[0]
        new_asset_count = conn.execute(
            "SELECT count(*) FROM question_visual_assets"
        ).fetchone()[0]

        print("=== FINAL COUNTS ===")
        print(f"2012 CS Questions: {new_q_count} (expected 65)")
        print(f"2012 CS Options: {new_opt_count} (expected 256)")
        print(f"Total Visual Assets: {new_asset_count}")
        print("====================")

    except Exception as e:
        conn.rollback()
        print(f"ERROR: Transaction rolled back due to error: {e}")
        raise
    finally:
        conn.close()
        val_conn.close()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    reconcile_database(dry_run=dry_run)
