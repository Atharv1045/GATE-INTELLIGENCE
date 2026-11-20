import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO_ROOT = Path(__file__).resolve().parents[2]
ORIGINAL_DB = REPO_ROOT / "storage" / "gate_intelligence.db"
SCRATCH_DIR = Path(r"C:\Users\athar\.gemini\antigravity-cli\brain\305dbfd9-af4b-4b0e-9894-5e575eeb200b\scratch")
SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
TEST_DB = SCRATCH_DIR / "test_endpoints.db"
shutil.copy2(ORIGINAL_DB, TEST_DB)
os.environ["SQLITE_DB_PATH"] = str(TEST_DB)

from tests.direct_client import DirectTestClient

client = DirectTestClient()

print("=== 1. HEALTH CHECK ===")
res = client.get("/health")
print("Health:", res.status_code, res.json())

print("\n=== 2. QUESTION BANK ===")
res = client.get("/api/v1/questions?paper_code=CS&page=1&page_size=3")
print("Questions:", res.status_code, "Total:", res.json().get("total"), "Items:", len(res.json().get("items", [])))
q0 = res.json()["items"][0]
print("Q0:", q0["question_number"], q0["question_type"], q0["marks"], "Verified:", q0["answer_key"]["is_verified"])

# Test answer check on Q0
ans_check = client.post(f"/api/v1/questions/{q0['id']}/check", json={"selected_options": ["B"]})
print("Answer check result:", ans_check.status_code, ans_check.json())

print("\n=== 3. DASHBOARD ===")
res = client.get("/api/v1/dashboard/metrics?paper_code=CS")
print("Dashboard metrics:", res.status_code, res.json())
res = client.get("/api/v1/dashboard/progress?paper_code=CS")
print("Dashboard progress:", res.status_code, f"{len(res.json().get('subjects', []))} subjects")
res = client.get("/api/v1/dashboard/recent?paper_code=CS")
print("Dashboard recent activity:", res.status_code, f"{len(res.json().get('activity', []))} items")

print("\n=== 4. PAPER LIBRARY ===")
res = client.get("/api/v1/papers?paper_code=CS")
print("Papers list:", res.status_code, f"{len(res.json().get('papers', []))} papers")
paper0 = res.json()["papers"][0]
print("Paper 0:", paper0["title"], paper0["question_count"], "questions, verified:", paper0["verified_keys_count"])

res = client.get(f"/api/v1/papers/{paper0['id']}/questions")
print("Paper questions preview:", res.status_code, "Questions count:", res.json().get("total_questions"))

print("\n=== 5. PYQ ANALYTICS ===")
res = client.get("/api/v1/analytics/distributions?paper_code=CS")
print("Analytics distributions:", res.status_code)
d = res.json()
print("  Subjects:", len(d.get("subject_distribution", [])))
print("  Top topics:", len(d.get("topic_distribution", [])))
print("  Year trends:", len(d.get("year_trends", [])))
print("  Question types:", len(d.get("question_types", [])))
print("  Marks dist:", len(d.get("marks_distribution", [])))

print("\n=== 6. CBT MOCK TEST ===")
res = client.post("/api/v1/tests/start", json={"paper_code": "CS", "test_mode": "full", "duration_minutes": 180})
print("Test start:", res.status_code, res.json().get("title"), "Questions:", res.json().get("total_questions"))
test_id = res.json()["test_id"]
t_questions = res.json()["questions"]

# Submit test with answers
submit_payload = {
    "responses": [
        {"question_id": t_questions[0]["question_id"], "selected_options": ["B"], "time_spent_seconds": 60},
        {"question_id": t_questions[1]["question_id"], "selected_options": ["A"], "time_spent_seconds": 45},
    ]
}
sub_res = client.post(f"/api/v1/tests/{test_id}/submit", json=submit_payload)
print("Test submit:", sub_res.status_code)
s_data = sub_res.json()
print("  Total marks:", s_data.get("total_marks"), "Marks obtained:", s_data.get("marks_obtained"), "Accuracy:", s_data.get("accuracy_percent"))
print("  Correct:", s_data.get("correct_count"), "Incorrect:", s_data.get("incorrect_count"), "Unattempted:", s_data.get("unattempted_count"))

print("\n=== 7. LIGHTWEIGHT AGENTS ===")
res = client.post("/api/v1/agents/pyq-analysis", json={"paper_code": "CS"})
print("Agent 1 (PYQ):", res.status_code, res.json().get("agent_name"), "Insights:", res.json().get("insights"))
res = client.post("/api/v1/agents/performance", json={"paper_code": "CS"})
print("Agent 2 (Perf):", res.status_code, res.json().get("agent_name"), "Status:", res.json().get("status"), "Attempts:", res.json().get("total_attempts"))
res = client.post("/api/v1/agents/question-assistant", json={"question_id": q0["id"]})
print("Agent 3 (Q Assistant):", res.status_code, "Guidance:", res.json().get("guidance"))
res = client.post("/api/v1/agents/paper-analysis", json={"year": 2012, "paper_code": "CS"})
print("Agent 4 (Paper):", res.status_code, "Summary:", res.json().get("summary"))

print("\n=== 8. SETTINGS & DATA MANAGEMENT ===")
res = client.get("/api/v1/settings/info")
print("Settings info:", res.status_code, res.json())
res = client.get("/api/v1/settings/preferences")
print("Settings prefs:", res.status_code, res.json())
res = client.post("/api/v1/settings/backup")
print("Backup test:", res.status_code, res.json().get("backup_filename"))
