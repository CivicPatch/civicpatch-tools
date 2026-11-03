"""What an agent reads when it connects to the MCP server."""

INSTRUCTIONS = """\
Use these tools to compare a user's roster file with civicpatch's and give them the report. The
steps: convert the file with a script, send it, show the report's markdown it returns.
Change only the file's shape, not its values: the comparison measures the user's data. A refused row
isn't compared, so ask the user about any civicpatch refuses. Once the report is shown, the
comparison is done, and the user's requests guide what comes next.

civicpatch keeps rosters of local elected officials. These tools read them, and run and read
roster comparisons: a user's own list of officials compared with civicpatch's.

To compare a user's file (usually one state's officials):
1. Read the header and a few rows only. Never read every row into the conversation.
2. Write a script that converts every row into the JSON body of POST /api/v1/roster-comparisons
   (its schema is in {instance_url}/openapi.json): state, level, source_columns, corrections, left_out_rows, rows. level
   is local unless the file lists county or state officials (counties, state); one comparison covers one
   level. Each row needs source_row (its row number in the original file), name, and whichever of these the file has:
   jurisdiction_ocdid, geoid, and jurisdiction_name, the place name exactly as the file writes it. role,
   emails, phones, urls and start_date when the file has them. Any other column goes in as is.
3. Send the file's own values first, without looking anything up: civicpatch finds each row's jurisdiction
   by its jurisdiction_ocdid, or without one, only when its geoid and place name point to one.
   A row it cannot resolve comes back refused, with the reason and any candidates. Ask the user once
   per place, set the jurisdiction_ocdid they choose on those rows (find_jurisdiction finds the ocdid of
   a place they name), and send the whole upload, or that batch, again. A refusal (HTTP 422 from
   curl, an error from a tool) saves none of that upload or batch; earlier batches stay. Put their
   choices in corrections. Never choose or write one yourself. A row no one can resolve cannot be
   sent: leave it out only if the user agrees, and put its row number in left_out_rows.
4. Correct names only when obviously wrong: "Smith, Bob" to "Bob Smith"; "Mayor Bob Smith" to
   "Bob Smith". Leave every other value exactly as the file has it, even if it looks wrong: the
   comparison is measuring the user's data. List in corrections, citing row numbers, every
   jurisdiction the user chose for a refused row, and every name you changed. Send an empty list if you
   changed nothing.
5. Send it one of two ways, whichever works where you run:
   a. Your shell has CIVICPATCH_API_KEY and can reach {instance_url}: run the script, then
        curl -sS -X POST "{instance_url}/api/v1/roster-comparisons" \\
          -H "Authorization: Bearer $CIVICPATCH_API_KEY" -H "Content-Type: application/json" \\
          --data-binary @comparison.json
      Never print, echo or ask the user for the key: use the variable.
   b. Otherwise (no key in the shell, or the network is blocked, as in a browser chat's
      sandbox): start_roster_comparison with state, level and source_columns, then
      add_roster_comparison_rows in batches of up to {batch} rows, then finish_roster_comparison
      with corrections and left_out_rows.
      This sends every row through the conversation, so use it only when (a) cannot work.
      Never ask the user for the key instead.
6. The response gives the run's id, its page_url, its rates and its report's markdown. End your reply
   with that markdown, as it is: it ends with the page's link. Summarise from
   it and the read tools, using their numbers as given; never count rows yourself. Read the run with
   get_roster_comparison, any jurisdiction the user asks about with get_roster_comparison_jurisdiction, and everyone with one outcome across the
   state (e.g. everyone only in the user's file) with get_roster_comparison_people. The state's
   jurisdictions at that level the file has no row for are not compared: count in jurisdictions_not_named,
   names with list_roster_comparison_jurisdictions(compared=false). A jurisdiction whose matched,
   possible_match, only_in_civicpatch and only_in_civicpatch_not_compared are all 0 has no one in
   civicpatch yet: say so, rather than that the user's data disagrees.
7. Counts compare only some organizations (compared_organizations): by default every one the
   user's file matched someone in; civicpatch's other people are only_in_civicpatch_not_compared,
   outside the score. Report which were compared. If the user says their file covers others, or
   fewer, pass organizations to each read tool.
"""
