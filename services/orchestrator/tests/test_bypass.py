from orchestrator.bypass import build_bypass_variants


def test_returns_three_documented_techniques():
    variants = build_bypass_variants("GET", "/admin/users")
    techniques = {v.technique for v in variants}
    assert techniques == {"origin_header_spoof", "path_segment_mutation", "method_override"}


def test_origin_header_spoof_sets_forwarded_headers():
    variants = build_bypass_variants("GET", "/admin/users")
    origin = next(v for v in variants if v.technique == "origin_header_spoof")
    assert origin.extra_headers["X-Forwarded-For"] == "127.0.0.1"
    assert origin.method == "GET"
    assert origin.path == "/admin/users"


def test_method_override_switches_to_post_and_preserves_original_method_header():
    variants = build_bypass_variants("DELETE", "/admin/users/1")
    override = next(v for v in variants if v.technique == "method_override")
    assert override.method == "POST"
    assert override.extra_headers["X-HTTP-Method-Override"] == "DELETE"


def test_path_segment_mutation_inserts_double_slash():
    variants = build_bypass_variants("GET", "/admin/users")
    mutated = next(v for v in variants if v.technique == "path_segment_mutation")
    assert mutated.path == "/admin//users"
