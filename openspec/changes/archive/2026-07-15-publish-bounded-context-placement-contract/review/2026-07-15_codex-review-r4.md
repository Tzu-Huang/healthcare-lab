# Codex Review Round 4: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`404ded3`)

Verdict: **Changes requested**

## Findings

### [P1] Preserve whitespace inside frontend string literals when fingerprinting

`tests/test_architecture_contract.py:154`

The string branch of `stable_fingerprint()` collapses every whitespace run in the raw JavaScript chunk before hashing it. That includes whitespace inside quoted strings and template literals, where whitespace is runtime data rather than formatting. Consequently, this materially changed payload returns no placement violation against the original inventory:

```javascript
// reviewed
function buildPayload() { return "A B"; }

// changed
function buildPayload() { return "A  B"; }
```

This is especially relevant to this repository's protocol previews and generated payload text, where spacing and line breaks may be significant. Hash raw frontend text after normalizing only transport-level differences such as CRLF versus LF, or use a syntax-aware normalizer that preserves literal contents. Add a fixture proving that whitespace changes inside a string or template literal invalidate the baseline.

### [P2] Preserve comment newlines when reporting CSS selector lines

`tests/test_architecture_contract.py:423`

`frontend_selector_families()` removes block comments with an empty replacement and then derives line numbers from the shortened source. Multiline comments therefore shift every later diagnostic upward. For this source, `.new-family` is on line 4 but the violation reports line 2:

```css
/* first
second
third */
.new-family { display: block; }
```

The OpenSpec scenario requires the current source line. Replace comment characters while retaining their newline count (or calculate positions against the original source), and add an assertion for the exact reported line after a multiline comment.

## Missing tests and residual risks

- Existing frontend fingerprint tests change executable tokens, but do not change whitespace within a JavaScript string or template literal.
- Selector tests assert only that a numeric line is present, not that it equals the selector's line in the original source.
- Several dependency-direction checks still use non-recursive `glob("*.py")`; nested backend layer packages would require recursive discovery.
- Current automated verification remains green at 25 architecture tests and 224 full-suite tests; both findings are uncovered edge cases rather than existing test failures.

## Resolution

- Frontend literal-whitespace coverage resolved by `f34dd2d`: source fingerprints now normalize only line endings, preserve all JavaScript literal contents, and use a regenerated reviewed frontend baseline.
- CSS line accuracy resolved in the follow-up fix: block comments are replaced with the same number of newline characters before selector discovery.
- Added both requested counterexamples. Focused architecture verification after both fixes: 26 tests passed.
