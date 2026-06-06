"""
Blood transfusion compatibility matrix.
Maps each donor blood group to the recipient blood groups it can safely donate to.
"""

# donor_blood_group -> [compatible recipient blood groups]
DONOR_TO_RECIPIENTS: dict[str, list[str]] = {
    "O Negative": [
        "O Negative", "O Positive",
        "A Negative", "A Positive",
        "B Negative", "B Positive",
        "AB Negative", "AB Positive",
    ],
    "O Positive": ["O Positive", "A Positive", "B Positive", "AB Positive"],
    "A Negative": ["A Negative", "A Positive", "AB Negative", "AB Positive"],
    "A Positive": ["A Positive", "AB Positive"],
    "B Negative": ["B Negative", "B Positive", "AB Negative", "AB Positive"],
    "B Positive": ["B Positive", "AB Positive"],
    "AB Negative": ["AB Negative", "AB Positive"],
    "AB Positive": ["AB Positive"],
    # Rare types — treated as exact match only unless type is confirmed
    "A1 Positive": ["A1 Positive", "A Positive", "AB Positive"],
    "A2 Positive": ["A2 Positive", "A Positive", "AB Positive"],
    "A1B Positive": ["A1B Positive", "AB Positive"],
    "A2 Negative": ["A2 Negative", "A Negative", "AB Negative"],
    "A2B Positive": ["A2B Positive", "AB Positive"],
    "A2B Negative": ["A2B Negative", "AB Negative"],
    # Bombay Blood Group — can only receive Bombay blood (rarest case)
    "Bombay Blood Group": ["Bombay Blood Group"],
}

# Rare groups that require expanded search radius automatically
RARE_BLOOD_GROUPS = {
    "AB Negative",
    "B Negative",
    "A Negative",
    "O Negative",
    "A1 Positive",
    "A2 Positive",
    "A1B Positive",
    "A2 Negative",
    "A2B Positive",
    "A2B Negative",
    "Bombay Blood Group",
}


def get_compatible_donors_for_recipient(recipient_blood_group: str) -> list[str]:
    """
    Given a recipient's blood group, return all donor blood groups
    that can safely donate to them.
    """
    compatible = []
    for donor_type, can_donate_to in DONOR_TO_RECIPIENTS.items():
        if recipient_blood_group in can_donate_to:
            compatible.append(donor_type)
    return compatible if compatible else [recipient_blood_group]


def can_donate_to(donor_blood_group: str, recipient_blood_group: str) -> bool:
    """Return True if the donor blood group is compatible with the recipient."""
    return recipient_blood_group in DONOR_TO_RECIPIENTS.get(donor_blood_group, [donor_blood_group])


def is_rare_blood_group(blood_group: str) -> bool:
    return blood_group in RARE_BLOOD_GROUPS


def get_initial_search_radius(blood_group: str) -> int:
    """Rare groups start at 100 km; standard groups start at 10 km."""
    return 100 if is_rare_blood_group(blood_group) else 10
