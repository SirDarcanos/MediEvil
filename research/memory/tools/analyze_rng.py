#!/usr/bin/env python3
"""Validate observed native RNG steps; report consumers without inventing outcomes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

STATE = 0x800F3994
MULTIPLIER = 0x41C64E6D
INCREMENT = 0x3039


def step(state):
    state = (state * MULTIPLIER + INCREMENT) & 0xffffffff
    return state, (state >> 16) & 0x7fff


def analyze(rows):
    if not rows:
        raise ValueError('No RNG execution callbacks captured')
    discontinuities = []
    previous = None
    for index, row in enumerate(rows):
        state, output = step(row['before'])
        if state != row['afterRegister'] or output != row['output']:
            raise ValueError(f'Native RNG mismatch at call {index}')
        if previous is not None and row['before'] != previous:
            discontinuities.append({'call': index, 'previous_after': previous,
                                    'next_before': row['before'], 'frame': row['frame']})
        previous = state
    return {'calls': len(rows), 'validated_native_steps': len(rows),
            'state_address': f'0x{STATE:08X}', 'multiplier': f'0x{MULTIPLIER:08X}',
            'increment': f'0x{INCREMENT:08X}', 'first_state': rows[0]['before'],
            'last_state': rows[-1]['afterRegister'],
            'caller_return_addresses': dict(Counter(f"0x{r['callerRA']:08X}" for r in rows)),
            'submode_calls': dict(Counter(str(r['submode']) for r in rows)),
            'state_discontinuities': discontinuities,
            'scope': 'Exact native PRNG steps/callers in this trace window. Scratch actor is only a context hint. Discontinuities need reseed/write tracing; no combat outcome manipulation is implied.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    run = json.loads((args.run / 'run.json').read_text())
    if not run.get('semantic_pass'):
        parser.error('Run has not passed its declared semantic checks')
    trace = args.run / 'rng-calls.jsonl'
    result = analyze([json.loads(line) for line in trace.read_text().splitlines()])
    result.update(run_id=args.run.name, probe_sha256=run['probe_sha256'],
                  seed_sha256=run['seed_sha256'], instrumentation=run['instrumentation'],
                  trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    else:
        print(text, end='')


if __name__ == '__main__':
    main()
