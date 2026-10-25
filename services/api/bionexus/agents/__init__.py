"""The roles that call a model: planner, literature, critic, verifier and synthesizer.

The code calls every role an "agent", but they are not alike. A model is used only here, in the
AI reviewers (planner, critic, verifier, synthesizer) and in literature, a source specialist that
reads the direction of papers. The roles that need no model live elsewhere:

- `bionexus.specialists`: genetics, pathways, clinical (source specialists, plain code)
- `bionexus.workflow.supervisor`: the coordinator (plain code)

This package also holds what every role is built on (`base.py`) and the limits on model use
(`optimization.py`). See the README, "The team and how it talks".
"""
