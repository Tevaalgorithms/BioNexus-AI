# Limits and honest caveats

What BioNexus does not do, and what is not proven yet. Linked from the [README](../README.md).

- **Synthetic demo evidence.** The offline sample and the evaluation reference set are made up. They show the mechanics work, not accuracy on real research.
- **The newest roles are tested for behaviour, not accuracy.** The planner, the critic's explanations and the verifier are tested with scripted models and sources: requests, limits, validation, fallbacks and the report are proven. Whether they improve results on real research has not been measured. `python -m bionexus.evals.ablation` runs the product with each step switched off and on, with a real model, so you can compare.
- **The multi-agent design is not shown to beat a simpler one.** On the tiny offline set a single-agent baseline matches the team. Answering that needs a scientist-written locked question set and real models.
- **Search is lexical, not semantic.** Ranking fuses PostgreSQL full-text search with pgvector, but the vectors are 64-bucket word-count hashes (`retrieval/embedder.py`, `HashingEmbedder`). They match shared words, not meaning, so a paper that says the same thing in different words can rank low. A hosted embedder (`OpenAIEmbedder`) is written but not wired in. Using it means a new index, since a new embedding model needs one.
- **Live models.** One full run has been done with an OpenAI model. Anthropic models have not been verified live, and production still uses placeholder models until an admin registers a real one.
- **Direction can be wrong.** Literature direction comes from a model reading an abstract and is labelled unreviewed. Database associations are not proof. Only a scientist's review makes a finding reliable.
- **Source rights are conservative defaults, not legal advice.** For example only open-access Europe PMC articles are reusable.
- **Data leaves the machine in live mode.** Do not load confidential material until the provider and retention decisions are made.
- **Single host, no high availability.** Web sessions are held in memory, so a restart (including every deploy) signs everyone out.
- **No MFA.** Sign-in is invite-only with a password.
- **Not built:** remove-member and delete-project, mapping corrections, scheduled source refresh, raw-response capture, a Python lockfile, alert delivery.
- **No treatment advice.** BioNexus assesses public evidence for research use. It does not diagnose, recommend treatment, accept patient records, or establish that a gene causes a disease. Counts guide judgement and are not probabilities.
