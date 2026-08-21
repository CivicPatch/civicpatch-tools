BEGIN;

-- Seat events. `posts.py` wrote no change logs at all, so who created or removed a seat was
-- unrecorded, while roles, people and pull requests were all attributed.
--
-- One type per act, with the seat's identity in the payload — `change_logs` has no post_id
-- column, the same reason person events carry person_id there.
INSERT INTO change_log_types (type) VALUES
    ('add_post'),
    ('edit_post'),
    ('delete_post');

COMMIT;
