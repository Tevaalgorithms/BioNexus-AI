"""Source specialists that need no model: genetics, pathways and clinical trials.

Each one searches its public databases, applies the evidence gate (licence, cutoff, not excluded)
and returns what it found. No model is involved, so nothing here can be argued out of the facts.
They share their base class with the roles in `bionexus.agents`.

Literature is also a source specialist, but it asks a model to read the direction of papers that
state none, so it lives with the roles that call a model. The coordinator (the supervisor) is
plain code too and lives in `bionexus.workflow`.
"""
