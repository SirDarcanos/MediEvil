"""Captured positive/negative reference cases; not Windows ASL integration tests."""
import json
from pathlib import Path
import unittest
from tools.asl_signals import EXE_SHA1, boss_death_candidate

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence'


class BossSignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.final = json.loads((EVIDENCE / 'final-boss-events.json').read_text())
        cls.zarok = json.loads((EVIDENCE / 'zarok-death-events.json').read_text())

    def check(self, row, encounter='zarok', sha=EXE_SHA1):
        return boss_death_candidate(row, encounter, exe_sha1=sha)

    def test_observed_kardok_death(self):
        self.assertTrue(self.check(self.final['kardok_native_death'], 'kardok'))

    def test_observed_negative_zarok_hp_and_death(self):
        row = self.zarok['native_death']
        self.assertEqual(row['bossHP'], -8)
        self.assertEqual(row['barActive'], 1)
        self.assertTrue(self.check(row))

    def test_positive_hp_before_killing_blow_is_not_death(self):
        self.assertFalse(self.check(self.zarok['before_native_death']))
        self.assertFalse(self.check(self.final['kardok_before_death'], 'kardok'))

    def test_phase8_before_zarok_registration_is_not_death(self):
        self.assertFalse(self.check(self.final['first_phase8']))

    def test_initial_zarok_and_live_fight_are_not_death(self):
        self.assertFalse(self.check(self.final['zarok_registered']))
        self.assertFalse(self.check(self.final['zarok_alive_music21']))
        self.assertFalse(self.check(self.final['last_sample']))

    def test_zero_before_spawn_is_not_death(self):
        row = dict(self.zarok['native_death'], bossPointer=0, bossHP=0,
                   bossConstructor=0, bossDefinition=0, bossAction=0)
        self.assertFalse(self.check(row))

    def test_wrong_owner_context_and_version_are_rejected(self):
        row = self.zarok['native_death']
        for changes in [{'mode': 2}, {'overlay': 24}, {'level': 6},
                        {'phaseIndex': 6}, {'bossConstructor': 0x80011F24},
                        {'bossPointer': row['bossPointer'] + 1}]:
            with self.subTest(changes=changes):
                self.assertFalse(self.check(dict(row, **changes)))
        self.assertFalse(self.check(row, sha='unsupported'))

    def test_hud_zero_does_not_turn_live_hp_into_a_death(self):
        row = dict(self.zarok['before_native_death'], barCache=0, barInput=0)
        self.assertFalse(self.check(row))

    def test_unsigned_overkill_is_not_the_signed_hp_watch(self):
        row = dict(self.zarok['native_death'], bossHP=65528)
        self.assertFalse(self.check(row))


if __name__ == '__main__':
    unittest.main()
