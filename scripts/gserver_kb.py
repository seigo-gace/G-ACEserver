#!/usr/bin/env python3
"""Inspect the existing F: G-ACE KB Current from Gserver without changing it."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from kb_source import inspect, verify_existing_projection, verify_existing_counts, KBSourceError, F_ROOT


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=F_ROOT)
    p.add_argument("--verify-hashes", action="store_true",
                   help="Stream and verify six authoritative files; no indexing")
    p.add_argument("--verify-projection", action="store_true",
                   help="Run the existing read-only F: Dev KB byte-exact Current verifier")
    p.add_argument("--verify-counts", action="store_true",
                   help="Independently count actual JSONL record lines against ACTIVE authority")
    args = p.parse_args()
    print("========== GACE_RESULT_BEGIN ==========")
    print("PROJECT=Gserver")
    print("ACTION=DEV_KB_CURRENT_READ_ONLY")
    try:
        result = inspect(args.root, verify_hashes=(args.verify_hashes or args.verify_projection or args.verify_counts))
        print("KB_CURRENT=" + result["current"])
        print("HISTORICAL_FORMAL_PRESENT=" + str(result["historical_formal_corpus_present"]))
        print("KB_SOURCE_PRESENT=" + str(result["existing_kb_source_present"]))
        print("KB_SEARCH_CORPUS_PRESENT=" + str(result["search_corpus_present"]))
        print("EXISTING_WINDOWS_MVS_PRESENT=" + str(result["existing_windows_mvs_present"]))
        if "counts" in result:
            print("KB_CATALOG_COMMIT=" + result["catalog_commit"])
            for key, value in sorted(result["counts"].items()):
                print("KB_" + key.upper() + "=" + str(value))
        if args.verify_counts:
            verified_counts = verify_existing_counts(args.root, result)
            print("KB_JSONL_CARDINALITIES=PASS")
            for key, value in sorted(verified_counts["counts"].items()):
                print("KB_ACTUAL_" + key.upper() + "=" + str(value))
        else:
            print("KB_JSONL_CARDINALITIES=NOT_VERIFIED")
        if args.verify_projection:
            projection = verify_existing_projection(args.root, result)
            print("KB_EXISTING_RUNTIME_PROJECTION=" + projection["projection"])
        else:
            print("KB_EXISTING_RUNTIME_PROJECTION=NOT_VERIFIED")
        print("KB_SEARCH_E2E=NOT_VERIFIED")
        print("KB_CURRENT_CUTOVER=NOT_PERFORMED")
        print("F_SOURCE_MODIFIED=NONE")
        print("CHANGES=NONE")
        print("VERIFY=PASS")
        return 0
    except (KBSourceError, OSError, ValueError) as exc:
        code = str(exc) if isinstance(exc, KBSourceError) else type(exc).__name__
        print("KB_ERROR=" + code)
        print("F_SOURCE_MODIFIED=NONE")
        print("CHANGES=NONE")
        print("VERIFY=FAIL")
        return 1
    finally:
        print("PROJECT_END=Gserver")
        print("========== GACE_RESULT_END ==========")


if __name__ == "__main__":
    raise SystemExit(main())
