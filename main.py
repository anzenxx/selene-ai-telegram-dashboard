import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.workspace import SeleneApp

if __name__ == "__main__":
    app = SeleneApp()
    app.mainloop()
