import json
import time

large_memories = {
    "preferences": [{"content": f"Preference {i}", "timestamp": int(time.time()) - i} for i in range(100)],
    "past_issues": [{"content": f"Past issue {i}", "timestamp": int(time.time()) - i*2} for i in range(1000)],
    "system_context": [{"content": f"System context {i}", "timestamp": int(time.time()) - i*3} for i in range(500)]
}

with open("memories.json", "w") as f:
    json.dump(large_memories, f, indent=2)