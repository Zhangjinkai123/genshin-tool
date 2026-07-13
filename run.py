import sys


sys.dont_write_bytecode = True

from app.server import run


if __name__ == "__main__":
    run()
