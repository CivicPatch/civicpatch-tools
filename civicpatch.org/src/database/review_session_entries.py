from database.database import get_pool


async def pass_current_entry(review_session_id: str, entry_number: int) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'passed'
                WHERE review_session_id = %s AND entry_number = %s AND status = 'claimed'
                """,
                (review_session_id, entry_number),
            )


async def resolve_review_session_entries_by_request_id(request_id: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved', resolved_at = NOW()
                WHERE %s = ANY(request_ids) AND status != 'resolved'
                """,
                (request_id,),
            )
            # Append the resolved jurisdiction to the session's reviewed list
            # so it won't appear in future allocations for this session.
            await cur.execute(
                """
                UPDATE review_sessions rs
                SET reviewed_ocdids = array_append(reviewed_ocdids, r.jurisdiction_ocdid)
                FROM requests r
                WHERE r.id::text = %s
                  AND NOT (r.jurisdiction_ocdid = ANY(COALESCE(rs.reviewed_ocdids, ARRAY[]::text[])))
                  AND EXISTS (
                      SELECT 1 FROM review_session_entries rse
                      WHERE rse.review_session_id = rs.id
                        AND %s = ANY(rse.request_ids)
                  )
                """,
                (request_id, request_id),
            )


async def resolve_review_session_entries_by_pr_number(pr_number: str) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                UPDATE review_session_entries
                SET status = 'resolved', resolved_at = NOW()
                WHERE EXISTS (
                    SELECT 1 FROM pipeline_runs j
                    JOIN requests r ON r.id = j.request_id
                    JOIN pull_requests pr ON pr.request_id = r.id
                    WHERE pr.url LIKE %s
                      AND j.request_id::text = ANY(review_session_entries.request_ids)
                )
                AND status != 'resolved'
                """,
                (f"%/pull/{pr_number}",),
            )
