import json, os, signal, subprocess, sys, time, datetime
arm, d, prompt_file = sys.argv[1:4]
CL = os.environ.get("CLAUDE_BIN", "claude")  # path to the claude CLI binary
prompt = open(prompt_file).read().strip()
cmd = [CL, "-p", prompt, "--model", "opus", "--output-format", "stream-json", "--verbose",
       "--setting-sources", "project,local", "--strict-mcp-config",
       "--permission-mode", "bypassPermissions"]
TIMEOUT = 60 * 60
start = time.time(); t0 = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
timed_out = False
with open(os.path.join(d, "..", f"{arm}.transcript.jsonl"), "w") as out, open(os.path.join(d, "..", f"{arm}.stderr.txt"), "w") as err:
    p = subprocess.Popen(cmd, cwd=d, stdin=subprocess.DEVNULL, stdout=out, stderr=err, start_new_session=True)
    try:
        code = p.wait(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        timed_out = True; os.killpg(p.pid, signal.SIGTERM); time.sleep(5)
        try: os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError: pass
        code = -1
meta = dict(arm=arm, cmd=cmd, cwd=d, start=t0, end=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            seconds=round(time.time() - start), exit_code=code, timed_out=timed_out, timeout_s=TIMEOUT,
            has_result=os.path.exists(os.path.join(d, "result.html")))
json.dump(meta, open(os.path.join(d, "..", f"{arm}.meta.json"), "w"), indent=1)
print(json.dumps(meta))
