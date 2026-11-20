import sqlite3

conn = sqlite3.connect('storage/gate_intelligence.db')
c = conn.cursor()

tables = [row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
for t in tables:
    cols = c.execute(f"PRAGMA table_info('{t}')").fetchall()
    col_str = ", ".join([f"{col[1]} ({col[2]})" for col in cols])
    print(f"{t}: {col_str}")

print("\n=== SAMPLE QUESTION PAPERS ROWS ===")
for row in c.execute("SELECT * FROM question_papers LIMIT 3").fetchall():
    print(row)

print("\n=== SAMPLE ANSWER KEYS ROWS ===")
for row in c.execute("SELECT * FROM answer_keys LIMIT 3").fetchall():
    print(row)

print("\n=== SAMPLE QUESTIONS ROWS ===")
for row in c.execute("SELECT * FROM questions LIMIT 2").fetchall():
    print(row)
