# -*- coding: utf-8 -*-
"""极简 JSON Schema 子集校验器（标准库；仅供 S0D 测试用，用于对照旧 vhs_response.schema.json）。
支持：$ref(#/$defs/...)、oneOf、type、enum、const、required、properties、items、minLength、minItems、maxItems。
R1 追加（供 v0.2 草案使用；旧 schema 未使用这些关键字，因此对旧 schema 的校验结果不变）：
  allOf、anyOf、not、pattern、maxLength、minimum、maximum、additionalProperties（布尔或子 schema）。
不支持的关键字被忽略（在 compat_report 中说明）。不修改旧 schema。"""
import re

_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
    "boolean": lambda v: isinstance(v, bool),
}


def validate(instance, schema, root=None, path="$"):
    root = root if root is not None else schema
    if schema is True:
        return []
    if schema is False:
        return ["%s: false schema (property/instance not allowed)" % path]
    errs = []
    if "$ref" in schema:
        ref = schema["$ref"]
        assert ref.startswith("#/$defs/"), ref
        return validate(instance, root["$defs"][ref[len("#/$defs/"):]], root, path)
    if "oneOf" in schema:
        ok = [i for i, s in enumerate(schema["oneOf"]) if not validate(instance, s, root, path)]
        if len(ok) != 1:
            errs.append("%s: oneOf matched %d branches" % (path, len(ok)))
        return errs
    for sub in schema.get("allOf", []):
        errs += validate(instance, sub, root, path)
    if "anyOf" in schema and not any(not validate(instance, s, root, path) for s in schema["anyOf"]):
        errs.append("%s: anyOf matched 0 branches" % path)
    if "not" in schema and not validate(instance, schema["not"], root, path):
        errs.append("%s: must not match 'not' schema" % path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            return ["%s: type %s expected" % (path, t)]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append("%s: %r not in enum" % (path, instance))
    if "const" in schema and instance != schema["const"]:
        errs.append("%s: const %r expected" % (path, schema["const"]))
    if isinstance(instance, str) and "minLength" in schema and len(instance) < schema["minLength"]:
        errs.append("%s: minLength" % path)
    if isinstance(instance, str) and "maxLength" in schema and len(instance) > schema["maxLength"]:
        errs.append("%s: maxLength" % path)
    if isinstance(instance, str) and "pattern" in schema and not re.search(schema["pattern"], instance):
        errs.append("%s: pattern %s" % (path, schema["pattern"]))
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append("%s: minimum" % path)
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append("%s: maximum" % path)
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append("%s: minItems" % path)
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append("%s: maxItems" % path)
        if "items" in schema:
            for i, v in enumerate(instance):
                errs += validate(v, schema["items"], root, "%s[%d]" % (path, i))
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                errs.append("%s: missing required %s" % (path, k))
        for k, sub in schema.get("properties", {}).items():
            if k in instance:
                errs += validate(instance[k], sub, root, "%s.%s" % (path, k))
        ap = schema.get("additionalProperties", True)
        if ap is not True:
            for k in instance:
                if k in schema.get("properties", {}):
                    continue
                if ap is False:
                    errs.append("%s: additional property %s not allowed" % (path, k))
                else:
                    errs += validate(instance[k], ap, root, "%s.%s" % (path, k))
    return errs
