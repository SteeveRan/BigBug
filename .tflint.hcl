# TFLint config for BigBug infra (issue #78, ADR-0038).
# Run: `tflint --recursive` from the repo root (config applies to all layers).
# Bundled terraform ruleset only — no plugins, no deep checking
# (module sources are local; provider-level checks need credentials/network).
plugin "terraform" {
  enabled = true
  preset  = "recommended"
}
