from enum import Enum


class Sex(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    DECLINE_TO_ANSWER = "Decline to Answer"
