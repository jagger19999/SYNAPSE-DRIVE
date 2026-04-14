import csv
import os
import sys
from datetime import datetime


def _parse_dt(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None


def verify_driving_csv(csv_path: str):
    total = 0
    first_dt = None
    last_dt = None
    max_gap = 0.0
    gaps_200ms = 0
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            total += 1
            dt = _parse_dt(row.get("system_timestamp", ""))
            if dt is None:
                continue
            if first_dt is None:
                first_dt = dt
            if last_dt is not None:
                gap = (dt - last_dt).total_seconds()
                if gap > max_gap:
                    max_gap = gap
                if gap >= 0.2:
                    gaps_200ms += 1
            last_dt = dt
    duration = (last_dt - first_dt).total_seconds() if first_dt and last_dt and last_dt >= first_dt else None
    rate = (total / duration) if duration and duration > 0 else None
    return {
        "path": csv_path,
        "rows": total,
        "start": first_dt.isoformat(sep=" ") if first_dt else None,
        "end": last_dt.isoformat(sep=" ") if last_dt else None,
        "duration_s": duration,
        "est_rate_hz": rate,
        "max_gap_s": max_gap,
        "gap_ge_200ms": gaps_200ms,
    }


def verify_uxf_trackers_folder(trackers_dir: str, expected_blocks=4):
    result = {"trackers_dir": trackers_dir, "block_files": [], "errors": []}
    if not os.path.isdir(trackers_dir):
        result["errors"].append("trackers_dir_not_found")
        return result

    for b in range(1, expected_blocks + 1):
        found = []
        suffix = f"_B{b:02d}.csv"
        for name in os.listdir(trackers_dir):
            if name.endswith(suffix):
                found.append(os.path.join(trackers_dir, name))
        if not found:
            result["errors"].append(f"missing_block_{b:02d}")
        else:
            result["block_files"].extend(found)

    for p in result["block_files"]:
        try:
            with open(p, "r", encoding="utf-8-sig", newline="") as f:
                header = f.readline().strip()
            cols = [c.strip().strip('"') for c in header.split(",")]
            if len(cols) < 2 or cols[0] != "host_timestamp" or cols[1] != "time":
                result["errors"].append(f"bad_header:{os.path.basename(p)}")
        except Exception:
            result["errors"].append(f"read_failed:{os.path.basename(p)}")

    return result


def main(argv):
    if len(argv) < 2:
        print("用法:")
        print("  python verify_output_integrity.py driving <driving_csv_path>")
        print("  python verify_output_integrity.py uxf <trackers_dir>")
        return 2

    mode = argv[1].lower()
    if mode == "driving" and len(argv) >= 3:
        p = argv[2]
        print(verify_driving_csv(p))
        return 0
    if mode == "uxf" and len(argv) >= 3:
        p = argv[2]
        print(verify_uxf_trackers_folder(p))
        return 0

    print("参数错误")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

