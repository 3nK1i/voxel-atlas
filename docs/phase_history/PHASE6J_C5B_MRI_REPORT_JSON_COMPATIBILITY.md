# Phase 6J-C5B — MRI provider JSON report parsing compatibility

- Scope: parse the entire size-limited, regular-file `--report` JSON document emitted by the installed TotalSegmentator 2.18.0 CLI (`json.dump(..., indent=2)`); keep the existing report schema, identity, path, class, GPU, and mode validation unchanged.
- Motivation: C3B previously attempted to parse only the last nonempty report line, which is `}` in a formatted JSON document. A successful real model run could therefore fail during report acceptance.
- Test-first red state: the formatted-report unit test, the appended-JSON rejection test, and the C3B full synthetic lifecycle fail against the prior parser. After the correction both formatted and compact JSON are accepted and malformed, appended, non-object, oversized, linked, or invalid-encoding reports fail closed.
- No patient data, model weights, runtime configuration, CT paths, application provider registration, MRI execution authorization, or inference are touched by this patch.
- This slice resolves report *framing*. C5 still requires separately checking effective installed CLI report values (including `device`, `output_type`, and class names) and then authorizing the single restricted real trial.
