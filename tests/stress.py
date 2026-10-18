"""Stress test: a large synthetic CapabilityAccessManager.db through the real SQLECmd, timed.

    python tests/stress.py C:\\Tools\\SQLECmd.exe [--usage 200000 --identities 50000 --prompts 50000]

Reports wall time, peak memory (psutil, if installed) and checks that every row came out.
"""
import argparse
import csv
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixtures  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_measured(cmd, log_path):
    try:
        import psutil
    except ImportError:
        psutil = None
    with open(log_path, 'w', encoding='utf-8') as log:
        p = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.path.dirname(log_path))
        peak = 0
        proc = psutil.Process(p.pid) if psutil else None
        while p.poll() is None:
            if proc:
                try:
                    peak = max(peak, proc.memory_info().rss)
                except psutil.Error:
                    pass
            time.sleep(0.1)
    return p.returncode, (f'{peak / 1e6:.0f}' if proc else 'n/a (pip install psutil)')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('sqlecmd')
    ap.add_argument('--usage', type=int, default=200_000)
    ap.add_argument('--identities', type=int, default=50_000)
    ap.add_argument('--prompts', type=int, default=50_000)
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix='cam_stress_')
    try:
        t0 = time.time()
        n = fixtures.build_cam_stress(os.path.join(work, 'in'), a.usage, a.identities, a.prompts)
        print(f'built {n} in {time.time() - t0:.1f}s')
        out = os.path.join(work, 'out')
        cmd = [a.sqlecmd, '-d', os.path.join(work, 'in'), '--hunt', '--maps', os.path.join(ROOT, 'maps'),
               '--csv', os.path.join(out, 'csv')]
        t0 = time.time()
        rc, peak = run_measured(cmd, os.path.join(work, 'console.log'))
        wall = time.time() - t0
        counts = {}
        for f in glob.glob(os.path.join(out, 'csv', '*.csv')):
            with open(f, encoding='utf-8-sig', newline='') as fh:
                counts[os.path.basename(f).split('_', 1)[1]] = sum(1 for _ in csv.reader(fh)) - 1
        print(f'SQLECmd exit={rc} wall={wall:.1f}s peak_memory={peak} MB')
        for k, v in sorted(counts.items()):
            print(f'  {k}: {v} rows')
        want = {'PackagedUsageHistory': n['usage'], 'NonPackagedUsageHistory': n['usage'],
                'NonPackagedIdentityRelationship': n['identities'], 'NonPackagedGlobalPromptHistory': n['prompts']}
        ok = rc == 0 and all(any(k.startswith(f'CapabilityAccessManager_{q}_') and v == c for k, v in counts.items())
                             for q, c in want.items())
        print('RESULT:', 'PASS' if ok else 'FAIL')
        sys.exit(0 if ok else 1)
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
