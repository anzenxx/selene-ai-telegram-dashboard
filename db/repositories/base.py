import os
import sqlite3


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "selene.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
