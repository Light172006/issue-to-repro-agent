import json
import os
import sys
import time
from pathlib import Path

import docker
import httpx

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, 'src')
sys.path.insert(0, '.')

for line in Path('.env').read_text(encoding='utf-8-sig').splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip('\'"'))

from scripts.validate_dataset import validate_candidate

from repro.envbuilder import EnvironmentBuilder


def run_pass(pass_num, candidates, dc, hc, builder, runs_dir):
    print(f"\n==================== STARTING VALIDATION PASS {pass_num} ====================")
    results = {}
    for c in candidates:
        cid = c['id']
        start_t = time.time()
        ok, val_meta, reason = validate_candidate(c, dc, hc, builder, runs_dir / f'p{pass_num}')
        duration = time.time() - start_t
        results[cid] = {
            'accepted': ok,
            'reason': reason,
            'duration': duration,
            'meta': val_meta
        }
        status_str = "ACCEPTED" if ok else "REJECTED"
        print(f"[{status_str}] {cid:<20} in {duration:.1f}s - {reason[:60]}")
    return results

def main():
    dataset_path = Path('bench/dataset.json')
    candidates = json.loads(dataset_path.read_text(encoding='utf-8'))
    print(f"Loaded {len(candidates)} candidates from {dataset_path}")
    
    token = os.environ.get('GITHUB_TOKEN')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
        
    dc = docker.from_env()
    hc = httpx.Client(headers=headers, timeout=20)
    builder = EnvironmentBuilder(dc, hc)
    runs_dir = Path('runs/double_validation')
    runs_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        pass1 = run_pass(1, candidates, dc, hc, builder, runs_dir)
        pass2 = run_pass(2, candidates, dc, hc, builder, runs_dir)
        
        print("\n==================== COMPARISON & FLAKINESS CHECK ====================")
        discrepancies = []
        for c in candidates:
            cid = c['id']
            r1 = pass1[cid]
            r2 = pass2[cid]
            if r1['accepted'] != r2['accepted']:
                discrepancies.append((cid, r1, r2))
                print(f"FLAKY: {cid} differed between Pass 1 ({r1['accepted']}) and Pass 2 ({r2['accepted']})")
        
        if not discrepancies:
            print("ALL 18 CANDIDATES PRODUCED IDENTICAL OUTCOMES IN BOTH PASSES! Zero flakiness detected.")
        else:
            print(f"WARNING: {len(discrepancies)} flakiness discrepancies found!")
            
        # Write summary JSON for auditing
        summary = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(candidates),
            'discrepancies': len(discrepancies),
            'pass1': pass1,
            'pass2': pass2
        }
        (runs_dir / 'double_validation_results.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
        print(f"Results saved to {runs_dir / 'double_validation_results.json'}")
        
    finally:
        hc.close()
        dc.close()

if __name__ == '__main__':
    main()
