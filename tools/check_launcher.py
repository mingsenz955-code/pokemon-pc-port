"""Compile/run only the launcher's resolver mode; never start a game or edit saves."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from install_launcher import install_launcher


class LauncherChecks(unittest.TestCase):
    def test_stable_entry_switches_only_after_complete_release(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            release = dist/'game-0.2.41'
            release.mkdir()
            (release/'game-0.2.41.exe').write_bytes(b'not executed in resolver mode')
            (release/'data').mkdir()
            (release/'data/tables.json').write_text('{}')
            launcher = install_launcher(dist, release)
            pointer = launcher.parent/'current-release.txt'
            previous = pointer.read_text('utf-8')
            self.assertFalse(Path(previous).is_absolute())
            output = dist/'resolved.txt'
            subprocess.run([str(launcher), '--resolve', str(output)], check=True)
            self.assertEqual(release/'game-0.2.41.exe', Path(output.read_text('utf-8')))
            next_release = dist/'game-0.2.42'
            next_release.mkdir()
            with self.assertRaises(ValueError):
                install_launcher(dist, next_release)
            self.assertEqual(previous, pointer.read_text('utf-8'))
            (next_release/'game-0.2.42.exe').write_bytes(b'not executed')
            (next_release/'data').mkdir()
            (next_release/'data/tables.json').write_text('{}')
            launcher_bytes = launcher.read_bytes()
            self.assertEqual(launcher, install_launcher(dist, next_release))
            self.assertEqual(launcher_bytes, launcher.read_bytes())
            subprocess.run([str(launcher), '--resolve', str(output)], check=True)
            self.assertEqual(next_release/'game-0.2.42.exe', Path(output.read_text('utf-8')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
