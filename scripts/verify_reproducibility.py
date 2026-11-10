"""Regenerate twice with identical parameters and compare checksums, row counts and PK sequences."""
from __future__ import annotations
import argparse, csv, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def checksums(paths):
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in paths if p.exists() and p.is_file()}

def csv_evidence(paths):
    counts, pk_hashes = {}, {}
    for path in paths:
        if path.suffix != ".csv" or not path.exists():
            continue
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, [])
            ids = [row[0] for row in reader if row]
        name = str(path.relative_to(ROOT))
        counts[name] = len(ids)
        pk_hashes[name] = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    return counts, pk_hashes

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scale", choices=("starter", "full"), default="starter")
    parser.add_argument("--seed", type=int, default=20261022)
    args = parser.parse_args()
    command = [sys.executable, "-m", "scripts.generate_data", "--scale", args.scale, "--seed", str(args.seed)]
    subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    tracked = [ROOT / "manifest.json", ROOT / "data/generated/database/seed.sql",
               ROOT / "data/ground_truth/ground_truth.csv", ROOT / "data/anomalies/anomaly_cases.json"]
    tracked += sorted((ROOT / "data/generated/csv").glob("*.csv"))
    tracked += sorted((ROOT / "data/generated/json").glob("*.json"))
    first_hashes = checksums(tracked)
    first_counts, first_pks = csv_evidence(tracked)
    with tempfile.TemporaryDirectory() as temp:
        snapshot = Path(temp)
        for rel in first_hashes:
            dest = snapshot / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dest)
        subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
        second_hashes = checksums(tracked)
        second_counts, second_pks = csv_evidence(tracked)
    differences = [name for name in first_hashes if first_hashes[name] != second_hashes.get(name)]
    counts_match = first_counts == second_counts
    pks_match = first_pks == second_pks
    result = {"status": "PASS" if not differences and counts_match and pks_match else "FAIL",
              "scale": args.scale, "seed": args.seed, "files_compared": len(first_hashes),
              "mismatched_files": differences, "row_counts_match": counts_match,
              "row_counts": second_counts, "primary_key_sequences_match": pks_match,
              "primary_key_sequence_hashes": second_pks, "checksums": second_hashes}
    out = ROOT / "reports" / "reproducibility_report.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k not in ("checksums", "primary_key_sequence_hashes")}, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)

if __name__ == "__main__": main()
