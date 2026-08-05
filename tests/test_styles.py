"""
Contrast contract for the "Clinical Instrument" palette.

Colour is the one part of a UI that regresses silently: nothing crashes, no test
goes red, and the app just becomes slightly harder to read for the people who
already found it hardest. This file pins the ratios so a token cannot be nudged
without the suite saying so.

Written after a one-off check caught disabled label text sitting at 2.62:1 in
light mode and 2.93:1 in dark. WCAG 2.1 exempts disabled controls from contrast
requirements, so that was defensible - but leaning on an exemption is not the
same as being readable, and the fix cost two hex values.

Thresholds follow WCAG 2.1 AA:
  - 4.5:1 for body text (1.4.3)
  - 3.0:1 for meaningful non-text UI, which is what the status edge bars and
    focus rings are (1.4.11)
"""

import pytest

from styles import DARK_TOKENS, LIGHT_TOKENS

BODY_TEXT_MINIMUM = 4.5
UI_COMPONENT_MINIMUM = 3.0


def relative_luminance(hex_colour: str) -> float:
    """WCAG relative luminance for an #rrggbb string."""
    digits = hex_colour.lstrip("#")
    channels = [int(digits[index : index + 2], 16) / 255 for index in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG contrast ratio, ordered so it never returns a value below 1."""
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


# (description, foreground token, background token, minimum ratio)
CONTRACTS = [
    ("body text on a panel", "text", "panel", BODY_TEXT_MINIMUM),
    ("body text on the app surface", "text", "surface", BODY_TEXT_MINIMUM),
    ("muted legend on a panel", "muted", "panel", BODY_TEXT_MINIMUM),
    ("primary button label", "on_accent", "accent_fill", BODY_TEXT_MINIMUM),
    ("selected row text", "on_selection", "selection", BODY_TEXT_MINIMUM),
    ("text over the taken row tint", "text", "tint_taken", BODY_TEXT_MINIMUM),
    ("text over the overdue row tint", "text", "tint_overdue", BODY_TEXT_MINIMUM),
    ("disabled control label", "disabled_text", "disabled_bg", UI_COMPONENT_MINIMUM),
    ("taken status edge", "signal_taken", "panel", UI_COMPONENT_MINIMUM),
    ("due status edge", "signal_due", "panel", UI_COMPONENT_MINIMUM),
    ("overdue status edge", "signal_overdue", "panel", UI_COMPONENT_MINIMUM),
    ("focus ring", "accent", "panel", UI_COMPONENT_MINIMUM),
]

THEMES = [("light", LIGHT_TOKENS), ("dark", DARK_TOKENS)]


@pytest.mark.parametrize("theme_name, tokens", THEMES, ids=[name for name, _ in THEMES])
@pytest.mark.parametrize(
    "description, foreground, background, minimum",
    CONTRACTS,
    ids=[contract[0].replace(" ", "-") for contract in CONTRACTS],
)
def test_contrast_meets_wcag_aa(theme_name, tokens, description, foreground, background, minimum):
    ratio = contrast_ratio(tokens[foreground], tokens[background])
    assert ratio >= minimum, (
        f"{theme_name}: {description} is {ratio:.2f}:1, below the {minimum}:1 floor "
        f"({tokens[foreground]} on {tokens[background]})"
    )


def test_both_themes_define_exactly_the_same_tokens():
    """
    A token present in one theme and missing in the other is how light mode
    drifted to 8 rules against dark's 380 in the first place.
    """
    assert LIGHT_TOKENS.keys() == DARK_TOKENS.keys()


# Deliberately not tested here: whether the three status signals look different
# from each other. The first attempt asserted a contrast ratio between them and
# failed, but the code was right and the test was wrong - due and overdue sit at
# 1.04:1 in light mode while being 26 degrees apart in hue, because luminance
# contrast cannot express a hue difference. Green and red routinely share a
# luminance band, which is exactly why "never colour alone" is the rule instead.
# That rule is carried by the Status text column and the reminder banner's
# wording, not by the palette, so it is not something this file can assert.
