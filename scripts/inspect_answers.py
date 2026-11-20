import sqlite3

for db_path in ['storage/gate_intelligence.db', 'validation/database/phase8_test.db', 'validation/reports/phase8_before_visual_assets.db']:
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        count = c.execute("SELECT count(*) FROM answer_keys WHERE correct_options_json != '[]' AND correct_options_json IS NOT NULL").fetchone()[0]
        total = c.execute("SELECT count(*) FROM answer_keys").fetchone()[0]
        print(f"{db_path}: {count}/{total} answer keys have answers")
    except Exception as e:
        print(f"{db_path}: {e}")
