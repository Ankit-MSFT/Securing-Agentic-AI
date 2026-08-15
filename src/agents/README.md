# Agent implementations

This directory contains the assistant implementations used in the experiment.

## Contents

- `baseline/`: intentionally vulnerable or minimally protected agent
- `hardened/`: progressive hardening variants corresponding to the security staircase

## Expected pattern

Each agent variant should expose the same interface and comparable tool access, with the only difference being the controls being evaluated.

This makes it possible to compare baseline and hardened behavior under the same scenario definitions.
