# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D-R1 完整性快照工具（只读扫描；PROPOSED 项目辅助工具，非 DeepBas 组件）。

与 S0D 版 tools/integrity_snapshot.py 的区别（R1 强化，见 incident_audit.md INC-2 防止措施）：
  * 自写遍历函数 walk_pruned：目录名（不区分大小写）含 "sealed" 或 "quarantin" 即剪枝——
    不调用 scandir 进入、不列举其子项，只对目录项自身取 stat（修改时间）；
  * vhs_multistation 先做一级非递归列举，再只对白名单子目录（显式列名）递归；
    非白名单的一级目录只记录名称，不进入；
  * 不跟随符号链接/目录联接；
  * 监控范围（全部位于项目根之下）：项目根一级条目、research_next 一级条目、
    vhs_multistation 一级条目、白名单子目录（含 SHA-256）、本轮工作目录 D（含 SHA-256）、
    .venv（仅元数据：大小与 mtime，用于发现是否生成 __pycache__/pyc 等）；
  * 不访问 C:\\ 或项目根以外的任何路径；输出文件只允许写入 D 内。
用法：
  python -B tools/integrity_snapshot_r1.py snapshot <输出json（D 内）> --label pre|post
  python -B tools/integrity_snapshot_r1.py compare <pre.json> <post.json> [<输出json（D 内）>]
"""
import hashlib
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True

FORBIDDEN_DIR_RE = re.compile(r"(?i)sealed|quarantin")      # 剪枝判据：目录名含 sealed / quarantin(e)
VM_WHITELIST = ("b1a", "b1b_s0_deepbas_mvp", "evidence", "reports", "scripts")
NEW_DIR_NAME = "b1b_s0d_io_demo"
CHUNK = 1024 * 1024
D_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VM_DIR = os.path.dirname(D_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(VM_DIR))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _is_link(entry):
    return entry.is_symlink() or getattr(entry, "is_junction", lambda: False)()


def level1(path, scandir=os.scandir):
    """一级非递归列举：名称、类型、大小（仅文件）、mtime_ns。含 sealed/quarantin 的目录项只记名称与 mtime。"""
    out = {}
    with scandir(path) as it:
        for e in sorted(it, key=lambda x: x.name):
            st = e.stat(follow_symlinks=False)
            if _is_link(e):
                kind = "link"
            elif e.is_dir(follow_symlinks=False):
                kind = "dir"
            else:
                kind = "file"
            rec = {"type": kind, "mtime_ns": st.st_mtime_ns}
            if kind == "file":
                rec["size"] = st.st_size
            if kind == "dir" and FORBIDDEN_DIR_RE.search(e.name):
                rec["note"] = "sealed/quarantine-like name: metadata of the entry itself only, never entered"
            out[e.name] = rec
    return out


def walk_pruned(root, with_hash=True, scandir=os.scandir, trace=None):
    """自写遍历（显式栈）。目录名命中 FORBIDDEN_DIR_RE 即剪枝（不 scandir 进入）。
    trace：可选列表，记录每次 scandir 的目录（测试用，证明从未进入被剪枝目录）。"""
    root = os.path.abspath(root)
    if FORBIDDEN_DIR_RE.search(os.path.basename(root)):
        raise ValueError("refusing to walk a sealed/quarantine-like root")
    files, pruned, links = {}, [], []
    stack = [root]
    while stack:
        d = stack.pop()
        if trace is not None:
            trace.append(d)
        with scandir(d) as it:
            entries = sorted(it, key=lambda x: x.name)
        for e in entries:
            rel = os.path.relpath(e.path, root).replace("\\", "/")
            if _is_link(e):
                links.append(rel)
                continue
            if e.is_dir(follow_symlinks=False):
                if FORBIDDEN_DIR_RE.search(e.name):
                    st = e.stat(follow_symlinks=False)      # 只取目录项自身元数据
                    pruned.append({"path": rel, "mtime_ns": st.st_mtime_ns})
                    continue
                stack.append(e.path)
            elif e.is_file(follow_symlinks=False):
                st = e.stat(follow_symlinks=False)
                files[rel] = [st.st_size, st.st_mtime_ns, _sha256(e.path) if with_hash else None]
    lines = ["%s|%d|%d|%s" % (k, v[0], v[1], v[2]) for k, v in sorted(files.items())]
    return {"files": dict(sorted(files.items())), "pruned_dirs_metadata_only": sorted(pruned, key=lambda x: x["path"]),
            "links_not_followed": sorted(links),
            "summary": {"file_count": len(files), "total_bytes": sum(v[0] for v in files.values()),
                        "list_sha256": hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()}}


def snapshot(project_root=PROJECT_ROOT, d_dir=D_DIR, include_venv=True):
    vm = os.path.join(project_root, "research_next", "vhs_multistation")
    vm_l1 = level1(vm)
    scopes = {
        "project_root_level1": level1(project_root),
        "research_next_level1": level1(os.path.join(project_root, "research_next")),
        "vhs_multistation_level1": vm_l1,
        "vm_whitelist": {},
        "vm_level1_not_traversed": sorted(n for n, r in vm_l1.items() if r["type"] == "dir"
                                          and n not in VM_WHITELIST and n != NEW_DIR_NAME),
    }
    for name in VM_WHITELIST:
        if vm_l1.get(name, {}).get("type") == "dir":
            scopes["vm_whitelist"][name] = walk_pruned(os.path.join(vm, name), True)
    scopes["d_dir"] = walk_pruned(d_dir, True)
    venv = os.path.join(project_root, ".venv")
    if include_venv and os.path.isdir(venv):
        scopes["venv_metadata_only"] = walk_pruned(venv, False)
    return {"tool": "integrity_snapshot_r1", "project_root": os.path.abspath(project_root),
            "d_dir": os.path.abspath(d_dir), "forbidden_dir_regex": FORBIDDEN_DIR_RE.pattern,
            "vm_whitelist": list(VM_WHITELIST), "scopes": scopes}


def _cmp_files(a, b):
    fa, fb = a["files"], b["files"]
    return {"added": sorted(set(fb) - set(fa)), "removed": sorted(set(fa) - set(fb)),
            "changed": sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k]),
            "pruned_dirs_equal": a["pruned_dirs_metadata_only"] == b["pruned_dirs_metadata_only"],
            "links_equal": a["links_not_followed"] == b["links_not_followed"]}


def _cmp_level1(a, b):
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)),
            "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k])}


def compare(pre, post):
    sa, sb = pre["scopes"], post["scopes"]
    out = {}
    for k in ("project_root_level1", "research_next_level1", "vhs_multistation_level1"):
        out[k] = _cmp_level1(sa[k], sb[k])
    out["vm_whitelist"] = {n: _cmp_files(sa["vm_whitelist"][n], sb["vm_whitelist"][n])
                           for n in sorted(set(sa["vm_whitelist"]) | set(sb["vm_whitelist"]))
                           if n in sa["vm_whitelist"] and n in sb["vm_whitelist"]}
    out["vm_whitelist_scope_equal"] = sorted(sa["vm_whitelist"]) == sorted(sb["vm_whitelist"])
    out["vm_level1_not_traversed_equal"] = sa["vm_level1_not_traversed"] == sb["vm_level1_not_traversed"]
    out["d_dir"] = _cmp_files(sa["d_dir"], sb["d_dir"])
    if "venv_metadata_only" in sa and "venv_metadata_only" in sb:
        out["venv_metadata_only"] = _cmp_files(sa["venv_metadata_only"], sb["venv_metadata_only"])
    old_ok = all(not (v["added"] or v["removed"] or v["changed"]) and v["pruned_dirs_equal"]
                 for v in out["vm_whitelist"].values()) and out["vm_whitelist_scope_equal"]
    out["old_dirs_identical"] = old_ok
    return out


def _safe_out(path):
    full = os.path.abspath(path)
    if not path or not full.lower().startswith(os.path.abspath(D_DIR).lower() + os.sep):
        raise SystemExit("refusing to write outside D: %r" % path)
    if FORBIDDEN_DIR_RE.search(full):
        raise SystemExit("refusing sealed/quarantine-like output path")
    return full


def main(argv):
    if len(argv) >= 3 and argv[1] == "snapshot":
        out = _safe_out(argv[2])
        label = argv[4] if len(argv) > 4 and argv[3] == "--label" else "snapshot"
        t0 = time.time()
        snap = snapshot()
        snap["label"] = label
        snap["generated_at_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        snap["elapsed_s"] = round(time.time() - t0, 1)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=0)
        sc = snap["scopes"]
        print(json.dumps({"label": label, "elapsed_s": snap["elapsed_s"],
                          "vm_whitelist": {n: v["summary"] for n, v in sc["vm_whitelist"].items()},
                          "pruned": {n: v["pruned_dirs_metadata_only"] for n, v in sc["vm_whitelist"].items()
                                     if v["pruned_dirs_metadata_only"]},
                          "vm_level1_not_traversed": sc["vm_level1_not_traversed"],
                          "d_dir": sc["d_dir"]["summary"],
                          "venv": sc.get("venv_metadata_only", {}).get("summary"),
                          "project_root_level1_count": len(sc["project_root_level1"])}, ensure_ascii=False))
        return 0
    if len(argv) >= 4 and argv[1] == "compare":
        with open(argv[2], encoding="utf-8") as fh:
            pre = json.load(fh)
        with open(argv[3], encoding="utf-8") as fh:
            post = json.load(fh)
        res = compare(pre, post)
        if len(argv) > 4:
            with open(_safe_out(argv[4]), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(res, fh, ensure_ascii=False, indent=1)
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
