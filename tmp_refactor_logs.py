import os
import re

files_to_update = [
    r"c:\openClaw_Interview\main.py",
    r"c:\openClaw_Interview\src\agent.py",
    r"c:\openClaw_Interview\src\scheduler.py",
    r"c:\openClaw_Interview\src\whatsapp_client.py",
    r"c:\openClaw_Interview\src\channel_sender.py",
]

for file_path in files_to_update:
    if not os.path.exists(file_path):
        continue
        
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Check if logger is imported
    if "from src.logger_config import get_logger" not in content:
        # Insert import after the last import
        imports_end = [m.end() for m in re.finditer(r'^import [^\n]+|^from [^\n]+', content, re.MULTILINE)]
        if imports_end:
            insert_pos = imports_end[-1]
            content = content[:insert_pos] + '\nfrom src.logger_config import get_logger\nlogger = get_logger(os.path.basename(__file__) if "__file__" in locals() else "OpenClawBot")\n' + content[insert_pos:]
        else:
            content = 'import os\nfrom src.logger_config import get_logger\nlogger = get_logger("OpenClawBot")\n' + content

        # Remove old logging import in main.py
        content = re.sub(r'import logging\nlogging\.basicConfig[^\n]+\n', '', content)

    # Replace print("ERROR:...") with logger.error("...")
    content = re.sub(r'print\(\s*(f?"ERROR:\s*(.*?)["]\s*)[^)]*\)', r'logger.error(\1)', content)
    # Replace print("DEBUG:...") with logger.debug("...")
    content = re.sub(r'print\(\s*(f?"DEBUG:\s*(.*?)["]\s*)[^)]*\)', r'logger.debug(\1)', content)
    # Replace normal print(...) with logger.info(...)
    content = re.sub(r'print\(\s*([^)]*)\s*\)', r'logger.info(\1)', content)

    # Clean up instances like logger.info(f"ERROR: ...") that might have slipped due to missing "
    content = re.sub(r'logger\.info\(\s*(f?"ERROR:\s*(.*?)["])\s*\)', r'logger.error(\1)', content)
    content = re.sub(r'logger\.info\(\s*(f?"DEBUG:\s*(.*?)["])\s*\)', r'logger.debug(\1)', content)
    
    # Remove kwargs like flush=True from logger calls
    content = re.sub(r'(logger\.[a-z]+)\((.*?),\s*flush=True\s*\)', r'\1(\2)', content)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

print("Refactoring complete.")
