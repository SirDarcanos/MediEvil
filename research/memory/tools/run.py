#!/usr/bin/env python3
"""Finite isolated PCSX-Redux RAM capture. Uses only Python's standard library.

Raw RAM/save states stay outside Git: they contain copyrighted game data.
All input goes to a new CLI-only child, never a user's existing emulator.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROBE = ROOT / 'probes' / 'probe.lua'
EXE_SHA1 = '265ce5dc508002a339ae535e49a5b1b4e683b732'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def private_emulator(source, run):
    """A distinct executable name keeps this child out of canonical Redux discovery.

    Copy only to our new run directory; never rename/re-sign/edit the source app.
    The Mach-O bytes remain identical. Web/GDB services are disabled at launch.
    """
    original_app = source.parents[2]
    target_app = run / 'ReduxAudit.app'
    shutil.copytree(original_app, target_app, symlinks=True)
    copied = target_app / 'Contents/MacOS' / source.name
    private = copied.with_name('ReduxAudit')
    copied.rename(private)
    if sha256(private) != sha256(source):
        raise ValueError('Private emulator copy differs from source')
    return private


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--bios', type=Path, required=True)
    parser.add_argument('--scenario', choices=('boot', 'movement', 'actions', 'ui'), required=True)
    parser.add_argument('--seed', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--probe', type=Path, default=DEFAULT_PROBE)
    parser.add_argument('--level-setup', action='store_true',
                        help='Explicitly label the boss probe\'s three level-dispatch setup writes')
    parser.add_argument('--wake-setup', action='store_true',
                        help='Label Pumpkin wake-gate setup; never HP/HUD injection')
    parser.add_argument('--trace-rng', action='store_true',
                        help='Enable only the private interpreter debugger for non-pausing RNG callbacks; no GDB/web server')
    parser.add_argument('--relocation-setup', action='store_true',
                        help='Label the arena-seed laboratory position writes, never an in-game skip')
    parser.add_argument('--trace-position', action='store_true',
                        help='Observe private actor/physics position writers during arena setup')
    parser.add_argument('--intro-setup', action='store_true',
                        help='Explicit final-arena introduction prerequisite; not a natural encounter entry')
    parser.add_argument('--ally-heal-setup', action='store_true',
                        help='Explicit assisted boss preparation; restores allied skeleton HP only')
    parser.add_argument('--combat-supply-setup', action='store_true',
                        help='Explicit combat lab: restore living player HP and dagger ammo only')
    parser.add_argument('--boss-last-hit-setup', action='store_true',
                        help='Explicitly reduce each owned boss to 6 HP once, then require a native killing blow')
    parser.add_argument('--timeout-seconds', type=int, default=180,
                        help='Private emulator wall-time limit (30..900 seconds)')
    args = parser.parse_args()
    if not 30 <= args.timeout_seconds <= 900:
        parser.error('--timeout-seconds must be between 30 and 900')
    game = args.game.expanduser().resolve()
    emulator = game / 'tools/PCSX-Redux.app/Contents/MacOS/PCSX-Redux'
    bios = args.bios.expanduser().resolve()
    cue = game / 'MediEvil (USA).cue'
    probe = args.probe.expanduser().resolve()
    exe = game / 'EXE/MEDIEVIL.EXE'
    if probe.name == 'boss.lua' and not args.level_setup:
        parser.error('boss.lua requires --level-setup; do not label its setup as controller-only')
    if (probe.name == 'arena-seed.lua') != args.relocation_setup:
        parser.error('arena-seed.lua requires --relocation-setup, which is exclusive to that probe')
    if args.boss_last_hit_setup and (probe.name != 'boss-combat.lua' or not args.combat_supply_setup):
        parser.error('--boss-last-hit-setup requires boss-combat.lua and --combat-supply-setup')
    if (probe.name == 'boss-combat.lua') != args.combat_supply_setup:
        parser.error('boss-combat.lua requires --combat-supply-setup, exclusive to that probe')
    if (probe.name == 'boss-prep.lua') != args.ally_heal_setup:
        parser.error('boss-prep.lua requires --ally-heal-setup, exclusive to that probe')
    if args.intro_setup and probe.name != 'army.lua':
        parser.error('--intro-setup requires the bounded army probe')
    if args.trace_position and probe.name != 'arena-seed.lua':
        parser.error('--trace-position requires the bounded arena setup probe')
    if args.trace_rng and probe.name not in ('rng.lua', 'army.lua'):
        parser.error('--trace-rng requires rng.lua or the bounded army probe')
    if args.wake_setup and (probe.name != 'pumpkin.lua' or args.level_setup):
        parser.error('--wake-setup is only for the Pumpkin continuation, not a level dispatch')
    for path in (emulator, bios, cue, probe, exe):
        if not path.is_file():
            parser.error(f'Missing required file: {path}')
    exe_sha1 = hashlib.sha1(exe.read_bytes()).hexdigest()
    if exe_sha1 != EXE_SHA1:
        parser.error('Unsupported executable revision; expected the identified USA image')
    if args.scenario not in ('boot', 'ui') and not args.seed:
        parser.error('Gameplay experiments require an explicit, known gameplay seed')
    if args.scenario == 'ui' and probe == DEFAULT_PROBE:
        parser.error('UI experiments require an explicit bounded UI probe')
    run = (args.output or Path(tempfile.mkdtemp(prefix='medievil-memory-'))).resolve()
    run.mkdir(parents=True, exist_ok=True)
    # Refuse reuse rather than overwriting previous evidence or memory cards.
    marker = run / 'run.json'
    if any(run.iterdir()):
        parser.error('Output directory must be empty; existing files will not be overwritten')
    source_emulator = emulator
    emulator = private_emulator(source_emulator, run)
    # Freeze the script before launch, so later edits cannot change this run's input.
    frozen_probe = run / 'probe.lua'
    frozen_probe.write_bytes(probe.read_bytes())
    home = run / 'home'
    (home / '.config').mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / '.config'),
               XDG_DATA_HOME=str(home / '.local/share'), XDG_CACHE_HOME=str(home / '.cache'),
               MEMORY_SCENARIO=args.scenario, MEMORY_SEED='',
               BOSS_LAST_HIT_SETUP='1' if args.boss_last_hit_setup else '0',
               PUMPKIN_WAKE_SETUP='1' if args.wake_setup else '0',
               ARMY_INTRO_SETUP='1' if args.intro_setup else '0',
               ARMY_TRACE_RNG='1' if args.trace_rng else '0')
    seed_hash = None
    if args.seed:
        seed = args.seed.expanduser().resolve()
        data = gzip.decompress(seed.read_bytes()) if seed.suffix == '.gz' else seed.read_bytes()
        seed_hash = hashlib.sha256(data).hexdigest()
        (run / 'start.state').write_bytes(data)
        env['MEMORY_SEED'] = str(run / 'start.state')
    command = [str(emulator), '-cli', '-safe', '-noupdate', '-no-webserver', '-no-gdb',
               '-debugger' if (args.trace_rng or args.trace_position) else '-no-debugger', '-interpreter', '-softgpu', '-bios', str(bios), '-iso', str(cue),
               '-memcard1', str(run / 'card1.mcd'), '-memcard2', str(run / 'card2.mcd'),
               '-dofile', str(frozen_probe), '-run']
    record = {'scenario': args.scenario, 'command': command, 'ram_size': 0x200000,
              'seed_sha256': seed_hash, 'emulator_sha256': sha256(emulator),
              'source_emulator': str(source_emulator),
              'isolation': {'private_app': True, 'expected_process_name': 'ReduxAudit',
                            'webserver': False, 'gdb_server': False, 'debugger': args.trace_rng or args.trace_position},
              'probe_sha256': sha256(frozen_probe), 'probe_name': probe.name, 'run_directory': str(run),
              'exe_sha1': exe_sha1,
              'started_unix': time.time(),
              'setup': 'isolated save-state restoration' if args.seed else 'cold disc boot',
              'method': 'Controller inputs after setup; no direct game-RAM pokes by the probe'}
    if args.trace_position:
        record['instrumentation'] = {'position_write_callbacks': True, 'non_pausing': True}
    if args.trace_rng:
        record['instrumentation'] = {'rng_store_exec_callback': '0x800A43D8',
                                     'non_pausing': True, 'guest_memory_edits': False}
    if args.level_setup:
        record['setup_writes'] = {'0x800EEE30': int(env.get('BOSS_LEVEL', '10')),
                                  '0x800ED6CC': 1, '0x800EEE6C': 4}
        record['method'] = ('Explicit level-dispatch setup, then native execution/controller inputs; '
                            'no direct health, inventory, coordinates or boss-HUD pokes')
    if args.wake_setup:
        record['setup_writes'] = {'[0x800EE978]+0x10': 0}
        record['method'] = ('Forced wake prerequisite, then native execution/controller inputs; '
                            'no direct health, inventory, coordinates or boss-HUD pokes. '
                            'Injected gate/derived phase changes are not natural-progression verification.')
    if args.relocation_setup:
        record['setup_writes'] = {'player_actor_xyz': [0, -100, 2000],
                                  'player_physics_current_and_previous_16_16': [0, -6553600, 131072000],
                                  'motion_reset_offsets': ['0x48', '0x4C', '0x50', '0xBC', '0xC0', '0xC4'],
                                  'physics_spawn_short_xyz': [0, -100, 2000],
                                  'physics_b8': 0, 'player_state_68c': -100,
                                  'player_actor_flags_50_clear_mask': '0x18000000'}
        record['method'] = ('Explicit laboratory train detachment/relocation, not an in-game skip; '
                            'no HP, RNG, phase or spawn-flag writes')
    if args.combat_supply_setup:
        record['combat_goal'] = env.get('BOSS_GOAL', 'both')
        record['requested_weapon_via_controller'] = env.get('BOSS_WEAPON', '3')
        record['setup_writes'] = {'player_hp': 'Restore living HP to 300',
                                  'dagger_ammo': 'Restore owned ammo to 100'}
        record['method'] = ('Explicit player-health/ammo assistance; controller attacks and movement; '
                            'no boss HP/action, phase, RNG, actor position or inventory ownership writes')
    if args.boss_last_hit_setup:
        record['setup_writes']['boss_hp'] = 'Reduce positive HP above 6 to 6 once per guarded phase/actor/constructor; never write zero'
        record['method'] = ('Explicit boss last-hit HP setup and player-health/ammo assistance; '
                            'require native controller attack to cause death; no boss action, phase, RNG or actor-position writes')
    if args.ally_heal_setup:
        record['setup_writes'] = {'friendly_skeleton_actor_hp': 'Restore positive HP to 500 through registered friendly slots during phase 2 only'}
        record['method'] = ('Explicit assisted pre-boss setup, not a natural army victory; '
                            'no boss HP/action, phase, RNG, player HP or inventory writes')
    if args.intro_setup:
        record['setup_writes'] = {'0x800EE93F': 1}
        record['method'] = ('Injected missing introduction prerequisite only; then controller inputs/native execution. '
                            'Not a natural encounter entry or route-valid glitch reproduction; '
                            'no RNG/HP/soldier count or actor-slot writes.')
    marker.write_text(json.dumps(record, indent=2) + '\n')
    print(f'RUN {run}', flush=True)
    start = time.monotonic()
    with (run / 'emulator.log').open('w') as log:
        child = subprocess.Popen(command, cwd=run, env=env, stdout=log, stderr=subprocess.STDOUT)
        record['pid'] = child.pid
        try:
            observed = subprocess.run(['ps', '-p', str(child.pid), '-o', 'comm='],
                                      capture_output=True, text=True, timeout=3, check=True)
            record['isolation']['observed_process_path'] = observed.stdout.strip()
            if Path(observed.stdout.strip()).name != 'ReduxAudit':
                raise RuntimeError('Unexpected child name; refusing possible discovery interference')
            record['isolation']['excluded_from_canonical_discovery'] = True
            marker.write_text(json.dumps(record, indent=2) + '\n')
            record['exit_code'] = child.wait(timeout=args.timeout_seconds)
        except BaseException:
            # Only our own child is terminated on timeout/interruption.
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
            record['exit_code'] = child.returncode
            record['interrupted'] = True
            raise
        finally:
            record['duration_seconds'] = time.monotonic() - start
            marker.write_text(json.dumps(record, indent=2) + '\n')
    if record['exit_code']:
        raise SystemExit(f'Probe failed: {record["exit_code"]}; inspect {run}/emulator.log')
    rows = [json.loads(line) for line in (run / 'samples.jsonl').read_text().splitlines()]
    live = [row for row in rows if row.get('mode') == 3 and 'x' in row]
    record['semantic_checks'] = {
        'normal_completion': bool(rows) and rows[-1]['phase'] == 'finished',
        'samples': len(rows), 'live_samples': len(live),
        'unique_positions': len({(r['x'], r['y'], r['z']) for r in live}),
        'unique_game_frames': len({r['gameFrame'] for r in live}),
        'unique_vblank_counts': len({r['vblank'] for r in rows if 'vblank' in r}),
        'modes': sorted({r['mode'] for r in rows}),
    }
    check = record['semantic_checks']
    passed = check['normal_completion'] and check['unique_game_frames'] >= 100
    if args.scenario == 'ui':
        passed = check['normal_completion'] and check['unique_vblank_counts'] >= 100
    elif args.scenario == 'movement':
        passed = passed and check['unique_positions'] >= 10
    elif args.scenario == 'boot':
        passed = passed and 2 in check['modes'] and 3 in check['modes']
    record['semantic_pass'] = passed
    marker.write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2), flush=True)
    if not passed:
        raise SystemExit('Process exited normally but gameplay checks failed; do not claim verification')


if __name__ == '__main__':
    main()
