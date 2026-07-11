"""
Constants, WHEEL data, and emotion math functions.
"""

RING_CORE = 0.33
RING_MID  = 0.66

WHEEL = [
    {
        "name": "Joy", "color": "#e8b923",
        "mid": [
            {"label": "Optimistic", "outer": ["Hopeful", "Inspired", "Eager"]},
            {"label": "Confident",  "outer": ["Proud", "Courageous", "Self-assured"]},
            {"label": "Loving",     "outer": ["Affectionate", "Fond", "Warm"]},
            {"label": "Playful",    "outer": ["Delighted", "Amused", "Cheerful"]},
        ],
    },
    {
        "name": "Trust", "color": "#5b9a4d",
        "mid": [
            {"label": "Accepted",  "outer": ["Respected", "Valued", "Included"]},
            {"label": "Grateful",  "outer": ["Blessed", "Appreciative", "Thankful"]},
            {"label": "Peaceful",  "outer": ["Calm", "Content", "Serene"]},
            {"label": "Admiring",  "outer": ["Impressed", "Reverent", "Devoted"]},
        ],
    },
    {
        "name": "Fear", "color": "#3d84cf",
        "mid": [
            {"label": "Scared",     "outer": ["Frightened", "Terrified", "Panicky"]},
            {"label": "Anxious",    "outer": ["Worried", "Nervous", "Uneasy"]},
            {"label": "Insecure",   "outer": ["Inadequate", "Inferior", "Worthless"]},
            {"label": "Vulnerable", "outer": ["Fragile", "Hopeless", "Exposed"]},
        ],
    },
    {
        "name": "Surprise", "color": "#1fa6b8",
        "mid": [
            {"label": "Amazed",   "outer": ["Astonished", "Awed", "Dazzled"]},
            {"label": "Confused", "outer": ["Disillusioned", "Perplexed", "Dumbfounded"]},
            {"label": "Startled", "outer": ["Shocked", "Speechless", "Stunned"]},
            {"label": "Overcome", "outer": ["Moved", "Overwhelmed", "Reeling"]},
        ],
    },
    {
        "name": "Sadness", "color": "#5c6bc0",
        "mid": [
            {"label": "Lonely",    "outer": ["Isolated", "Abandoned", "Excluded"]},
            {"label": "Grieving",  "outer": ["Despair", "Sorrow", "Heartbroken"]},
            {"label": "Hurt",      "outer": ["Injured", "Wronged", "Disappointed"]},
            {"label": "Depressed", "outer": ["Empty", "Hopeless", "Miserable"]},
        ],
    },
    {
        "name": "Disgust", "color": "#9c46a8",
        "mid": [
            {"label": "Disapproving",  "outer": ["Judgmental", "Critical", "Skeptical"]},
            {"label": "Disliking",     "outer": ["Repelled", "Detestable", "Loathsome"]},
            {"label": "Contemptuous",  "outer": ["Ridicule", "Scorn", "Disdain"]},
            {"label": "Revolted",      "outer": ["Nauseated", "Appalled", "Awful"]},
        ],
    },
    {
        "name": "Anger", "color": "#d64545",
        "mid": [
            {"label": "Frustrated",  "outer": ["Annoyed", "Irritated", "Aggravated"]},
            {"label": "Hostile",     "outer": ["Hateful", "Spiteful", "Vindictive"]},
            {"label": "Aggressive",  "outer": ["Provoked", "Furious", "Enraged"]},
            {"label": "Critical",    "outer": ["Insulted", "Indignant", "Betrayed"]},
        ],
    },
    {
        "name": "Anticipation", "color": "#e08324",
        "mid": [
            {"label": "Interested", "outer": ["Curious", "Alert", "Attentive"]},
            {"label": "Eager",      "outer": ["Enthusiastic", "Motivated", "Energized"]},
            {"label": "Excited",    "outer": ["Passionate", "Aroused", "Elated"]},
            {"label": "Stressed",   "outer": ["Overwhelmed", "Pressured", "Impatient"]},
        ],
    },
]


def core_index(theta):
    theta = theta % 360
    return int(theta // 45)


def core_of(theta):
    return WHEEL[core_index(theta)]


def leaf_of(theta, r):
    idx = core_index(theta)
    core = WHEEL[idx]
    theta_mod = theta % 360
    angle_inside = theta_mod - idx * 45
    mid_width = 45 / len(core["mid"])
    mid_index = min(len(core["mid"]) - 1, int(angle_inside // mid_width))
    mid = core["mid"][mid_index]
    angle_mid = angle_inside - mid_index * mid_width
    outer_width = mid_width / len(mid["outer"])
    outer_index = min(len(mid["outer"]) - 1, int(angle_mid // outer_width))

    if r < RING_CORE:
        ring = "core"
        word = core["name"]
    elif r < RING_MID:
        ring = "mid"
        word = mid["label"]
    else:
        ring = "outer"
        word = mid["outer"][outer_index]

    return {
        "core": core,
        "mid": mid,
        "ring": ring,
        "word": word,
    }


def breadcrumb(theta, r):
    leaf = leaf_of(theta, r)
    text = f"{leaf['core']['name']} \u2192 {leaf['mid']['label']}"
    if leaf["ring"] == "outer":
        text += f" \u2192 {leaf['word']}"
    return text


def emotion_color(theta):
    """Return the hex color of the core emotion at angle theta."""
    return core_of(theta)["color"]
