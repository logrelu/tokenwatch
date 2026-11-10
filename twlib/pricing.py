"""Token kinds, list prices and per-reply cost."""

KINDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

# USD per million tokens: (input, output, cache read). Public API list prices, 2026-09.
# Matched by prefix, most specific first. Good enough for "where does it go", not for invoicing —
# and on a Pro/Max subscription you don't pay per token at all; read it as how fast you use your limit.
PRICES = [
    ("claude-fable-5-1",  (10.0, 50.0, 0.25)),
    ("claude-mythos-5-1", (10.0, 50.0, 0.25)),
    ("claude-fable",      (10.0, 50.0, 1.00)),
    ("claude-mythos",     (10.0, 50.0, 1.00)),
    ("claude-opus-5-5",   (4.0, 20.0, 0.20)),
    ("claude-opus",       (5.0, 25.0, 0.50)),
    ("claude-sonnet-5",   (2.0, 10.0, 0.20)),
    ("claude-sonnet",     (3.0, 15.0, 0.30)),
    ("claude-haiku",      (1.0, 5.0, 0.10)),
]

# Cache writes cost more than plain input: 1.25x for the 5-minute cache, 2x for the 1-hour cache.
WRITE_5M, WRITE_1H = 1.25, 2.0

# Cache writes cost more than plain input: 1.25x for the 5-minute cache, 2x for the 1-hour cache.
WRITE_5M, WRITE_1H = 1.25, 2.0

TOP_TIER = ("claude-fable", "claude-mythos", "claude-opus")

CHEAPER = "claude-sonnet-5-5"       # what the "same work on a cheaper model" figure is priced at

def cost_parts(model, u):
    """Dollar cost of one reply by token kind, at list prices; all zero for models we don't know."""
    for prefix, (p_in, p_out, p_read) in PRICES:
        if (model or "").startswith(prefix): break
    else:
        p_in = p_out = p_read = 0.0
    w = u.get("cache_creation_input_tokens", 0)
    w1h = min(w, (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0))
    return {"in": u.get("input_tokens", 0) * p_in / 1e6,
            "out": u.get("output_tokens", 0) * p_out / 1e6,
            "write": ((w - w1h) * WRITE_5M + w1h * WRITE_1H) * p_in / 1e6,
            "read": u.get("cache_read_input_tokens", 0) * p_read / 1e6}

def cost_of(model, u):
    return sum(cost_parts(model, u).values())
