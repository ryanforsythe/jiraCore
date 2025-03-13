# Jira API 
Performs Jira actions using the REST API.

## Keyring Credentials
User credentials are stored in the Credentials Manager. To add or updated, go to 
<mark>Credentials Manager->Generic Credentials</mark>.
https://pypi.org/project/keyring/

Expected Service Account credentials:
- jira-svcuser

*Add the credential above as 'Internet or network address:' and then the Jira user name and API Key.* 

By default the application uses the User credentials.

## Variables Files
.env.template: adjust the environment variables and remove .template

jiraVariables.py: contains variables related to the Jira application. Requires getting ID's for issue types, workflow steps, etc.
