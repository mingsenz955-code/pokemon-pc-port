"""Native viewport intersection and failed-search cost; no invented search radius."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'src'))
from original_data import OriginalData
from game_state import GameState
from treasure import TreasureHunt

DATA = OriginalData(ROOT/'original-1.20.4')


class TreasureSearch(unittest.TestCase):
    def setUp(self):
        self.state = GameState(DATA.tables, 33)
        self.state.grant('700002', 50)
        self.hunt = TreasureHunt(self.state)
        self.entry = self.hunt.buy('1')
        sprite = DATA.tables['TChest'][self.entry['chest_id']]['spriteId']
        self.box = json.loads(DATA.sprite_tiles()[sprite]['box'])

    def search(self, viewport, map_id=None):
        return self.hunt.use_magnifier(map_id=map_id or self.entry['map_id'], viewport=viewport, box=self.box)

    def test_wrong_map_charges_one_and_keeps_chest_hidden(self):
        x, y = self.entry['x'], self.entry['y']
        self.assertFalse(self.search((x-100, y-100, x+100, y+100), '7401'))
        self.assertEqual(2, self.state.count('220007'))
        self.assertFalse(self.entry['revealed'])

    def test_offscreen_chest_cannot_be_revealed(self):
        x, y = self.entry['x'], self.entry['y']
        self.assertFalse(self.search((x+100, y+100, x+500, y+500)))
        self.assertEqual(2, self.state.count('220007'))
        self.assertFalse(self.entry['revealed'])

    def test_visible_edge_of_bounding_box_counts_even_when_center_is_offscreen(self):
        x, y = self.entry['x'], self.entry['y']
        self.assertTrue(self.search((x+31, y-100, x+500, y+100)))
        self.assertEqual(2, self.state.count('220007'))
        self.assertTrue(self.entry['revealed'])

    def test_insufficient_magnifier_preserves_state_and_rng(self):
        self.state.inventory['220007'] = 0
        before = self.state.payload()
        x, y = self.entry['x'], self.entry['y']
        with self.assertRaises(ValueError):
            self.search((x-100, y-100, x+100, y+100))
        self.assertEqual(before, self.state.payload())

    def test_invalid_viewport_does_not_consume(self):
        before = self.state.payload()
        with self.assertRaises(ValueError):
            self.search((100, 100, 0, 0))
        self.assertEqual(before, self.state.payload())


if __name__ == '__main__':
    unittest.main(verbosity=2)
