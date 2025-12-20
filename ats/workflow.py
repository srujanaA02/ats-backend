VALID_TRANSITIONS = {
    "Applied": ["Screening", "Rejected"],
    "Screening": ["Interview", "Rejected"],
    "Interview": ["Offer", "Rejected"],
    "Offer": ["Hired", "Rejected"],
    "Hired": [],
    "Rejected": []
}

def validate_transition(current_stage, new_stage):
    return new_stage in VALID_TRANSITIONS.get(current_stage, [])
