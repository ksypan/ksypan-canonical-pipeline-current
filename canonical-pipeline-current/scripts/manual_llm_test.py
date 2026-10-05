"""Opt-in, single-document integration test. Not discovered by unittest.

Prints only targets and model data, never headers/configuration or raw errors.
The client may read local .env configuration; no .env is created or saved.
No merging or submission generation.
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.llm_client import LLMClientError, YandexConfig, call_llm
from pipeline.parser import extract_epicrisis
from pipeline.prompt_builder import build_llm_request

def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--input", type=Path, default=Path(__file__).resolve().parent.parent / "train-0003.md")
    cli.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds")
    args = cli.parse_args(argv)
    started_at = None
    try:
        config = YandexConfig.from_env()
        text = args.input.read_text(encoding="utf-8-sig")
        
        redacted_text, record = extract_epicrisis(text)
        
        # Build request with deidentified text
        request = build_llm_request(redacted_text, record)
        
        print("target_fields:")
        print(json.dumps(request["target_fields"], ensure_ascii=False, indent=2))
        started_at = time.perf_counter()
        result = call_llm(
            request, config=config,
            timeout=args.timeout,
        )

        print(f"LLM response time: {time.perf_counter() - started_at:.1f} s")
        print("LLM JSON:")
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except LLMClientError as error:
        print("Ошибка: " + str(error), file=sys.stderr)
        return 1
    except (OSError, UnicodeError):
        print("Не удалось прочитать входной эпикриз в UTF-8.", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
