"""
Utility functions for template generation.
"""


def pluralize(word: str) -> str:
    """
    Simple English pluralization.

    Args:
        word: Singular word to pluralize

    Returns:
        Pluralized word
    """
    if word.endswith("y"):
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"
