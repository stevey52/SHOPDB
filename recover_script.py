import json
import os

transcript_path = r"C:\Users\mt\.gemini\antigravity\brain\d739364b-a4fa-4dc6-b0e6-ad2c13e1aa82\.system_generated\logs\transcript_full.jsonl"
output_path = r"C:\Users\mt\.gemini\antigravity\brain\d739364b-a4fa-4dc6-b0e6-ad2c13e1aa82\scratch\recovered_edits.md"

with open(transcript_path, 'r', encoding='utf-8') as f, open(output_path, 'w', encoding='utf-8') as out:
    for line in f:
        try:
            entry = json.loads(line)
            if 'tool_calls' in entry:
                for call in entry['tool_calls']:
                    name = call.get('name', call.get('function', {}).get('name'))
                    args = call.get('args', call.get('arguments', call.get('function', {}).get('arguments', {})))
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except:
                            args = {}
                    
                    target = args.get('TargetFile') or args.get('targetFile') or 'Unknown'
                    if name in ('default_api:write_to_file', 'write_to_file'):
                        out.write(f"### TOOL: {name}\n")
                        out.write(f"TARGET: {target}\n")
                        content = args.get('CodeContent') or args.get('codeContent') or ''
                        out.write("CONTENT:\n```python\n" + content + "\n```\n\n")
                    elif name in ('default_api:replace_file_content', 'replace_file_content'):
                        out.write(f"### TOOL: {name}\n")
                        out.write(f"TARGET: {target}\n")
                        content = args.get('ReplacementContent') or args.get('replacementContent') or ''
                        out.write("REPLACEMENT:\n```python\n" + content + "\n```\n\n")
                    elif name in ('default_api:multi_replace_file_content', 'multi_replace_file_content'):
                        out.write(f"### TOOL: {name}\n")
                        out.write(f"TARGET: {target}\n")
                        chunks = args.get('ReplacementChunks') or args.get('replacementChunks') or []
                        for chunk in chunks:
                            content = chunk.get('ReplacementContent') or chunk.get('replacementContent') or ''
                            out.write("CHUNK REPLACEMENT:\n```python\n" + content + "\n```\n\n")
        except Exception as e:
            pass
print("Recovery script finished.")
