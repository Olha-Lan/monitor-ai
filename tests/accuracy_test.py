"""
Accuracy test for Monitor-AI.
Compares app readings against Windows native data sources:
  - CPU: GetSystemTimes() Windows API (same source as Task Manager / psutil)
  - RAM: Win32_OperatingSystem WMI (authoritative memory data)

Error metrics:
  - CPU:  absolute difference in percentage points (goal: < 1 pp)
          Relative % error is misleading for volatile metrics near 0-100.
  - RAM:  relative % error (goal: < 1%)
          RAM is stable and relative error is meaningful here.
"""
import ctypes
import subprocess
import threading
import time
import statistics
import sys
import psutil

SAMPLES = 10
CPU_GOAL_PP = 1.0   # max acceptable CPU difference in percentage points
RAM_GOAL_PCT = 1.0  # max acceptable RAM relative error %


# ── CPU reference: Windows GetSystemTimes() ──────────────────────

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime",  ctypes.c_uint32),
                ("dwHighDateTime", ctypes.c_uint32)]


def _ft_to_int(ft):
    return (ft.dwHighDateTime << 32) | ft.dwLowDateTime


def get_windows_cpu_api(interval=1.0):
    """
    Measure CPU % using GetSystemTimes() directly.
    This is exactly the same Windows API that psutil and Task Manager use.
    """
    idle1, kernel1, user1 = FILETIME(), FILETIME(), FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle1), ctypes.byref(kernel1), ctypes.byref(user1)
    )
    time.sleep(interval)
    idle2, kernel2, user2 = FILETIME(), FILETIME(), FILETIME()
    ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2)
    )
    d_idle   = _ft_to_int(idle2)   - _ft_to_int(idle1)
    d_kernel = _ft_to_int(kernel2) - _ft_to_int(kernel1)
    d_user   = _ft_to_int(user2)   - _ft_to_int(user1)
    d_total  = d_kernel + d_user
    if d_total == 0:
        return 0.0
    return round((d_total - d_idle) / d_total * 100, 1)


# ── psutil functions (same as app.py) ────────────────────────────

def get_psutil_cpu(interval=1.0):
    return psutil.cpu_percent(interval=interval)


def get_psutil_ram():
    mem = psutil.virtual_memory()
    return {
        "used_mb":  round(mem.used  / 1024 / 1024),
        "total_mb": round(mem.total / 1024 / 1024),
        "percent":  mem.percent,
    }


# ── RAM reference: WMI Win32_OperatingSystem ─────────────────────

_RAM_PS = (
    r"$os = Get-CimInstance -ClassName Win32_OperatingSystem; "
    r"$used  = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1024); "
    r"$total = [math]::Round($os.TotalVisibleMemorySize/1024); "
    r"$pct   = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)"
    r"/$os.TotalVisibleMemorySize*100,1); "
    r'"$used $total $pct"'
)


def get_windows_ram_wmi():
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", _RAM_PS],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"WMI RAM failed: {result.stderr}")
    parts = result.stdout.strip().split()
    return {
        "used_mb":  int(parts[0]),
        "total_mb": int(parts[1]),
        "percent":  float(parts[2]),
    }


# ── Simultaneous measurement pair ────────────────────────────────

def measure_pair():
    psutil_r  = {}
    win_cpu_r = {}
    win_ram_r = {}
    errors    = []

    def run_psutil():
        try:
            psutil_r["cpu"] = get_psutil_cpu(interval=1)
            psutil_r["ram"] = get_psutil_ram()
        except Exception as exc:
            errors.append(f"psutil: {exc}")

    def run_win_cpu():
        try:
            win_cpu_r["cpu"] = get_windows_cpu_api(interval=1)
        except Exception as exc:
            errors.append(f"win_cpu: {exc}")

    def run_win_ram():
        try:
            win_ram_r["ram"] = get_windows_ram_wmi()
        except Exception as exc:
            errors.append(f"win_ram: {exc}")

    threads = [
        threading.Thread(target=run_psutil),
        threading.Thread(target=run_win_cpu),
        threading.Thread(target=run_win_ram),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if errors:
        raise RuntimeError("; ".join(errors))

    return psutil_r, {**win_cpu_r, **win_ram_r}


# ── Main ─────────────────────────────────────────────────────────

def run_accuracy_test():
    print()
    print("=" * 72)
    print("  Monitor-AI  —  Accuracy Test vs Windows Native APIs")
    print("=" * 72)
    print("  CPU ref : GetSystemTimes()  (same API as Task Manager & psutil)")
    print("  RAM ref : Win32_OperatingSystem WMI")
    print(f"  Samples : {SAMPLES}   CPU interval: 1 s per sample")
    print()

    psutil.cpu_percent(interval=None)   # prime the counter
    time.sleep(0.3)

    rows = []
    cpu_diffs     = []   # absolute difference in percentage points
    ram_used_errs = []   # relative %
    ram_tot_errs  = []   # relative %
    ram_pct_errs  = []   # relative %

    for i in range(1, SAMPLES + 1):
        print(f"  Collecting sample {i:>2}/{SAMPLES} ...", end="\r", flush=True)
        our, win = measure_pair()

        cpu_diff    = abs(our["cpu"]            - win["cpu"])
        ru_err      = abs(our["ram"]["used_mb"] - win["ram"]["used_mb"]) \
                      / win["ram"]["used_mb"] * 100
        rt_err      = abs(our["ram"]["total_mb"] - win["ram"]["total_mb"]) \
                      / win["ram"]["total_mb"] * 100  if win["ram"]["total_mb"] else 0
        rp_err      = abs(our["ram"]["percent"] - win["ram"]["percent"]) \
                      / win["ram"]["percent"] * 100   if win["ram"]["percent"] else 0

        cpu_diffs.append(cpu_diff)
        ram_used_errs.append(ru_err)
        ram_tot_errs.append(rt_err)
        ram_pct_errs.append(rp_err)

        rows.append({
            "i":         i,
            "our_cpu":   our["cpu"],
            "win_cpu":   win["cpu"],
            "cpu_diff":  cpu_diff,
            "our_used":  our["ram"]["used_mb"],
            "win_used":  win["ram"]["used_mb"],
            "our_total": our["ram"]["total_mb"],
            "win_total": win["ram"]["total_mb"],
            "our_rpct":  our["ram"]["percent"],
            "win_rpct":  win["ram"]["percent"],
        })

    print()

    # ── Per-sample table ─────────────────────────────────────────
    print("  Per-sample readings:")
    sep = "  " + "-" * 76
    print(f"  {'#':>2}  {'App CPU':>8}  {'Win CPU':>8}  {'Diff':>5}  "
          f"{'App RAM%':>9}  {'Win RAM%':>9}  {'App MB':>9}  {'Win MB':>9}")
    print(sep)
    for r in rows:
        print(f"  {r['i']:>2}  "
              f"{r['our_cpu']:>7.1f}%  {r['win_cpu']:>7.1f}%  "
              f"{r['cpu_diff']:>4.1f}pp  "
              f"{r['our_rpct']:>8.1f}%  {r['win_rpct']:>8.1f}%  "
              f"{r['our_used']:>8,}  {r['win_used']:>8,}")

    # ── Summary table ────────────────────────────────────────────
    avg_cpu_diff = statistics.mean(cpu_diffs)
    max_cpu_diff = max(cpu_diffs)
    avg_ru       = statistics.mean(ram_used_errs)
    max_ru       = max(ram_used_errs)
    avg_rt       = statistics.mean(ram_tot_errs)
    max_rt       = max(ram_tot_errs)
    avg_rp       = statistics.mean(ram_pct_errs)
    max_rp       = max(ram_pct_errs)

    cpu_pass  = avg_cpu_diff < CPU_GOAL_PP
    ru_pass   = avg_ru       < RAM_GOAL_PCT
    rt_pass   = avg_rt       < RAM_GOAL_PCT
    rp_pass   = avg_rp       < RAM_GOAL_PCT
    all_pass  = cpu_pass and ru_pass and rt_pass and rp_pass

    avgs_our = {
        "cpu":   statistics.mean(r["our_cpu"]   for r in rows),
        "used":  statistics.mean(r["our_used"]  for r in rows),
        "total": statistics.mean(r["our_total"] for r in rows),
        "rpct":  statistics.mean(r["our_rpct"]  for r in rows),
    }
    avgs_win = {
        "cpu":   statistics.mean(r["win_cpu"]   for r in rows),
        "used":  statistics.mean(r["win_used"]  for r in rows),
        "total": statistics.mean(r["win_total"] for r in rows),
        "rpct":  statistics.mean(r["win_rpct"]  for r in rows),
    }

    print()
    print("  Accuracy Summary (average over 10 samples):")
    print()
    print(f"  {'Metric':<22}  {'App Avg':>9}  {'Win Avg':>9}  "
          f"{'Avg Err':>9}  {'Max Err':>9}  {'Goal':>10}  {'Result':>6}")
    print("  " + "-" * 85)

    def row_str(name, app, win, avg_e, max_e, goal_str, passed):
        tag = "PASS" if passed else "FAIL"
        return (f"  {name:<22}  {app:>9}  {win:>9}  "
                f"{avg_e:>9}  {max_e:>9}  {goal_str:>10}  {tag:>6}")

    print(row_str(
        "CPU %",
        f"{avgs_our['cpu']:.1f}%", f"{avgs_win['cpu']:.1f}%",
        f"{avg_cpu_diff:.2f} pp", f"{max_cpu_diff:.2f} pp",
        "< 1.0 pp", cpu_pass,
    ))
    print(row_str(
        "RAM used (MB)",
        f"{avgs_our['used']:.0f}", f"{avgs_win['used']:.0f}",
        f"{avg_ru:.2f}%", f"{max_ru:.2f}%",
        "< 1.0%", ru_pass,
    ))
    print(row_str(
        "RAM total (MB)",
        f"{avgs_our['total']:.0f}", f"{avgs_win['total']:.0f}",
        f"{avg_rt:.2f}%", f"{max_rt:.2f}%",
        "< 1.0%", rt_pass,
    ))
    print(row_str(
        "RAM %",
        f"{avgs_our['rpct']:.1f}%", f"{avgs_win['rpct']:.1f}%",
        f"{avg_rp:.2f}%", f"{max_rp:.2f}%",
        "< 1.0%", rp_pass,
    ))

    print()
    print("  Notes:")
    print("  - CPU goal is in percentage POINTS (pp), not relative %.")
    print("    Relative error is misleading for CPU (30% load -> 1pp diff = 3% relative).")
    print("  - Tiny CPU diff (~0.5 pp) = thread scheduling jitter, not app error.")
    print("  - RAM delta (App vs Win): WMI counts 'standby' pages differently than psutil.")
    print()
    print("=" * 72)
    print(f"  VERDICT: {'ALL GOALS MET' if all_pass else 'SOME GOALS NOT MET'}")
    print("=" * 72)
    print()

    return all_pass


if __name__ == "__main__":
    success = run_accuracy_test()
    sys.exit(0 if success else 1)
