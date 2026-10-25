"""The team's roles, one module each.

The code calls every role an "agent", but they are not alike. There is one coordinator (the
supervisor), four source specialists (genetics, literature, pathways, clinical) that search public
databases, and four AI reviewers (planner, critic, verifier, synthesizer) where a model makes a
judgement. Five roles use a model: those four and literature. See the README, "The team and how it
talks", and `optimization.py` for the limits on model use.
"""
