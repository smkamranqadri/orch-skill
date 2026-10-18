#!/usr/bin/env python3
"""Exercise real curses in a scratch PTY and save the drawn cells for visual QA."""
import curses
import datetime as dt
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys

loader = importlib.machinery.SourceFileLoader("board", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
board = importlib.util.module_from_spec(spec)
loader.exec_module(board)
snapshot = board.snapshot
board.snapshot = lambda directory, **kw: snapshot(directory, dt.datetime(2026, 10, 18, 12, tzinfo=dt.timezone.utc), **kw)
frames = []


class Capture:
    def __init__(self, screen):
        self.screen = screen
        self.keys = iter([curses.KEY_RIGHT, 10, 27, curses.KEY_NPAGE, curses.KEY_PPAGE, ord("q")])

    def __getattr__(self, name):
        return getattr(self.screen, name)

    def getch(self):
        return next(self.keys)

    def refresh(self):
        self.screen.refresh()
        height, width = self.screen.getmaxyx()
        frames.append({"bold": sum(bool(self.screen.inch(y, x) & curses.A_BOLD)
                                    for y in range(height) for x in range(width - 1)),
                       "lines": [self.screen.instr(y, 0, width - 1).decode("utf-8").rstrip()
                                  for y in range(height)],
                       "colors": [[curses.pair_number(self.screen.inch(y, x)) for x in range(width - 1)]
                                  for y in range(height)]})


curses.wrapper(lambda screen: board.ui(Capture(screen), Path(sys.argv[2])))
Path(sys.argv[3]).write_text(json.dumps(frames))
