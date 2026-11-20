import pypdf
import re
import json

reader = pypdf.PdfReader('validation/uploads/2012_CS.pdf')
text = reader.pages[17].extract_text() + "\n" + reader.pages[18].extract_text()

# We need Code A answers for Q 1 to 65
# The table has lines like:
# "CS  1B                          C                         B                         D                         "
# or "CS  10 C                         C                         Marks to All              D                         "
# or "CS  3 Marks to All              C                         C                         C                         "
# Let's inspect the regex matching
lines = text.splitlines()
answers = {}
for line in lines:
    line = line.strip()
    if not line.startswith("CS"):
        continue
    # Format: CS followed by question number and Code A
    # E.g. CS  1B or CS 10 C or CS 3 Marks to All
    match = re.match(r"^CS\s+(\d+)\s*(Marks\s+to\s+All|[A-D])", line, re.IGNORECASE)
    if match:
        q_num = int(match.group(1))
        ans = match.group(2).strip()
        answers[q_num] = ans
    else:
        # Check if question number is immediately followed by letter without space, e.g. 1B
        m2 = re.match(r"^CS\s+(\d+)([A-D])", line, re.IGNORECASE)
        if m2:
            q_num = int(m2.group(1))
            ans = m2.group(2).strip()
            answers[q_num] = ans

print(f"Extracted {len(answers)} answers out of 65:")
for q in range(1, 66):
    print(f"Q{q}: {answers.get(q, 'MISSING')}", end=", " if q % 5 != 0 else "\n")
