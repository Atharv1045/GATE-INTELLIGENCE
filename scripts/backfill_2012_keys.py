import sqlite3
import json
import re
import pypdf

reader = pypdf.PdfReader('validation/uploads/2012_CS.pdf')
text = reader.pages[17].extract_text() + "\n" + reader.pages[18].extract_text()

answers = {}
for line in text.splitlines():
    line = line.strip()
    if not line.startswith("CS"):
        continue
    match = re.match(r"^CS\s+(\d+)\s*(Marks\s+to\s+All|[A-D])", line, re.IGNORECASE)
    if match:
        q_num = int(match.group(1))
        ans = match.group(2).strip()
        answers[q_num] = ans
    else:
        m2 = re.match(r"^CS\s+(\d+)([A-D])", line, re.IGNORECASE)
        if m2:
            q_num = int(m2.group(1))
            ans = m2.group(2).strip()
            answers[q_num] = ans

print(f"Loaded {len(answers)} official answers for 2012 CS.")

conn = sqlite3.connect('storage/gate_intelligence.db')
c = conn.cursor()

# Find 2012 CS questions
q_rows = c.execute(
    "SELECT id, question_number FROM questions WHERE examination_year = 2012 AND paper_code = 'CS'"
).fetchall()
print(f"Found {len(q_rows)} questions in DB for 2012 CS.")

updated_keys = 0
updated_options = 0

for q_id, q_num in q_rows:
    if q_num not in answers:
        continue
    ans_val = answers[q_num]
    if "marks" in ans_val.lower():
        correct_opts = ["A", "B", "C", "D"]
    else:
        correct_opts = [ans_val.upper()]
    
    # Update answer_keys
    c.execute(
        """
        UPDATE answer_keys
        SET correct_options_json = ?, provenance = 'official_iit'
        WHERE question_id = ?
        """,
        (json.dumps(correct_opts), q_id)
    )
    updated_keys += 1
    
    # Update question_options
    c.execute(
        """
        UPDATE question_options
        SET is_correct = CASE WHEN option_label IN ({seq}) THEN 1 ELSE 0 END
        WHERE question_id = ?
        """.format(seq=','.join(['?']*len(correct_opts))),
        (*correct_opts, q_id)
    )
    updated_options += c.rowcount

conn.commit()
print(f"Updated {updated_keys} answer_keys and {updated_options} options.")

# Verify
res = c.execute(
    "SELECT count(*) FROM answer_keys WHERE correct_options_json != '[]' AND correct_options_json IS NOT NULL"
).fetchone()[0]
print(f"Total answer_keys with verified answers now in DB: {res}")
conn.close()
