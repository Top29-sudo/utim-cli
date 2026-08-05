import os
import shutil
import utim_cli
print("UTIM_CLI PATH:", utim_cli.__file__)

from typer.testing import CliRunner
from utim_cli.utim import app

runner = CliRunner()
tmp_path = "C:\\Users\\user\\Desktop\\New folder\\New folder\\scratch\\temp_test_cli"
if os.path.exists(tmp_path):
    shutil.rmtree(tmp_path)
os.makedirs(tmp_path)

old_cwd = os.getcwd()
os.chdir(tmp_path)
try:
    res = runner.invoke(app, ["init"])
    print("INIT EXIT CODE:", res.exit_code)
    print("INIT OUTPUT:\n", res.stdout)
    
    res = runner.invoke(app, ["reset"], input="y\n")
    print("RESET EXIT CODE:", res.exit_code)
    print("RESET OUTPUT:\n", res.stdout)
finally:
    os.chdir(old_cwd)
