import subprocess, shutil, re
bob = shutil.which("bob.cmd")
r = subprocess.run(
    [bob, "echo test", "--chat-mode", "code", "--output-format", "json", "--yolo"],
    capture_output=True, text=True, encoding="utf-8", input="/exit\n", timeout=60
)
out = r.stdout + r.stderr
print(f"STDOUT len: {len(r.stdout)}")
print(f"STDERR len: {len(r.stderr)}")
m = re.search(r'"total":\s*(\d+)', out)
print(f"Total: {m.group(1) if m else 'NONE'}")
m2 = re.search(r'"sessionCost":\s*([\d.]+)', out)
print(f"Cost: {m2.group(1) if m2 else 'NONE'}")
print(f"First 500 chars: {repr(out[:500])}")
print("---STDERR---")
print(r.stderr[:500])
