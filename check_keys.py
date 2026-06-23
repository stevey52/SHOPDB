import json

transcript_path = r"C:\Users\mt\.gemini\antigravity\brain\d739364b-a4fa-4dc6-b0e6-ad2c13e1aa82\.system_generated\logs\transcript_full.jsonl"

with open(transcript_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            entry = json.loads(line)
            if 'tool_calls' in entry:
                for call in entry['tool_calls']:
                    print(json.dumps(call, indent=2))
                    break
                break
        except Exception as e:
            pass
