from datetime import date

from schemas.elections import Election


def filter_upcoming(elections: list[Election], today: date) -> list[Election]:
    return [election for election in elections if election.date >= today]
