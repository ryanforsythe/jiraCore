import requests
import json
import jmespath as jq
import pandas as pd
from requests.auth import HTTPBasicAuth
from collections import namedtuple
import mimetypes
import pathlib
import re
from dotenv import load_dotenv
import os
import sys
from loguru import logger

import jiraVariables as jvars


class JiraAPI:
    """
    Handles interactions with the Jira API for project, issue, and user management.

    This class provides methods to authenticate, manage projects, users, and issues in
    Jira by leveraging the Jira REST API. It includes functionality for project retrieval,
    issue creation, user information queries, and search operations.

    :ivar jvars: Instance of JiraVariables providing default configurations.
    :type jvars: JiraVariables
    :ivar base_url: The base URL of the Jira instance used in requests.
    :type base_url: str
    :ivar headers: HTTP headers used for API requests, including content type and
        additional authentication headers when authenticated.
    :type headers: dict
    :ivar default_issue_type_id: Default type ID for creating Jira issues.
    :type default_issue_type_id: str
    :ivar default_priority_id: Default priority ID for creating Jira issues.
    :type default_priority_id: str
    :ivar default_project_key: The project key used if no specific key is provided.
    :type default_project_key: str
    :ivar _auth: Holds the authentication object using basic authentication.
    :type _auth: HTTPBasicAuth
    :ivar project_info: Stores metadata of the Jira project after retrieval.
    :type project_info: dict
    :ivar project_id: ID of the currently targeted Jira project.
    :type project_id: str
    """
    def __init__(self, project_key=None):
        """
        Constructor to initialize JiraAPI instance.
        :param base_url: Jira base URL
        :param username: Jira username
        :param auth_token: Jira API token
        """
        self.jvars = jvars.JiraVariables()
        self.init_logger()
        self.base_url = self.jvars.base_jira_url
        self._auth = None
        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self.default_issue_type_id = self.jvars.default_issue_type_id
        self.default_priority_id = self.jvars.default_priority_id
        if project_key is None:
            self.default_project_key = self.jvars.default_project_key
        else: self.default_project_key = project_key
        self.get_project_info(self.default_project_key)

        self._auth = HTTPBasicAuth(self.jvars.jira_user_name, self.jvars.jira_password)
        self._set_authenticated_headers()

    def init_logger(self):
        LOGGER_LEVEL = self.jvars.log_level
        CONSOLE_LEVEL = 'DEBUG'
        self.logger.add(jvars.log_location, rotation="30 MB", retention=5, enqueue=True, level=LOGGER_LEVEL)
        time_format = "YYYY-MM-DD HH:mm:ss"
        console_format = f"<green>{{time:{time_format}}}</green> | <level>{{level: <8}}</level> | {{name}}:{{function}}:{{line}} - {{message}}"
        self.logger.add(sink=sys.stdout,
                   level=CONSOLE_LEVEL,
                   format=console_format,
                   colorize=True,
                   )

    def _set_authenticated_headers(self):
        """
        Update headers with additional authentication information.
        """
        self.headers["X-ExperimentalAPI"] = "opt-in"

    def authenticate(self):
        """
        Authenticate the user by making a test API call.
        :return: Tuple containing the status code and headers with authentication info
        """
        url = f'{self.base_url}api/3/myself'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            return response.status_code
        except Exception as e:
            status_code = -14
            self.logger.error(f"Status Code: {status_code}; Authentication failed: {e}")
            return status_code
        
    def get_project_info(self, project_key):
        """
        Retrieve details for a Jira project.
        :param project_key: Project key
        :return: Project information
        """
        url = f'{self.base_url}api/3/project/{project_key}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            self.project_info = json.loads(response.text)
            self.project_id = jq.search('id',self.project_info)
            self.logger.debug(f"Project Key: {project_key}; Status Code: {response.status_code}; Result: {self.project_info}")
            return response.status_code
        except Exception as e:
            self.project_id = -1
            status_code = -16
            self.logger.error(f"Status Code: {status_code}; Error retrieving project info. Project Key: {project_key}; {e}")
            return status_code

    def get_user_info(self, account_id):
        """
        Get information related to a user.
        :param account_id: Jira account ID
        :return: Named tuple with user info
        """
        user_info = namedtuple("user_info", ["status_code", "jira_user_dict", "jira_user_found", "jira_user_email",
                                             "jira_user_display_name", "jira_user_active"])
        query = {'accountId': account_id}
        url = f'{self.base_url}api/3/user'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth, params=query)
            user_data = json.loads(response.text)
            if user_data:
                return user_info(
                    response.status_code, user_data, 1,
                    user_data.get("emailAddress"), user_data.get("displayName"), user_data.get("active")
                )
                self.logger.debug(f"Account ID: {account_id}; Status Code: {response.status_code}; Result: {user_data}")
            else:
                self.logger.warning(f"User not found. Account ID: {account_id}")
                return user_info(response.status_code, {}, 0, "", "", False)
        except Exception as e:
            status_code = -17;
            self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Account ID: {account_id}; {e}")
            return user_info(status_code, {}, -1, "", "", False)

    def get_user_by_email(self, email_address):
        """
        Get information related to a user by passing the email address.
        :param account_id: Jira account ID
        :return: Namedtuple user_info(status_code, jira_user_dict, jira_user_found)
        """
        user_info = namedtuple("user_info", ["status_code", "jira_user_dict", "jira_user_found"])

        pattern = re.compile(r'^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w+$', re.IGNORECASE)
        if pattern.match(email_address) is None:
            status_code = -18.1;
            jira_user_found = -1;
            jira_user_dict = []
            self.logger.warning(f"Status Code: {status_code}; Invalid email address. Email Address: {email_address}")
            return user_info(status_code, {}, 0)
        else:
            try:
                url = f'{self.base_url}api/3/user'
                response = requests.get(url, headers=self.headers, auth=self._auth)
                user_data = json.loads(response.text)
                self.logger.debug(f"Email Address: {email_address}; Status Code: {response.status_code}; Result: {user_data}")
                if user_data:
                    jira_user_dict = user_data[0]
                    jira_user_dict.pop("avatarUrls")
                    return user_info(
                        response.status_code, jira_user_dict, 1
                    )
                else:
                    self.logger.warning(f"User not found. Email Address: {email_address}")
                    return user_info(response.status_code, {}, 0)
            except Exception as e:
                status_code = -18;
                self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Email Address: {email_address}; {e}")
                return user_info(status_code, {}, -1)

    def search_issues(self, search_query, as_dataframe=False):
        """
        Search Jira issues based on a query.
        :param search_query: Jira search query (JQL)
        :param as_dataframe: Return result as pandas DataFrame if True
        :return: Search results in the desired format
        """
        IssueSearchResult = namedtuple("issue_search_results", ["status_code", "jira_issues"])
        url = f'{self.base_url}api/3/search?jql={search_query}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            result_dict = json.loads(response.text)
            self.logger.debug(f"Search query: {search_query}; Result: {result_dict}")
            if as_dataframe:
                jira_issues = pd.json_normalize(result_dict, record_path=['issues'], errors='ignore', sep='_')
            else:
                jira_issues = result_dict
            return IssueSearchResult(response.status_code, jira_issues)
        except Exception as e:
            status_code = -21
            self.logger.error(f"Status Code: {status_code}; Error searching for issues. Query: {search_query}; {e}")
            return IssueSearchResult(status_code, [])

    def issue_create(self, summary, project_id=None, issue_type_id=None, description=None, assignee=None, priority=None):
        """
        Create a Jira issue.
        :param project_id: Project ID
        :param summary: Issue summary
        :param issue_type_id: Issue type ID (default: 12412)
        :param description: Issue description
        :param assignee: Assignee account ID, optional
        :param priority: Priority ID, optional (default: 10100)
        :return: Status code and issue info
        """
        if project_id is None: project_id = self.project_id
        if issue_type_id is None: issue_type_id = self.default_issue_type_id
        if description is None: description = ""
        if assignee is None: assignee = ""
        if priority is None: priority = self.default_priority_id
        priority = json.loads(f'"{priority}"')
        input_json = {
            "fields": {
                "assignee": {"accountId": assignee},
                "description": {
                    "content": [
                        {"content": [{"text": description, "type": "text"}], "type": "paragraph"}
                    ],
                    "type": "doc",
                    "version": 1,
                },
                "issuetype": {"id": issue_type_id},
                "priority": {"id": priority},
                "project": {"id": project_id},
                "summary": summary,
            }
        }
        payload = json.dumps(input_json)
        url = f'{self.base_url}api/3/issue'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            logger.info(f"Issue created: {response.status_code}; Project: {project_id}; Summary: {summary}; Issue Type: {issue_type_id}; Priority: {priority}; Assignee: {assignee}; ")
            return response.status_code, response.json()
        except Exception as e:
            status_code = -35
            logger.error(f"Status Code: {status_code}; Error creating issue; Project: {project_id}; Summary: {summary}; Issue Type: {issue_type_id}; Priority: {priority}; Assignee: {assignee}; {e}")
            return status_code, str(e)

    def issue_transition(self, issue_id, transition_id):
        """
        Transition a Jira issue.
        :param issue_id: Jira issue ID
        :param transition_id: Transition ID
        :return: Status code. Error returns status code -37.
        """
        payload = json.dumps({"transition": {"id": transition_id}})
        url = f'{self.base_url}api/3/issue/{issue_id}/transitions'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            self.logger.info(f"Issue transitioned: {response.status_code}; Issue ID: {issue_id}; Transition ID: {transition_id}")
            return response.status_code
        except Exception as e:
            status_code = -37
            self.logger.error(f"Status Code: {status_code}; Error transitioning issue. Issue ID: {issue_id}; Transition ID: {transition_id}; {e}")
            return status_code

    def issue_field_update(self, issue_id, field_update_dict) -> int:
        """
        Update a field in a Jira issue.
        :param issue_id: Jira issue ID
        :param field_udpate_dict: Field dictionary.
        :return: Status code
        :Example: field_update_data = {"customfield_14064": [{"accountId": "712020:d4f13f91-ed7f-493d-8fef-4029b44eb7cb"},{"accountId": "5a4e734573cadb08a03ed16c"}]}
        """
        payload = json.dumps({"fields": field_update_dict})
        url = f'{self.base_url}api/3/issue/{issue_id}'
        try:
            response = requests.put(url, headers=self.headers, auth=self._auth, data=payload)
            self.logger.info(f"Issue field updated: {response.status_code}; Issue ID: {issue_id}")
            return response.status_code
        except Exception as e:
            status_code = -35
            self.logger.error(f"Status Code: {status_code}; Error updating issue. Issue ID: {issue_id}; Field Data: {field_update_dict}; {e}")
            return status_code

    def issue_detail(self, issue_id, include_forms=False):
        """
        Retrieve the detail for a Jira issue. Also includes the issue forms if include_forms=True.
        :param issue_id: Jira issue ID
        :param include_forms: True/False. Default False. Option to include forms.
        :return: Namedtuple. issue_detail_info(status_code, jira_issue_info_dict[reporter_account_id, reporter_email_address, issue_status_id, issue_status_name,
                                change_start_datetime, assignee_id, assignee_email_address], jira_issue_dict, question_response_df)
        """
        issue_detail_info = namedtuple("issue_detail_info", ["status_code", "jira_issue_info_dict", "jira_issue_dict",
                                                             "question_response_df"])
        url = f'{self.base_url}api/3/issue/{issue_id}?properties=*all'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            status_code = response.status_code
            # jiraIssueDetail_json = json.loads(jiraIssueDetail.text)
            # print(jiraIssueForms.text)
            jiraIssueFormsText = response.text
            # print(jiraIssueFormsText)
            jira_issue_dict = json.loads(response.text)
            reporter_account_id = jq.search('fields.reporter.accountId', jira_issue_dict)
            reporter_email_address = jq.search('fields.reporter.emailAddress', jira_issue_dict)
            issue_status_id = jq.search('fields.status.id', jira_issue_dict)
            issue_status_name = jq.search('fields.status.name', jira_issue_dict)
            change_start_datetime = jq.search('fields.customfield_14069', jira_issue_dict)
            assignee_id = jq.search("fields.assignee.accountId", jira_issue_dict)
            assignee_email_address = jq.search("fields.assignee.emailAddress", jira_issue_dict)
            jira_issue_info_dict = {"reporter_account_id": reporter_account_id,
                                    "reporter_email_address": reporter_email_address,
                                    "issue_status_id": issue_status_id,
                                    "issue_status_name": issue_status_name,
                                    "change_start_datetime": change_start_datetime,
                                    "assignee_id": assignee_id,
                                    "assignee_email_address": assignee_email_address, }

            if include_forms == True:
                jira_issue_properties = jira_issue_dict.get('properties')
                # the proforma.form.i value changes as a unique identifier
                jira_issue_forms_element = {k: v for k, v in jira_issue_properties.items() if
                                            k.startswith('proforma.forms.i')}
                jira_issue_form_key, jira_issue_forms = next(iter(jira_issue_forms_element.items()))
                questions_list = jq.search('design.questions', jira_issue_forms)
                # print(questions_list)
                data = []
                # Loop through question_list
                for key, val in questions_list.items():
                    # Append a dict containing the required information to the list
                    data.append(
                        {'questionID': key, 'jiraField': val.get('jiraField'), 'type': val.get('type'),
                         'label': val.get('label'), 'questionKey': val.get('questionKey'),
                         'choices': val.get('choices')})
                # print(f"{questions_list}")
                # Convert the list of dicts to a DataFrame
                df_questions = pd.DataFrame(data)

                responses_list = jq.search('state.answers', jira_issue_forms)
                # print(responses_list)
                responses_list_fmt = []

                # Loop through question_list
                for key, val in responses_list.items():
                    # Append a dict containing the required information to the list
                    responses_list_fmt.append(
                        {'questionID': key, 'textField': val.get('text'), 'users': val.get('users'),
                         'label': val.get('label'), 'choices': val.get('choices'), 'date': val.get('date'),
                         'time': val.get('time')})

                # print(responses_list)
                # Convert the list of dicts to a DataFrame
                # print(f"responses_list_fmt: {responses_list_fmt}")
                df_responses = pd.DataFrame(responses_list_fmt)
                # combine the dataframes df_responses and df_questions
                question_response_df = pd.merge(df_responses, df_questions, on='questionID')
                question_response_df.loc[:, "type_name"] = ""
                question_response_df.loc[:, "value_consolidated"] = ""
                # print(f"question_response_df: {question_response_df.to_json(orient='records')}")
                for ind in question_response_df.index:
                    # print(f"index:{ind}")
                    response_type = question_response_df.loc[ind, 'type']
                    # print(f"response_type:{response_type}")
                    response_type_name = self.response_type_ref(response_type)
                    response_type_col = self.response_type_col_ref(response_type)
                    # print(f"response_type_col:{response_type_col}; response_type_name:{response_type_name}")
                    question_response_df.loc[ind, 'type_name'] = response_type_name
                    if response_type not in ('dt', 'cs', 'cd', 'cl', 'cm'):
                        question_response_df.loc[ind, 'value_consolidated'] = str(
                            question_response_df.loc[ind, response_type_col])
                    elif response_type == 'dt':
                        question_response_df.loc[
                            ind, 'value_consolidated'] = f"{question_response_df.loc[ind, 'date']}H{question_response_df.loc[ind, 'time']}"
                    elif response_type in ('cs', 'cd', 'cl', 'cm'):
                        choices_responses = question_response_df.loc[ind, 'choices_x']
                        choices_options = question_response_df.loc[ind, 'choices_y']
                        # print(f"choice_responses:{choices_responses}; choices_options:{choices_options}")
                        if choices_options is not None:
                            selected_choices = [{'choice_id': option['id'], 'value': option['label']} for option in
                                                choices_options if
                                                option['id'] in choices_responses]
                            selected_choices_list = json.dumps(selected_choices)
                            question_response_df.loc[ind, 'value_consolidated'] = selected_choices_list
                        else:
                            question_response_df.loc[ind, 'value_consolidated'] = None
                # print(f"question_response_df: {question_response_df}")
                return issue_detail_info(status_code, jira_issue_info_dict, jira_issue_dict, question_response_df)
            else:
                question_response_df = pd.DataFrame()
                self.logger.debug(f"Issue detail. Issue ID: {issue_id}; Status Code: {status_code}; Result: {jira_issue_dict}; Detail: {jira_issue_info_dict}")
                return issue_detail_info(status_code, jira_issue_info_dict, jira_issue_dict, question_response_df)
            # print(question_response_df)
        except Exception as e:
            status_code = -30
            self.logger.error(f"Status Code:{status_code}; Error retrieving Issue Detail. Issue ID: {issue_id} message:{e}")
            question_response_df = pd.DataFrame()
            return issue_detail_info(status_code, [], {}, question_response_df)

    def issue_add_comment(self, issue_id, comment):
        """
        Add a comment to an issue.
        :param issue_id: Jira issue ID
        :param comment: Comment text
        :return: Status code
        """
        payload = json.dumps({"body": {"content": [{"content": [{"text": comment, "type": "text"}], "type": "paragraph"}],
                            "type": "doc", "version": 1}})
        url = f'{self.base_url}api/3/issue/{issue_id}/comment'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, json=payload)
            self.logger.info(f"Added comment to issue: {response.status_code}; Issue ID: {issue_id}; Comment: {comment}")
            return response.status_code
        except Exception as e:
            status_code = -33
            self.logger.error(f"Status Code: {status_code}; Error adding comment to issue. Issue ID: {issue_id}; Comment: {comment}; {e}")
            return status_code

    def issue_assign(self, issue_id, accountId) -> int:
        """
        Assign a Jira issue.
        :param jira_issue_id: Jira issue id
        :param accountId: Jira account id
        :return: status_code. Error returns -32
        """
        payload = json.dumps({"accountId": accountId})
        url = f'{self.base_url}api/3/issue/{issue_id}/assignee'
        try:
            response = requests.put(url, headers=self.headers, auth=self._auth, data=payload)
            self.logger.info(f"Issue assigned: {response.status_code}; Issue ID: {issue_id}; Assignee: {accountId}")
            return response.status_code
        except Exception as e:
            status_code = -34
            self.logger.error(f"Status Code: {status_code}; Error assigning issue. Issue ID: {issue_id}; Assignee: {accountId}; {e}")
            return status_code

    def issue_add_attachment(self, issue_id, file_attachment) -> int:
        """
        Adds attachment to issue.
        :param issue_id: Jira issue id
        :param file_attachment: Full path to file attachment.
        :return: status_code. Error returns -33
        """
        headers_jira_auth_upload = {
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check"
        }
        application_type = get_file_application_type(file_attachment=file_attachment)
        payload = {"file": (file_attachment, open(file_attachment, "rb"), application_type)}
        url = f'{self.base_url}api/3/issue/{issue_id}/attachments'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, files=payload)
            self.logger.info(f"Issue attachment added: {response.status_code}; Issue ID: {issue_id}; Attachment: {file_attachment}")
            return response.status_code
        except Exception as e:
            status_code = -33
            self.logger.error(f"Status Code: {status_code}; Error adding attachment to issue. Issue ID: {issue_id}; Attachment: {file_attachment}; {e}")
            return status_code

    def issue_changelog(self, issue_id, max_results=1000) -> object:
        """
        Retrieve changelog for a Jira issue.
        :param issue_id: Jira issue ID
        :param max_results: Defaults to 1000. The number of results to retrieve.
        :return: changelog_dict {status_code, changelog_entries, status_exception_comment}
        """
        changelog_dict = {'status_code': None, 'changelog_entries': None, 'status_exception_comment': None}
        url = f'{self.base_url}api/3/issue/{issue_id}/changelog?maxResults={max_results}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            changelog_entries = json.loads(response.text)
            changelog_dict.update({'status_code': response.status_code, 'changelog_entries': changelog_entries})
            self.logger.debug(f"Changelog. Issue ID: {issue_id}; Status Code: {response.status_code}")
            return changelog_dict
        except Exception as e:
            status_code = -36
            status_exception_comment = f"Error retrieving changelog. {e}"
            self.logger.error(f"Status Code: {status_code}; Issue ID: {issue_id}; {status_exception_comment}")
            changelog_dict.update(
                {"status_code": status_code, "status_exception_comment": status_exception_comment})
            return changelog_dict

    def role_add_user(self, role_id, accountId, project_id=None) -> int:
        """
        Add user to a Jira role.
        :param auth: Authentication token.
        :param role_id: Jira role id
        :param accountId: Jira account id
        :param project_id: Optional. Project id. Defaults to self.project_id.
        :return: status_code. Error returns -51
        """
        if project_id is None: project_id = self.project_id
        payload = json.dumps({"user": [accountId]})
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            self.logger.info(f"Role Add User. Role ID: {role_id}; Account ID: {accountId}; Project: {project_id}; Status Code: {response.status_code}")
            return response.status_code
        except Exception as e:
            status_code = -51
            self.logger.error(f"Status Code: {status_code}; Error adding user to role. Role ID: {role_id}; Account ID: {accountId}; Project: {project_id}; {e}")
            return status_code

    def jira_role_get_users(self, role_id, project_id=None) -> object:
        """
        Get users associated with Jira role.
        :param auth: Authentication token.
        :param role_id: Jira role id
        :param project_id: Optional. Project id. Defaults to self.project_id.
        :return: Namedtuple. role_info(status_code, jiraRole_users_df, jiraRole_dict)
        :raises Error code = -50
        """
        if project_id is None: project_id = self.project_id
        role_info = namedtuple("role_info", ["status_code", "jiraRole_users_df", "jiraRole_dict"])
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            jiraRole_dict = json.loads(response.text)
            jiraRole_users_df = pd.json_normalize(jiraRole_dict, record_path=['actors'], errors='ignore', sep='_')
            jiraRole_users_df.loc[:, "user_email"] = ""
            for ind in jiraRole_users_df.index:
                accountId = jiraRole_users_df.loc[ind, 'actorUser_accountId']
                user_info = self.get_user_info(accountId=accountId)
                jiraRole_users_df.loc[ind, "user_email"] = user_info.jira_user_email
            self.logger.debug(f"Jira Role Users. Role ID: {role_id}; Project: {project_id}; Status Code: {response.status_code}")
            return role_info(response.status_code, jiraRole_users_df, jiraRole_dict)
        except Exception as e:
            status_code = -50
            jiraRole_dict = {}
            jiraRole_users_df = pd.DataFrame()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Users. Role ID: {role_id}; Project: {project_id}; {e}")
            return role_info(status_code, jiraRole_users_df, jiraRole_dict)

    def jira_role_info(self, role_id, project_id=None) -> object:
        """
        Get role information associated with Jira role. Returns role members as a dataframe.
        :param auth:  Authentication token.
        :param role_id: Jira role id
        :return: Namedtuple. role_info(status_code, jira_role_members_df)
        """
        role_info = namedtuple("role_info", ["status_code", "jira_role_members_df"])
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            status_code = response.status_code
            # print(f"{jiraProjInfo.status_code};{jiraProjInfo.text}")
            # print(jiraRoleInfo.text)
            jira_role_json = json.loads(response.text)
            jira_role__dict = dict(response.json())
            # print(responseList.text)
            # response_df = pd.json_normalize(responseList_json, record_path=['result'], errors='ignore', sep='_', record_prefix='dossier_')
            jira_role_members_df = pd.json_normalize(jira_role_json, record_path=['actors'], errors='ignore', sep='_')
            self.logger.debug(f"Jira Role Info. Role ID: {role_id}; Project: {project_id}; Status Code: {status_code}")
            return role_info(status_code, jira_role_members_df)
        except Exception as e:
            status_code = -17
            # print(f"{jiraProjInfo.status_code};{jiraProjInfo.text}")
            jira_role_members_df = pd.dataframe()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Info. Role ID: {role_id}; Project: {project_id}; {e}")
            return role_info(status_code, jira_role_members_df)

    def response_type_ref(self, response_type) -> str:
        """
        Used for processing Jira fields.
        :param response_type: Input Jira field
        :return: response_type_name
        """
        response_type_name = {
            'ts': 'Text Short'
            , 'cs': 'Choice Selector'
            , 'cd': 'Choice Dropdown'
            , 'cl': 'Choice List'
            , 'us': 'User'
            , 'um': 'User Multiple'
            , 'at': 'Attachment'
            , 'dt': 'Date/Time'
            , 'da': 'Date'
            , 'ti': 'Time'
            , 'tl': 'Title'
            , 'cm': 'Choice Multiple'
            , 'pg': 'Paragraph'
            , 'rt': 'Rich-Text'
        }

        return response_type_name.get(response_type)

    def response_type_col_ref(self, response_type) -> str:
        """
        Gets the field type for responses.
        :param response_type: String
        :return: response_col_name
        """
        response_col_name = {
            'ts': 'textField'
            , 'cs': 'choices_x'
            , 'cd': 'choices_x'
            , 'cl': 'choices_x'
            , 'cm': 'choices_x'
            , 'us': 'users'
            , 'um': 'users'
            , 'at': 'textField'
            , 'dt': 'Date Time'
            , 'da': 'date'
            , 'ti': 'time'
            , 'tl': 'textField'
            , 'pg': 'textField'
            , 'rt': 'textField'
        }

        return response_col_name.get(response_type)

def get_file_application_type(file_attachment) -> str:
    """
    Gets file type for encoding.
    :param file_attachment: Full path to file attachment.
    :return: application_type (i.e., application/octet-stream, txt/plain'
    """
    file_extension = pathlib.Path(file_attachment).suffix
    file_extension = file_extension.strip('.')
    if file_extension in ('mmp'):
        application_type = 'application/octet-stream'
    else:
        application_type = mimetypes.guess_type(file_attachment)[0]
        if application_type is None: application_type = 'txt/plain'
    return application_type
    # Additional methods (e.g., attaching files, fetching changelogs, etc.) can be similarly refactored