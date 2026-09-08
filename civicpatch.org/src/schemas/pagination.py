def pagination_offset(page: int, per_page: int) -> int:
    return (page - 1) * per_page


def pagination_total_pages(total_items: int, per_page: int) -> int:
    return max(1, (total_items + per_page - 1) // per_page)


def paginated_response(total_items: int, page: int, per_page: int, data: list) -> dict:
    """The house pagination shape: `page` + `per_page` in, `{total_items, page, total_pages,
    data}` out. Not every paged endpoint returns this — some carry extra summary fields, and
    search endpoints report `total_pages=0` on no results rather than clamping to 1 — so this
    is for the ones that match it exactly, not a mandate to reshape the others to fit."""
    return {
        "total_items": total_items,
        "page": page,
        "total_pages": pagination_total_pages(total_items, per_page),
        "data": data,
    }
