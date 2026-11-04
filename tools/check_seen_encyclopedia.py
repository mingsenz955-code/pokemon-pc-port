"""Original monotonic unknown/seen/owned status and old-save migration."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState

DATA = OriginalData(ROOT/'original-1.20.4')


class SeenEncyclopedia(unittest.TestCase):
    def test_sighting_does_not_grant_ownership_or_mount(self):
        state = GameState(DATA.tables, 14)
        state.initialize(1)
        inventory, owned, rides = dict(state.inventory), list(state.encyclopedia), list(state.rides)
        species = DATA.tables['Ride']['500003']['petId']
        state.record_seen_pet(species)
        state.record_seen_pet(species)
        self.assertEqual(1, state.seen_species.count(species))
        self.assertEqual(owned, state.encyclopedia)
        self.assertEqual(rides, state.rides)
        self.assertEqual(inventory, state.inventory)

    def test_owned_status_cannot_be_downgraded_by_sighting(self):
        state = GameState(DATA.tables, 14)
        state.initialize(1)
        state.record_seen_pet('100001')
        state.record_pet('100001')
        state.record_seen_pet('100001')
        self.assertIn('100001', state.encyclopedia)
        self.assertEqual(1, state.seen_species.count('100001'))
        state.initialize(1)
        self.assertNotIn('100001', state.encyclopedia)
        self.assertNotIn('100001', state.seen_species)

    def test_seen_save_roundtrip_and_old_save_recovers_only_owned(self):
        state = GameState(DATA.tables, 14)
        state.initialize(1)
        state.record_pet('100001')
        state.record_seen_pet('100002')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'slot.json'
            state.save(path)
            restored = GameState.load(DATA.tables, path)
            self.assertEqual(state.seen_species, restored.seen_species)
            self.assertEqual(state.encyclopedia, restored.encyclopedia)
            payload = json.loads(path.read_text(encoding='utf-8'))
            payload['state'].pop('seen_species')
            path.write_text(json.dumps(payload), encoding='utf-8')
            restored = GameState.load(DATA.tables, path)
            self.assertEqual(['100001'], restored.seen_species)

    def test_invalid_species_does_not_modify_status(self):
        state = GameState(DATA.tables, 14)
        before = state.payload()
        with self.assertRaises(KeyError):
            state.record_seen_pet('not-a-pet')
        self.assertEqual(before, state.payload())


if __name__ == '__main__':
    unittest.main(verbosity=2)
