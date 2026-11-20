import json

with open('validation/reports/gate_cs_2012_after_fix.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

item = data['items'][0]
print("answer_key:", item['answer_key'])
print("options:", item['options'])
