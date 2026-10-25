"""Agent optimizations: every lever that keeps an investigation cheap and fast, in one place.

Each constant below is one optimization (AO-n). The code that applies it imports it from here, so
this file is the one place to read, tune and review. The README table "Agent optimizations" matches
this list.

COST: fewer and smaller model calls
  AO-1  Only two agents call a model at all. The supervisor, genetics, pathways, clinical and the
        critic are plain code, so an investigation makes about ten small calls, not dozens.
  AO-2  Prompts stay small: source passages are shortened to AO_PASSAGE_CHARS, and only a second
        look reads the longer AO_RECHECK_PASSAGE_CHARS, on at most AO_MAX_RECHECKS_PER_ROUND.
  AO-3  Literature classifies the direction of at most AO_MAX_DIRECTION_CALLS papers.
  AO-4  The synthesizer writes from at most AO_MAX_RETAINED_EVIDENCE accepted records.
  AO-5  An identical prompt from the same organisation is paid for once: the model gateway keeps up
        to AO_RESPONSE_CACHE_ENTRIES answers (llm/cache.py) and records a hit in the ledger as
        `cached` with zero cost. Prompts put their fixed text first, so a provider's own prompt
        caching can also apply when a prompt is long enough to qualify.

SPEED: independent work runs at the same time
  AO-6  Up to AO_MAX_PARALLEL_SPECIALISTS specialists run together (workflow/dispatcher.py).
  AO-7  Literature's direction calls run together, AO_MAX_PARALLEL_MODEL_CALLS at a time.

SAFETY: the limits that stop a run from growing
  Budgets are reserved before each call and enforced per run and per organisation (workflow/
  budget.py); the router caps messages and depth (messaging/router.py).
"""

AO_PASSAGE_CHARS = 300  # AO-2: how much of a passage a normal prompt carries
AO_RECHECK_PASSAGE_CHARS = 1500  # AO-2: a second look reads the whole retrieved passage
AO_MAX_RECHECKS_PER_ROUND = 3  # AO-2: second looks per repair round (each is one model call)
AO_MAX_DIRECTION_CALLS = 10  # AO-3: papers whose direction a model reads
AO_MAX_RETAINED_EVIDENCE = 40  # AO-4 (SCOPE-06): records the synthesizer may use
AO_RESPONSE_CACHE_ENTRIES = 512  # AO-5: answers remembered per process (0 turns the cache off)
AO_MAX_PARALLEL_SPECIALISTS = 2  # AO-6 (SCOPE-05): specialists running at once
AO_MAX_PARALLEL_MODEL_CALLS = 4  # AO-7: direction calls running at once
