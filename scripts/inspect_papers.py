import sqlite3

conn = sqlite3.connect('storage/gate_intelligence.db')
c = conn.cursor()

print("Questions count by paper_id / year:")
rows = c.execute("SELECT examination_year, paper_code, count(*) FROM questions GROUP BY examination_year, paper_code").fetchall()
print(rows)

rows = c.execute("SELECT id, title, examination_year, session_set, total_extracted_questions FROM question_papers").fetchall()
print("\nQuestion papers in DB:")
for r in rows:
    print(r)
