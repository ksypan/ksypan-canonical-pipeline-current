"""Development-only batch runner for text files in input/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.processor import process_epicrisis_bundle
from pipeline.evidence import write_evidence


def run_batch(input_dir: Path, output_dir: Path, evidence_dir: Path | None = None, llm_call=None) -> tuple[int, int, int]:
    files = sorted({*input_dir.glob("*.txt"), *input_dir.glob("*.md")})
    output_dir.mkdir(parents=True, exist_ok=True)
    if evidence_dir is not None:
        evidence_dir.mkdir(parents=True, exist_ok=True)
        (evidence_dir / "text").mkdir(parents=True, exist_ok=True)
    success = failed = 0
    for path in files:
        try:
            bundle = process_epicrisis_bundle(path.read_text(encoding="utf-8-sig"), document=path.stem, llm_call=llm_call)
            (output_dir / f"{path.stem}.json").write_text(json.dumps(bundle["result"], ensure_ascii=False, indent=2), encoding="utf-8")
            if evidence_dir is not None:
                write_evidence(evidence_dir / f"{path.stem}.evidence.json", bundle["evidence"])
                (evidence_dir / "text" / f"{path.stem}.md").write_text(bundle["text"], encoding="utf-8")
            success += 1
            print(f"OK   {path.name}")
        except Exception as exc:  # one bad document must not stop the batch
            failed += 1
            print(f"FAIL {path.name}: {exc}")
    print(f"processed: {len(files)}")
    print(f"success: {success}")
    print(f"failed: {failed}")
    return len(files), success, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("input"))
    parser.add_argument("--output-dir", type=Path, default=Path("result"))
    parser.add_argument("--evidence-dir", type=Path, default=Path("evidence"))
    args = parser.parse_args()
    _, _, failed = run_batch(args.input_dir, args.output_dir, args.evidence_dir)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
