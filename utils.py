import sys
import os
import config

def dbg(msg):
    if config.DEBUG:
        print(f"[dbg] {msg}", file=sys.stderr)

def dbg_context(msg):
    if config.SHOW_CONTEXT:
        print(f"[ctx] {msg}", file=sys.stderr)

def select_models(operating_system):
    if operating_system == "windows":
        return "null", "null" # TODO: define and tune
    elif operating_system == "linux":
        return "devstral_small", "devstral_large" # TODO: define and tune
    elif operating_system == "mac":
        # return "qwen3:4b", "qwen3:30b-a3b"
        return "llama3.2:3b", "qwen3.5:9b" #"gemma3:4b" #"rnj-1" 
    return "null", "null"