"""Run the staged X story against its own save directory."""
import argparse
import os
import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent/'src'))
from original_data import OriginalData
from pc_game import NativeGame


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('staging', type=Path)
    args = parser.parse_args()
    directory = args.staging.resolve()
    if not (directory/'migration-audit.json').is_file():
        parser.error('Expected data produced by stage_x_story.py')
    os.environ['POCKET_NATIVE_SAVE_DIR'] = str(directory/'preview-saves')
    root = tk.Tk()
    NativeGame(root, OriginalData(directory), show_opening=True)
    root.title('口袋妖怪 X 剧情迁移测试 · 独立存档')
    root.mainloop()
