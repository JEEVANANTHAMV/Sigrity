import subprocess

out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Capture.exe"], capture_output=True, text=True)
print(out.stdout)
n = subprocess.run(["taskkill", "/F", "/IM", "Capture.exe"], capture_output=True, text=True)
print("kill:", n.stdout.strip(), n.stderr.strip())
# also any orphaned specctra/pspice from tests
for img in ("syscap.exe",):
    subprocess.run(["taskkill", "/F", "/IM", img], capture_output=True, text=True)
