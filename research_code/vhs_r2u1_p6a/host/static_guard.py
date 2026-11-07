"""
static_guard.py  --  VHS v0.5.1 static-file boundary (fixes Codex P0-01)

The v0.5 check (normpath + startswith('..') + isabs) let the Windows
drive-relative form ``E:../server.py`` escape the static root. v0.5.1 serves a
static file only if ALL of the following hold:

1. the raw (still percent-encoded) request path matches a strict grammar:
   segments of [A-Za-z0-9_-], final segment ``name.ext``; this alone rejects
   ``..``, ``:`` (drive letters, ``C:foo``, NTFS ``::$DATA``), ``\\``,
   ``%`` (any URL encoding, incl. double encoding ``%252e``), NUL, spaces,
   trailing dots/spaces, empty segments (``//server`` UNC style) and
   absolute paths;
2. the stem is not a Windows reserved device name (CON, NUL, COM1 ...);
3. the extension is in a strict allow-list;
4. the candidate is resolved with ``os.path.realpath`` (follows symlinks and
   junctions) and must stay inside the resolved static root
   (``os.path.commonpath`` on normcase'd paths);
5. optionally (server default) the resolved file must be in a whitelist built
   once at start-up from the top level of the static root.

Every refusal returns a stable error code; nothing outside the root is
opened.
"""
import os
import re

ALLOWED_EXT = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}
_SEG = r"[A-Za-z0-9_-]{1,64}"
_GRAMMAR = re.compile(r"^(?:%s/){0,3}%s\.[a-z0-9]{1,5}$" % (_SEG, _SEG))
RESERVED = {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} | \
    {"COM%d" % i for i in range(10)} | {"LPT%d" % i for i in range(10)}


class StaticRefused(Exception):
    def __init__(self, status, code, detail=""):
        super().__init__("%s %s" % (code, detail))
        self.status, self.code, self.detail = status, code, detail


def _norm(p):
    return os.path.normcase(os.path.realpath(p))


def _inside(child, root):
    try:
        return os.path.commonpath([child, root]) == root
    except ValueError:              # different drives on Windows
        return False


class StaticGuard:
    def __init__(self, root, use_whitelist=True):
        if not root:
            raise ValueError("empty static root")
        self.root = os.path.abspath(root)
        self.root_real = _norm(self.root)
        self.use_whitelist = use_whitelist
        self.whitelist = self._build_whitelist() if use_whitelist else None

    def _build_whitelist(self):
        out = {}
        for name in sorted(os.listdir(self.root)):
            full = os.path.join(self.root, name)
            if not os.path.isfile(full) or os.path.islink(full):
                continue
            ext = os.path.splitext(name)[1]
            if ext not in ALLOWED_EXT or not _GRAMMAR.match(name):
                continue
            real = _norm(full)
            if _inside(real, self.root_real):
                out[name] = real
        return out

    def check_grammar(self, rel):
        if rel is None or rel == "":
            raise StaticRefused(400, "BAD_PATH", "empty")
        if len(rel) > 200:
            raise StaticRefused(400, "BAD_PATH", "too long")
        if "\x00" in rel or "%" in rel or "\\" in rel or ":" in rel:
            raise StaticRefused(400, "BAD_PATH", "forbidden character")
        if not _GRAMMAR.match(rel):
            raise StaticRefused(400, "BAD_PATH", "grammar")
        stem = rel.rsplit("/", 1)[-1].split(".", 1)[0].upper()
        if stem in RESERVED or any(s.upper() in RESERVED
                                   for s in rel.split("/")[:-1]):
            raise StaticRefused(400, "BAD_PATH", "reserved device name")
        ext = os.path.splitext(rel)[1]
        if ext not in ALLOWED_EXT:
            raise StaticRefused(400, "BAD_EXTENSION", ext)
        return ext

    def resolve(self, rel):
        """Return (absolute real path, content-type) or raise StaticRefused."""
        ext = self.check_grammar(rel)
        cand = os.path.join(self.root, *rel.split("/"))
        real = _norm(cand)
        if not _inside(real, self.root_real):
            raise StaticRefused(403, "OUTSIDE_STATIC_ROOT", rel)
        if self.use_whitelist:
            if rel not in self.whitelist or self.whitelist[rel] != real:
                raise StaticRefused(404, "STATIC_NOT_FOUND", rel)
        if not os.path.isfile(real):
            raise StaticRefused(404, "STATIC_NOT_FOUND", rel)
        return real, ALLOWED_EXT[ext]
