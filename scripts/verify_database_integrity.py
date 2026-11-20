import sqlite3
import os
from pathlib import Path

DB_PATH = Path(r"D:\Projects\GATE-INTELLIGENCE\storage\gate_intelligence.db")
BACKUP_DIR = Path(r"D:\Projects\GATE-INTELLIGENCE\storage\backups")

def verify_database():
    print("==================================================")
    print("      DATABASE INTEGRITY & SAFETY VERIFICATION    ")
    print("==================================================")
    assert DB_PATH.exists(), f"Database file missing: {DB_PATH}"
    print(f"[OK] Database exists at {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.2f} MB)")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. SQLite PRAGMA integrity_check
    cursor.execute("PRAGMA integrity_check")
    integrity = cursor.fetchall()
    print(f"[OK] PRAGMA integrity_check: {integrity[0][0]}")
    assert integrity[0][0] == "ok", "Database integrity check failed!"

    # 2. SQLite PRAGMA foreign_key_check
    cursor.execute("PRAGMA foreign_key_check")
    fk_violations = cursor.fetchall()
    print(f"[OK] PRAGMA foreign_key_check: {len(fk_violations)} violations found")
    assert len(fk_violations) == 0, f"Foreign key violations: {fk_violations}"

    # 3. Tables and record counts
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
    print(f"[OK] Database contains {len(tables)} tables: {', '.join(tables)}")

    for t in ["disciplines", "syllabus_subjects", "topics", "question_papers", "questions", "question_options", "answer_keys", "mock_tests", "student_responses"]:
        if t in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {t}")
            count = cursor.fetchone()[0]
            print(f"     - Table '{t}': {count} records")

    # 4. Check for duplicate questions within the same paper
    cursor.execute("""
        SELECT question_paper_id, question_number, COUNT(*)
        FROM questions
        GROUP BY question_paper_id, question_number
        HAVING COUNT(*) > 1
    """)
    duplicates = cursor.fetchall()
    print(f"[OK] Duplicate questions per paper: {len(duplicates)}")
    assert len(duplicates) == 0, f"Duplicate questions found: {duplicates}"

    # 5. Question counts per paper
    cursor.execute("""
        SELECT qp.paper_code, qp.examination_year, COUNT(q.id)
        FROM question_papers qp
        LEFT JOIN questions q ON qp.id = q.question_paper_id
        GROUP BY qp.id
    """)
    paper_counts = cursor.fetchall()
    print("[OK] Question counts per paper:")
    for code, yr, cnt in paper_counts:
        print(f"     - {code} {yr}: {cnt} questions")

    # 6. Answer key provenance distribution
    cursor.execute("""
        SELECT provenance, COUNT(*)
        FROM answer_keys
        GROUP BY provenance
    """)
    provenance = cursor.fetchall()
    print("[OK] Answer key provenance distribution:")
    for prov, cnt in provenance:
        print(f"     - Provenance: '{prov}': {cnt} keys")

    # 7. Backup files verification
    backups = list(BACKUP_DIR.glob("*.db"))
    print(f"[OK] Found {len(backups)} backup files in {BACKUP_DIR}:")
    for b in backups:
        b_size = b.stat().st_size
        # Verify backup can be opened and queried
        b_conn = sqlite3.connect(b)
        b_cur = b_conn.cursor()
        b_cur.execute("SELECT COUNT(*) FROM questions")
        b_qcount = b_cur.fetchone()[0]
        b_conn.close()
        print(f"     - {b.name}: {b_size / 1024 / 1024:.2f} MB, {b_qcount} questions (Valid SQLite)")
        assert b_qcount > 0, f"Backup question count too low: {b_qcount}"

    conn.close()
    print("\n>>> ALL DATABASE INTEGRITY CHECKS PASSED SUCCESSFULLY <<<\n")

if __name__ == "__main__":
    verify_database()
