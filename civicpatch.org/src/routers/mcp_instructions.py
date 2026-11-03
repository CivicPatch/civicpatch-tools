"""What an agent reads when it connects to the MCP server."""

INSTRUCTIONS = """\
Use these tools to compare a user's roster file with civicpatch's and give them the report. The
steps: convert the file with a script, send it, show the report's markdown it returns.
Change only the file's shape, not its values: the comparison measures the user's data. A refused row
isn't compared, so ask the user about any civicpatch refuses. Once the report is shown, the
comparison is done, and the user's requests guide what comes next.

1. Read the header and a few rows only. Never read every row into the conversation.
2. Script every row into the JSON body of POST {instance_url}/api/v1/roster-comparisons (schema:
   {instance_url}/openapi.json). Each row needs source_row, name, and whichever the file has of
   jurisdiction_ocdid, geoid and jurisdiction_name, then role, emails, phones, urls and start_date. Other
   columns go in as they are. level is local unless the file lists county or state officials.
3. Send the file's own values first, without looking anything up. A refused row comes back with its
   reason and candidates, and nothing from that upload or batch is saved. Ask the user once per place,
   set the jurisdiction_ocdid they choose (find_jurisdiction finds a place they name), list it in
   corrections, and send that upload or batch again. Never choose one yourself. Leave a row out only if the user
   agrees, and put its number in left_out_rows.
4. Change a name only when obviously wrong ("Smith, Bob" to "Bob Smith") and list it in corrections.
5. If your shell has CIVICPATCH_API_KEY and reaches civicpatch, send the file:
     curl -sS -X POST "{instance_url}/api/v1/roster-comparisons" \\
       -H "Authorization: Bearer $CIVICPATCH_API_KEY" -H "Content-Type: application/json" \\
       --data-binary @comparison.json
   Otherwise use start_roster_comparison. Never print the key or ask the user for it.
6. End your reply with the response's markdown, as it is. Use its numbers; never count rows yourself.
"""
