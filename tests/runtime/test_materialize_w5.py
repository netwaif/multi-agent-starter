"""W5 게이트 — brief materializer + backend capability (V8 inline_only 집행).

materializer가 file_references를 도출(LLM 자기신고 아님) · inline_only backend는 attachment 생성
금지 + 원본 tree 미노출 · secret scan fail-closed · backends.json grok-critic registered_disabled.
"""
import json, sys, pathlib, tempfile, os
_REPO = pathlib.Path(__file__).resolve().parents[2]
_RUNTIME = _REPO / "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/runtime"
_BACKENDS = _REPO / "plugins/multi-agent-starter/skills/configure-multiagent/generator/templates/claude/_shared/backends.json"
sys.path.insert(0, str(_RUNTIME))
import materialize as m

INLINE_ONLY = {"input_mode": "inline_only", "file_read": False, "tool_use": False}
FILE_READ = {"input_mode": "path", "file_read": True, "tool_use": True}


def _tmpfile(content: str) -> str:
    fd, p = tempfile.mkstemp(suffix=".md")
    os.write(fd, content.encode("utf-8")); os.close(fd)
    return p


def test_inline_only_gets_inline_with_provenance():
    p = _tmpfile("review this design carefully")
    try:
        brief = m.materialize_brief([p], INLINE_ONLY, mission="x")
        assert len(brief["inline_artifacts"]) == 1
        assert brief["file_references"] == []                 # inline_only는 참조 0
        art = brief["inline_artifacts"][0]
        assert art["source_path"] == p and art["sha256"] == m.sha256_of("review this design carefully")
    finally:
        os.unlink(p)

def test_file_read_backend_gets_reference_not_inline():
    p = _tmpfile("data")
    try:
        brief = m.materialize_brief([p], FILE_READ)
        assert brief["inline_artifacts"] == [] and brief["file_references"] == [p]
    finally:
        os.unlink(p)

def test_unapproved_path_never_surfaces():
    p1, p2 = _tmpfile("approved"), _tmpfile("secret-tree-file")
    try:
        brief = m.materialize_brief([p1, p2], INLINE_ONLY, approved_paths=[p1])
        srcs = [a["source_path"] for a in brief["inline_artifacts"]]
        assert p2 not in srcs and p2 not in brief["file_references"]   # 원본 tree 미노출
    finally:
        os.unlink(p1); os.unlink(p2)

def test_secret_scan_fail_closed():
    p = _tmpfile("token=ghp_" + "a" * 36)   # GitHub PAT 패턴
    try:
        raised = False
        try:
            m.materialize_brief([p], INLINE_ONLY)
        except m.SecretScanError:
            raised = True
        assert raised, "secret-bearing artifact must raise, not silently inline/drop"
    finally:
        os.unlink(p)

def test_check_admission_rejects_inline_only_with_file_refs():
    bad = {"mission": "x", "inline_artifacts": [], "file_references": ["/some/path"]}
    r = m.check_admission(bad, INLINE_ONLY)
    assert r["status"] == "ineligible" and r["reason"] == "inline_only_file_reference"

def test_check_admission_accepts_clean_inline_only():
    good = {"mission": "x", "inline_artifacts": [{"source_path": "/a", "sha256": "h", "content": "c"}],
            "file_references": []}
    assert m.check_admission(good, INLINE_ONLY)["status"] == "eligible"

def test_backends_json_grok_registered_disabled():
    b = json.loads(_BACKENDS.read_text())
    g = b["workers"]["grok-critic"]
    assert g["status"] == "registered_disabled"
    assert g["capabilities"] == INLINE_ONLY
    assert b["workers"]["gemini"]["capabilities"] == INLINE_ONLY   # agy auto-deny 반영


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    bad = 0
    for fn in fns:
        try:
            fn(); print(f"PASS {fn.__name__}")
        except Exception:
            bad += 1; print(f"FAIL {fn.__name__}"); traceback.print_exc()
    print(f"\n{len(fns)-bad}/{len(fns)} passed")
    sys.exit(1 if bad else 0)
