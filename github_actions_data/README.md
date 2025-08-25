# Github Actions Data

Daily at 5 AM PST, a GitHub Actions workflow will query this server
for all the data it's scraped since the last query.

This server should send the data to GitHub Actions and flush all of the files 
under the .github_actions_data folder.