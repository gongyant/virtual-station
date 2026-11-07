# -*- coding: utf-8 -*-
"""VHS-NEXT-B1B-S0D 完整性快照工具（只读；SYNTHETIC 项目辅助工具，非 DeepBas 组件）。

用途：对 research_next\\vhs_multistation 下"本轮新目录以外"的文件做
  相对路径 | 字节数 | 修改时间(ns) | SHA-256 清单，用于开发前后比较。
约束：
  * 只读：仅 open(..., "rb") 计算哈希，不写入被扫描目录；输出文件只写到本轮新目录内。
  * 封存/隔离目录按"目录名"剪枝：不进入、不列举、不读取其中任何内容，
    只记录目录自身的修改时间（os.stat 目录本身）。
  * 不跟随符号链接/目录联接（junction），遇到只记录不进入。
用法：python -B tools/integrity_snapshot.py <vhs_multistation 根> <输出json> [--label pre|post]
"""
import hashlib
import json
import os
import sys
import time

sys.dont_write_bytecode = True

# 剪枝目录名（只用于"跳过不进入"，本工具不会打开这些目录内的任何条目）
PRUNE_DIR_NAMES = frozenset({"sealed_runoff", "quarantine"})
NEW_DIR_NAME = "b1b_s0d_io_demo"
CHUNK = 1024 * 1024


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            b = fh.read(CHUNK)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def snapshot(root, with_hash=True, only_subdir=None):
    root = os.path.abspath(root)
    files = {}
    pruned = []
    links = []
    start = os.path.join(root, only_subdir) if only_subdir else root
    stack = [start]
    while stack:
        d = stack.pop()
        with os.scandir(d) as it:
            entries = sorted(it, key=lambda e: e.name)
        for e in entries:
            rel = os.path.relpath(e.path, root).replace("\\", "/")
            is_junction = getattr(e, "is_junction", lambda: False)()
            if e.is_symlink() or is_junction:
                links.append(rel)
                continue
            if e.is_dir(follow_symlinks=False):
                if d == root and e.name == NEW_DIR_NAME:
                    continue
                if e.name in PRUNE_DIR_NAMES:
                    st = os.stat(e.path)  # 只取目录自身元数据
                    pruned.append({"path": rel, "mtime_ns": st.st_mtime_ns})
                    continue
                stack.append(e.path)
            elif e.is_file(follow_symlinks=False):
                st = e.stat(follow_symlinks=False)
                files[rel] = [st.st_size, st.st_mtime_ns, _sha256(e.path) if with_hash else None]
    lines = ["%s|%d|%d|%s" % (k, v[0], v[1], v[2]) for k, v in sorted(files.items())]
    return {
        "root": root,
        "excluded_new_dir": NEW_DIR_NAME,
        "pruned_dirs_metadata_only": sorted(pruned, key=lambda x: x["path"]),
        "links_not_followed": sorted(links),
        "files": dict(sorted(files.items())),
        "summary": {
            "file_count": len(files),
            "total_bytes": sum(v[0] for v in files.values()),
            "list_sha256": hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest(),
        },
    }


def compare(a, b):
    fa, fb = a["files"], b["files"]
    added = sorted(set(fb) - set(fa))
    removed = sorted(set(fa) - set(fb))
    changed = sorted(k for k in set(fa) & set(fb) if fa[k] != fb[k])
    pa = {p["path"]: p["mtime_ns"] for p in a["pruned_dirs_metadata_only"]}
    pb = {p["path"]: p["mtime_ns"] for p in b["pruned_dirs_metadata_only"]}
    return {"added": added, "removed": removed, "changed": changed,
            "pruned_dirs_equal": pa == pb, "identical": not (added or removed or changed) and pa == pb}


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    root, out = argv[1], argv[2]
    label = argv[4] if len(argv) > 4 and argv[3] == "--label" else "snapshot"
    t0 = time.time()
    snap = snapshot(root)
    snap["label"] = label
    snap["generated_at_local"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    snap["elapsed_s"] = round(time.time() - t0, 1)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(snap, fh, ensure_ascii=False, indent=0)
    print(json.dumps({"label": label, "summary": snap["summary"], "elapsed_s": snap["elapsed_s"],
                      "pruned_dirs_metadata_only": snap["pruned_dirs_metadata_only"],
                      "links_not_followed": snap["links_not_followed"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
