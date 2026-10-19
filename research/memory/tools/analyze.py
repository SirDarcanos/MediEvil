#!/usr/bin/env python3
"""Compare every byte of captured 2 MiB RAM; report observations, not inferred names."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

RAM_SIZE = 0x200000


def compare_all(paths):
    changed = bytearray(RAM_SIZE)
    previous = None
    captures = []
    for path in paths:
        data = path.read_bytes()
        if len(data) != RAM_SIZE:
            raise ValueError(f'{path}: expected exactly 2 MiB')
        captures.append({'file': path.name, 'size': len(data),
                         'sha256': hashlib.sha256(data).hexdigest()})
        if previous is not None:
            # Every address is compared, including unaligned bytes and code/data.
            for offset, (old, new) in enumerate(zip(previous, data)):
                if old != new:
                    changed[offset] = 1
        previous = data
    if len(captures) < 2:
        raise ValueError('Need at least two complete captures for a RAM comparison')
    return {'bytes_compared_per_pair': RAM_SIZE, 'capture_count': len(captures),
            'changed_bytes': sum(changed), 'captures': captures,
            'changed_bytes_by_4KiB': [sum(changed[i:i+4096]) for i in range(0, RAM_SIZE, 4096)]}


def summarize(samples):
    groups = defaultdict(list)
    for sample in samples:
        groups[sample['phase']].append(sample)
    result = {}
    for phase, rows in groups.items():
        fields = {}
        for key in sorted(set().union(*(row.keys() for row in rows)) - {'phase'}):
            values = [row[key] for row in rows if key in row]
            distinct = set(values)
            fields[key] = {'min': min(values), 'max': max(values), 'distinct': len(distinct)}
            if len(distinct) <= 12:
                fields[key]['values'] = sorted(distinct)
        live = [r for r in rows if r.get('mode') == 3 and all(k in r for k in
                ('x', 'y', 'z', 'fixedX', 'fixedY', 'fixedZ'))]
        errors = []
        for axis in ('X', 'Y', 'Z'):
            differences = [abs(r[axis.lower()] - r['fixed'+axis] / 65536) for r in live]
            errors.append(max(differences, default=None))
        result[phase] = {'samples': len(rows), 'fields': fields,
                         'max_actor_physics_difference_xyz': errors}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    results = []
    for run in args.runs:
        record = json.loads((run / 'run.json').read_text())
        if (record.get('exit_code') != 0 or record.get('interrupted')
                or record.get('semantic_pass') is not True):
            raise ValueError(f'{run}: no successful gameplay verification; normal process exit alone is insufficient')
        samples = [json.loads(line) for line in (run/'samples.jsonl').read_text().splitlines()]
        if not samples or samples[-1]['phase'] != 'finished':
            raise ValueError(f'{run}: missing normal completion sample')
        results.append({'run': record, 'full_ram_scan': compare_all(sorted(run.glob('*.ram'))),
                        'observations': summarize(samples)})
        print(f'{run}: {len(samples)} samples', flush=True)
    args.output.write_text(json.dumps({'runs': results}, indent=2) + '\n')


if __name__ == '__main__':
    main()
