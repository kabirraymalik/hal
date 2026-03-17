import os
# ================ touch =====================
SKILLS_RELEVANT_THRESHOLD = 0.7
SKILL_RELEVANT_THRESHOLD = 0.5
SHORT_TERM_MEMORY_LEN = 3
# ============= DO NOT TOUCH =================
DEBUG = False
SHOW_CONTEXT = False
HAL_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_DIR = os.path.join(HAL_DIR, "memory")
ST_MEMORY_DIR = os.path.join(MEMORY_DIR, "st_memory.txt")
LT_MEMORY_DIR = os.path.join(MEMORY_DIR, "lt_memory.jsonl")