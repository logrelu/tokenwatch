"""Every test runs with tokenwatch's own files pointed at a throwaway folder, so a budget or theme you saved
on this machine (~/.config/tokenwatch) can never change a result, and no test can overwrite it."""
import atexit, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from twlib import config

_SANDBOX = tempfile.mkdtemp(prefix="tokenwatch-tests-")
atexit.register(shutil.rmtree, _SANDBOX, True)
config.PREFS = os.path.join(_SANDBOX, "prefs", "config.json")
os.environ.pop("TOKENWATCH_BUDGET", None)
