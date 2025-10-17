"""Static workout templates consumed by the training planner."""
from typing import Dict, List


WORKOUT_LIBRARY: Dict[str, List[dict]] = {
    "easy_runs": [
        {
            "name": "Recovery Run",
            "description": "30-45 minutes easy pace, HR Zone 2",
            "target_duration": 40,
        }
    ]
}
