import os

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import sqlite3

import pytest

import game


@pytest.fixture()
def pg():
    g = game.PetunaGame()
    yield g
    try:
        g.db_conn.close()
    except Exception:
        pass
    g.game.quit()


@pytest.fixture()
def memdb(pg):
    """Point the game at a fresh in-memory scoreboard."""
    conn = sqlite3.connect(':memory:')
    conn.execute('CREATE TABLE scores (name TEXT NOT NULL, score INTEGER)')
    conn.commit()
    pg.db_conn = conn
    yield pg
    conn.close()
