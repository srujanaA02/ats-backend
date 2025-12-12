VALID_TRANSITIONS = {
    "applied": ["screening", "rejected"],
    "screening": ["interview", "rejected"],
    "interview": ["offer", "rejected"],
    "offer": ["hired", "rejected"],
    "hired": [],
    "rejected": []
}


def validate_transition(current_stage, new_stage):
    return new_stage in VALID_TRANSITIONS.get(current_stage, [])
