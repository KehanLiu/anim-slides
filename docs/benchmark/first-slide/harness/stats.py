import json, sys, collections
for path in sys.argv[1:]:
    init, result, tools, sub_tools, skills_used, files_written = None, None, collections.Counter(), collections.Counter(), [], []
    models = collections.Counter()
    for line in open(path):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("type") == "system" and e.get("subtype") == "init" and init is None:
            init = e
        if e.get("type") == "result":
            result = e
        if e.get("type") == "assistant":
            m = e["message"]
            models[m.get("model")] += 1
            for c in m.get("content", []):
                if c.get("type") == "tool_use":
                    (sub_tools if e.get("parent_tool_use_id") else tools)[c["name"]] += 1
                    if c["name"] == "Skill":
                        skills_used.append(c["input"])
                    if c["name"] in ("Write", "Edit"):
                        files_written.append((c["name"], c["input"].get("file_path")))
    print("==", path)
    print("init: version", init.get("claude_code_version"), "model", init.get("model"), "cwd", init.get("cwd"))
    print("init skills:", init.get("skills"))
    print("init mcp:", init.get("mcp_servers"), "plugins:", [p["name"] for p in init.get("plugins", [])])
    print("init tools:", init.get("tools"))
    print("assistant models:", dict(models))
    print("tool calls main:", sum(tools.values()), dict(tools))
    print("tool calls subagents:", sum(sub_tools.values()), dict(sub_tools))
    print("skills invoked:", skills_used)
    print("writes/edits:", files_written)
    if result:
        print("result: subtype", result.get("subtype"), "is_error", result.get("is_error"), "turns", result.get("num_turns"),
              "duration_ms", result.get("duration_ms"), "cost", result.get("total_cost_usd"))
        print("usage:", json.dumps(result.get("usage")))
        print("modelUsage:", json.dumps(result.get("modelUsage")))
        print("final text:", (result.get("result") or "")[:3000])
