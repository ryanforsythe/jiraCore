import requests
import json
import jmespath as jq
import pandas as pd
from requests.auth import HTTPBasicAuth
from collections import namedtuple
import mimetypes
import pathlib
import re
import sys
from loguru import logger

import jiraVariables as jvars


class JiraAPI:
    """
    Provides functionality to interact with the Jira API for various operations such as user and
    project management, issue tracking, and search functionalities.

    This class is designed to handle authentication, make REST API calls to Jira, and manage
    application-wide headers. The purpose is to abstract Jira's API calls and simplify usage for
    Jira users and projects.

    :ivar jvars: Reference to the JiraVariables instance for configuration data.
    :type jvars: JiraVariables
    :ivar base_url: The base URL for Jira API requests.
    :type base_url: str
    :ivar _auth: Authentication credentials for Jira API calls.
    :type _auth: HTTPBasicAuth
    :ivar default_issue_type_id: The default issue type identifier for Jira issues.
    :type default_issue_type_id: str
    :ivar default_priority_id: The default priority identifier for Jira issues.
    :type default_priority_id: str
    :ivar headers: Standard headers used for HTTP requests to the Jira API.
    :type headers: dict
    :ivar default_project_key: The default key of the Jira project being used.
    :type default_project_key: str
    :ivar logger: Logger instance for managing log records.
    :type logger: Logger
    :ivar project_info: Details of the Jira project.
    :type project_info: dict
    :ivar project_id: Identifier of the Jira project currently being worked on.
    :type project_id: str
    :ivar user_account_id: Account ID of the authenticated user.
    :type user_account_id: str
    """
    def __init__(self, project_key=None):
        """
        Constructor to initialize JiraAPI instance.
        :param project_key: Optional. The Jira project key. If not provided, the default project key will be used.
        """
        self.jvars = jvars.JiraVariables()
        self.init_logger()
        self.base_url = self.jvars.base_jira_url
        self._auth = None
        self.default_issue_type_id = self.jvars.default_issue_type_id
        self.default_priority_id = self.jvars.default_priority_id

        self.headers = {"Accept": "application/json", "Content-Type": "application/json"}
        self._auth = HTTPBasicAuth(self.jvars.jira_user_name, self.jvars._jira_password)
        self._set_authenticated_headers()
        self.authenticate()

        if project_key is None:
            self.default_project_key = self.jvars.default_project_key
        else: self.default_project_key = project_key
        self.project_info(self.default_project_key)


    def init_logger(self):
        LOGGER_LEVEL = self.jvars.log_level
        CONSOLE_LEVEL = 'DEBUG'
        self.logger = logger
        self.logger.add(self.jvars.log_location, rotation="30 MB", retention=5, enqueue=True, level=LOGGER_LEVEL)
        time_format = "YYYY-MM-DD HH:mm:ss"
        console_format = f"<green>{{time:{time_format}}}</green> | <level>{{level: <8}}</level> | {{name}}:{{function}}:{{line}} - {{message}}"
        self.logger.add(sink=sys.stdout,
                   level=CONSOLE_LEVEL,
                   format=console_format,
                   colorize=True,
                   )

    def _set_authenticated_headers(self):
        """
        Sets headers to authenticate the request using an experimental API.

        This private method is used internally to add authentication headers specific
        to the experimental API, enabling proper communication with the server.

        :return: None
        """
        self.headers["X-ExperimentalAPI"] = "opt-in"

    def authenticate(self):
        """
        Authenticates the user by sending a GET request to the specified API endpoint
        using the base URL and provided credentials. This method captures the response,
        logs the status and user information on successful authentication, and updates
        the ``user_account_id`` attribute. It handles exceptions, logs errors, and
        returns appropriate status codes on failure.

        :raises requests.exceptions.HTTPError: If an HTTP exception occurs during the
            request.
        :raises Exception: For any other unexpected failures during the execution.

        :return: A tuple containing the status code (int) and an error message (str)
            on failure, or the status code (int) alone on success.
        :rtype: int or tuple
        """
        url = f'{self.base_url}api/3/myself'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            self.logger.debug(f"Authentication: {response.status_code}; {response.text}")
            user_info = json.loads(response.text)
            self.user_account_id = user_info.get("accountId")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -14.1
            self.logger.error(f"Status Code: {status_code}; Authentication failed: {errh}; {response.text}")
            return status_code, str(errh)
        except Exception as e:
            status_code = -14
            self.logger.error(f"Status Code: {status_code}; Authentication failed: {e}")
            return status_code
        
    def project_info(self, project_key):
        """
        Retrieves project information from a given project key by calling a REST API endpoint.
        It processes the response to extract necessary project details, such as project ID,
        logs critical debug and error information, and handles exceptions.

        :param project_key: Unique identifier of the project for which information is being retrieved.
        :type project_key: str
        :return: The status code of the HTTP request. For exceptions, it returns a custom negative
            status code.
        :rtype: int or tuple(int, str)
        :raises requests.exceptions.HTTPError: Raised when the HTTP request fails due to a
            non-success status code.
        :raises Exception: Raised for all other unexpected errors during the request or processing.
        """
        url = f'{self.base_url}api/3/project/{project_key}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            self.project_info = json.loads(response.text)
            self.project_id = jq.search('id',self.project_info)
            self.logger.debug(f"Project Key: {project_key}; Status Code: {response.status_code}; Result: {self.project_info}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -16.1
            self.logger.error(f"Status Code: {status_code}; Error retrieving project info. Project Key: {project_key}; {errh}; {response.text}")
            return status_code, str(errh)
        except Exception as e:
            self.project_id = '-1'
            status_code = -16
            self.logger.error(f"Status Code: {status_code}; Error retrieving project info. Project Key: {project_key}; {e}")
            return status_code

    def user_info(self, account_id):
        """
        Retrieve information about a user from Jira using their account ID.

        This method interacts with the Jira REST API to fetch user information based on the provided
        account ID. It returns a named tuple containing the response status code, user data, whether
        or not the user was found, user email address, display name, and activity status. If the
        specified user is not found or an error occurs during the API request, appropriate responses
        are logged and returned to the caller.

        :param account_id: The Jira account ID of the user whose details are to be fetched.
        :type account_id: str

        :returns: On success, a named tuple containing:
                  - status_code (int): HTTP response code from the Jira API.
                  - jira_user_dict (dict): Dictionary containing user information.
                  - jira_user_found (int): Indicator whether the user was found (1 if found, 0 otherwise).
                  - jira_user_email (str): Email address of the user.
                  - jira_user_display_name (str): Display name of the user.
                  - jira_user_active (bool): Active status of the user.
                  On failure, varies as:
                  - For HTTP request errors, returns a tuple (status_code: float, error_message: str).
                  - For other exceptions, returns the named tuple with status_code -17 and appropriate default
                    values.
        :rtype: Union[namedtuple, Tuple[float, str]]

        :raises requests.exceptions.HTTPError: If the HTTP request to Jira fails due to response errors.
        :raises Exception: If any other exception occurs during the execution.
        """
        user_info = namedtuple("user_info", ["status_code", "jira_user_dict", "jira_user_found", "jira_user_email",
                                             "jira_user_display_name", "jira_user_active"])
        query = {'accountId': account_id}
        url = f'{self.base_url}api/3/user'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth, params=query)
            response.raise_for_status()
            user_data = json.loads(response.text)
            if user_data:
                self.logger.debug(f"Account ID: {account_id}; Status Code: {response.status_code}; Result: {user_data}")
                return user_info(
                    response.status_code, user_data, 1,
                    user_data.get("emailAddress"), user_data.get("displayName"), user_data.get("active")
                )
            else:
                self.logger.warning(f"User not found. Account ID: {account_id}")
                return user_info(response.status_code, {}, 0, "", "", False)
        except requests.exceptions.HTTPError as errh:
            status_code = -17.1
            self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Account ID: {account_id}; {errh}; {response.text}")
            return status_code, str(errh)
        except Exception as e:
            status_code = -17
            self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Account ID: {account_id}; {e}")
            return user_info(status_code, {}, -1, "", "", False)

    def user_by_email(self, email_address):
        """
        Retrieves user information based on the given email address by querying the Jira API. The system will validate
        the email address format before sending the data request. If the email address format is invalid, the method
        immediately logs the error and returns a structured tuple with a specific error code. If the request to the
        API is successful, the method returns the first user matching the provided email address. Logging is utilized
        throughout the process to provide detailed runtime diagnostics.

        :param email_address: An email address string to query the Jira API for user information.
        :type email_address: str
        :return: A named tuple containing:
            -status_code
            -jira_user_dict: a dictionary of user information (or an empty dictionary if not found)
            -jira_user_found: flag indicating if the user was found (1 for found, 0 for not found, -1 for errors).
        :rtype: tuple
        """
        user_info = namedtuple("user_info", ["status_code", "jira_user_dict", "jira_user_found"])

        pattern = re.compile(r'^[a-z0-9]+[\._]?[a-z0-9]+[@]\w+[.]\w+$', re.IGNORECASE)
        if pattern.match(email_address) is None:
            status_code = -18.1
            jira_user_found = -1
            jira_user_dict = []
            self.logger.warning(f"Status Code: {status_code}; Invalid email address. Email Address: {email_address}")
            return user_info(status_code, {}, 0)
        else:
            try:
                url = f'{self.base_url}api/3/user/search/?query={email_address}'
                response = requests.get(url, headers=self.headers, auth=self._auth)
                response.raise_for_status()
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
            except requests.exceptions.HTTPError as errh:
                status_code = -18.1
                self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Email Address: {email_address}; {errh}; {response.text}")
                return status_code, str(errh)
            except Exception as e:
                status_code = -18
                self.logger.error(f"Status Code: {status_code}; Error retrieving user info. Email Address: {email_address}; {e}")
                return user_info(status_code, {}, -1)

    def search_issues(self, search_query, as_dataframe=False):
        """
        Executes a search query against the Jira API to retrieve issues based on the provided JQL.

        The function returns the issues either in raw format or as a DataFrame based on the input flag.
        HTTP errors and general exceptions are handled, with relevant error messages logged.
        The returned data is encapsulated into a named tuple containing the response details.

        Parameters:
            search_query (str): The JQL (Jira Query Language) expression used to retrieve issues from Jira.
            as_dataframe (bool): A flag indicating whether the response should be returned as a pandas DataFrame.
                Defaults to False.

        Returns:
            collections.namedtuple: A named tuple containing the following elements:
                - `status_code` (int): The HTTP status code of the API response.
                - `jira_issues` (list | pandas.DataFrame): The retrieved issues, returned as raw JSON (list) or
                  as a pandas DataFrame depending on the value of `as_dataframe`.

        Raises:
            requests.exceptions.HTTPError: If the API request fails with an HTTP error.
            Exception: For general unexpected errors.
        """

        IssueSearchResult = namedtuple("issue_search_results", ["status_code", "jira_issues"])
        url = f'{self.base_url}api/3/search?jql={search_query}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            result_dict = json.loads(response.text)
            self.logger.debug(f"Search query: {search_query}; Result: {result_dict}")
            if as_dataframe:
                jira_issues = pd.json_normalize(result_dict, record_path=['issues'], errors='ignore', sep='_')
            else:
                jira_issues = result_dict
            return IssueSearchResult(response.status_code, jira_issues)
        except requests.exceptions.HTTPError as errh:
            status_code = -21.1
            self.logger.error(f"Status Code: {status_code}; Error searching for issues. Query: {search_query}; {errh}; {response.text}")
            return status_code, str(errh)
        except Exception as e:
            status_code = -21
            self.logger.error(f"Status Code: {status_code}; Error searching for issues. Query: {search_query}; {e}")
            return IssueSearchResult(status_code, [])

    def issue_create(self, summary, project_id=None, issue_type_id=None, description=None, assignee=None, priority=None):
        """
        Create a Jira issue.

        This function interacts with the Jira API to create an issue in a specified project.

        :param project_id: The ID of the project where the issue will be created.
        :type project_id: str
        :param summary: The summary (short description) of the issue.
        :type summary: str
        :param issue_type_id: The type of issue to create (default: 12412).
        :type issue_type_id: int, optional
        :param description: A longer description of the issue, optional.
        :type description: str, optional
        :param assignee: The account ID of the person to assign the issue to, optional.
        :type assignee: str, optional
        :param priority: The priority of the issue (default: 10100), optional.
        :type priority: int, optional
        :return: A namedtuple representing the created issue with the fields:
                 - `status_code` (int): The HTTP status code of the response.
                 - `issue_info` (dict): Additional information about the created issue.
                 - `id` (str): The ID of the newly created issue.
                 - `key` (str): The Jira key of the created issue (e.g., "PROJECT-123").
                 - `issue_url` (str): The URL of the created issue in Jira.
        :rtype: namedtuple("issue", ["status_code", "issue_info", "id", "key", "issue_url"])
        """
        IssueInfo = namedtuple("issue", ["status_code", "issue_info","id", "key", "issue_url"])
        if project_id is None: project_id = self.project_id
        if issue_type_id is None: issue_type_id = self.default_issue_type_id
        if description is None: description = ""
        if assignee is None: assignee = self.user_account_id
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
                #"priority": {"id": priority},
                "project": {"id": project_id},
                "summary": summary,
            }
        }
        payload = json.dumps(input_json)
        url = f'{self.base_url}api/3/issue'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            issue_info = json.loads(response.text)
            logger.info(f"Issue created: {response.status_code}; Project: {project_id}; Summary: {summary}; Issue Type: {issue_type_id}; Priority: {priority}; Assignee: {assignee}; ")
            return IssueInfo(response.status_code, issue_info, issue_info.get("id"), issue_info.get("key"), issue_info.get("self"))
        except requests.exceptions.HTTPError as errh:
            status_code = -35.1
            logger.error(f"Status Code: {status_code}; Error creating issue; Project: {project_id}; Summary: {summary}; Issue Type: {issue_type_id}; Priority: {priority}; Assignee: {assignee}; {errh}; {response.text}")
            return IssueInfo(response.status_code, [], -1 , "", "")
        except Exception as e:
            status_code = -35
            logger.error(f"Status Code: {status_code}; Error creating issue; Project: {project_id}; Summary: {summary}; Issue Type: {issue_type_id}; Priority: {priority}; Assignee: {assignee}; {e}")
            return IssueInfo(response.status_code, [], -1 , "", "")

    def issue_transition(self, issue_id, transition_id):
        """
        Transitions a specified issue in a project management system to a new state using
        a provided transition ID. This involves making a POST request to the system's API
        while handling potential exceptions and logging outcomes.

        :param issue_id: Identifier for the issue to be transitioned.
        :type issue_id: str
        :param transition_id: Identifier for the transition to apply to the issue.
        :type transition_id: str
        :return: Status code of the API response, or custom error status codes for
                 exceptional conditions (-37 or -37.1).

        :rtype: int
        """
        payload = json.dumps({"transition": {"id": transition_id}})
        url = f'{self.base_url}api/3/issue/{issue_id}/transitions'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            self.logger.info(f"Issue transitioned: {response.status_code}; Issue ID: {issue_id}; Transition ID: {transition_id}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -37.1
            self.logger.error(
                f"Status Code: {status_code}; Error transitioning issue. Issue ID: {issue_id}; Transition ID: {transition_id}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -37
            self.logger.error(f"Status Code: {status_code}; Error transitioning issue. Issue ID: {issue_id}; Transition ID: {transition_id}; {e}")
            return status_code

    def issue_field_update(self, issue_id, field_update_dict) -> int:
        """
        Updates the fields of a specific issue in the issue tracking system by sending
        a PUT request to the API endpoint. This method allows updating multiple fields
        at once by providing a dictionary of field names and their corresponding new
        values.

        If the update operation is successful, it logs the changes and returns the
        HTTP response status code. In case of an HTTP error or other exceptions, it logs
        the appropriate error details and returns specific negative status codes to
        indicate failure.

        :param issue_id: The unique identifier of the issue to be updated.
        :type issue_id: str
        :param field_update_dict: Dictionary containing the fields to update
            and their new values. The keys in the dictionary represent the field
            names, and the values represent the new data for those fields.
            Example: field_update_data = {"customfield_14064": [{"accountId": "712020:d4f13f91-ed7f-493d-8fef-4029b44eb7cb"},{"accountId": "5a4e734573cadb08a03ed16c"}]}
        :type field_update_dict: dict
        :return: The HTTP status code of the update request if successful, or a
            specific negative status code indicating an error (-35 for general
            exceptions, -35.1 for HTTP errors).
        :rtype: int
        """
        payload = json.dumps({"fields": field_update_dict})
        url = f'{self.base_url}api/3/issue/{issue_id}'
        try:
            response = requests.put(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            self.logger.info(f"Issue field updated: {response.status_code}; Issue ID: {issue_id}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -35.1
            self.logger.error(f"Status Code: {status_code}; Error updating issue. Issue ID: {issue_id}; Field Data: {field_update_dict}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -35
            self.logger.error(f"Status Code: {status_code}; Error updating issue. Issue ID: {issue_id}; Field Data: {field_update_dict}; {e}")
            return status_code

    def issue_detail(self, issue_id, include_forms=False):
        """
        Retrieves the details of a Jira issue, including various metadata and optionally form responses. It fetches
        issue details such as reporter information, assignee information, status, and custom fields. If
        `include_forms` is set to `True`, it extracts additional data from Proforma forms present in the issue and
        merges questions and responses into a pandas DataFrame.

        This method makes an authenticated HTTP request to the Jira API to retrieve the specified issue's details.
        It processes the response to parse issue metadata and optional form-related data.

        :param issue_id: The unique identifier of the Jira issue
        :param include_forms: If set to True, retrieves and processes forms associated with the issue.
        :return: A named tuple containing the following elements:
            - `status_code` (int): The HTTP status code of the request.
            - `jira_issue_info_dict` (dict): Metadata and details about the Jira issue.
            - `jira_issue_dict` (dict): Raw API response data from Jira.
            - `question_response_df` (pandas.DataFrame): A DataFrame containing Proforma form responses, if `include_forms` is True.
        :rtype: namedtuple
        :raises: Handles HTTP error or generic exceptions during API requests or data processing.
        """
        issue_detail_info = namedtuple("issue_detail_info", ["status_code", "jira_issue_info_dict", "jira_issue_dict",
                                                             "question_response_df"])
        url = f'{self.base_url}api/3/issue/{issue_id}?properties=*all'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
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
        except requests.exceptions.HTTPError as errh:
            status_code = -30.1
            self.logger.error(f"Status Code:{status_code}; Error retrieving Issue Detail. Issue ID: {issue_id} message:{errh}; {response.text}")
            question_response_df = pd.DataFrame()
            return issue_detail_info(status_code, [], {}, question_response_df)
        except Exception as e:
            status_code = -30
            self.logger.error(f"Status Code:{status_code}; Error retrieving Issue Detail. Issue ID: {issue_id} message:{e}")
            question_response_df = pd.DataFrame()
            return issue_detail_info(status_code, [], {}, question_response_df)

    def issue_add_comment(self, issue_id, comment):
        """
        Adds a comment to a specified issue in the issue tracking system.

        This method sends a POST request to the specified issue endpoint with the
        given comment payload. The content of the comment is added to the issue
        identified by the `issue_id`. The method verifies the response, logs the success
        or failure event, and returns the status code based on the operation outcome.

        :param issue_id: The identifier of the issue to which the comment will be added
                        (str).
        :param comment: The text of the comment to be added to the issue (str).
        :return: The HTTP response status code of the action. Returns -33.1 in case of
                 an HTTP error and -33 in case of a general exception (int).
        """
        payload = json.dumps({"body": {"content": [{"content": [{"text": comment, "type": "text"}], "type": "paragraph"}],
                            "type": "doc", "version": 1}})
        url = f'{self.base_url}api/3/issue/{issue_id}/comment'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            self.logger.info(f"Added comment to issue: {response.status_code}; Issue ID: {issue_id}; Comment: {comment}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -33.1
            self.logger.error(f"Status Code: {status_code}; Error adding comment to issue. Issue ID: {issue_id}; Comment: {comment}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -33
            self.logger.error(f"Status Code: {status_code}; Error adding comment to issue. Issue ID: {issue_id}; Comment: {comment}; {e}")
            return status_code

    def issue_assign(self, issue_id, accountId) -> int:
        """
        Assigns an issue to a specified user in the system using the provided issue ID and account ID.
        This method sends a PUT request to the respective API endpoint to assign the issue. It logs
        the outcome and returns the HTTP status code or a specific error code in case of a failure.

        :param issue_id: The unique identifier of the issue to be assigned.
        :type issue_id: str
        :param accountId: The account ID of the user to whom the issue will be assigned.
        :type accountId: str
        :return: HTTP status code if assignment is successful, -34 for a general error, or -34.1
                 for HTTP request-related errors.
        :rtype: int
        """
        payload = json.dumps({"accountId": accountId})
        url = f'{self.base_url}api/3/issue/{issue_id}/assignee'
        try:
            response = requests.put(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            self.logger.info(f"Issue assigned: {response.status_code}; Issue ID: {issue_id}; Assignee: {accountId}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -34.1
            self.logger.error(f"Status Code: {status_code}; Error assigning issue. Issue ID: {issue_id}; Assignee: {accountId}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -34
            self.logger.error(f"Status Code: {status_code}; Error assigning issue. Issue ID: {issue_id}; Assignee: {accountId}; {e}")
            return status_code

    def issue_add_attachment(self, issue_id, file_attachment) -> int:
        """
        Adds an attachment to a JIRA issue. This method uploads a file attachment to the specified
        JIRA issue using the JIRA REST API. The file is identified by its path, and JIRA-specific
        headers are configured to handle the attachment upload correctly.

        This method attempts to post the given file as an attachment to the JIRA issue identified
        by its ID. The file's application type is determined internally using a helper function.

        :param str issue_id: The unique identifier of the issue to which the attachment will be added.
        :param str file_attachment: The path to the file that needs to be attached.
        :return: The HTTP status code of the response for successful upload, negative values for errors.
        :rtype: int
        """
        headers_jira_auth_upload = {
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check"
        }
        application_type = get_file_application_type(file_attachment=file_attachment)
        payload = {"file": (file_attachment, open(file_attachment, "rb"), application_type)}
        url = f'{self.base_url}api/3/issue/{issue_id}/attachments'
        try:
            response = requests.post(url, headers=headers_jira_auth_upload, auth=self._auth, files=payload)
            response.raise_for_status()
            self.logger.info(f"Issue attachment added: {response.status_code}; Issue ID: {issue_id}; Attachment: {file_attachment}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -33.1
            self.logger.error(f"Status Code: {status_code}; Error adding attachment to issue. Issue ID: {issue_id}; Attachment: {file_attachment}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -33
            self.logger.error(f"Status Code: {status_code}; Error adding attachment to issue. Issue ID: {issue_id}; Attachment: {file_attachment}; {e}")
            return status_code

    def issue_changelog(self, issue_id, max_results=1000) -> object:
        """
        Fetches the changelog entries for a specific issue from the Jira API. The method sends
        a GET request to the Jira API endpoint for issue changelogs, using the provided issue ID
        and an optional maximum result limit. Returns a dictionary that contains the HTTP status
        code, retrieved changelog entries, or details about any exception encountered during the request.

        :param issue_id: The identifier of the issue whose changelog is to be retrieved.
        :type issue_id: str
        :param max_results: The maximum number of changelog entries to retrieve. Defaults to 1000.
        :type max_results: int, optional
        :return: A dictionary containing:
            - status_code (float): The HTTP status code of the response or a custom error code
              if an exception occurs.
            - changelog_entries (object): The JSON parsed changelog entries retrieved from the
              API, or None if an error occurs.
            - status_exception_comment (str): A message describing any exception encountered,
              or None if the request is successful.
        :rtype: dict
        """
        changelog_dict = {'status_code': None, 'changelog_entries': None, 'status_exception_comment': None}
        url = f'{self.base_url}api/3/issue/{issue_id}/changelog?maxResults={max_results}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            changelog_entries = json.loads(response.text)
            changelog_dict.update({'status_code': response.status_code, 'changelog_entries': changelog_entries})
            self.logger.debug(f"Changelog. Issue ID: {issue_id}; Status Code: {response.status_code}")
            return changelog_dict
        except requests.exceptions.HTTPError as errh:
            status_code = -36.1
            status_exception_comment = f"Error retrieving changelog. {errh}; {response.text}"
            self.logger.error(f"Status Code: {status_code}; Issue ID: {issue_id}; {status_exception_comment}")
            changelog_dict.update(
                {"status_code": status_code, "status_exception_comment": status_exception_comment})
            return changelog_dict
        except Exception as e:
            status_code = -36
            status_exception_comment = f"Error retrieving changelog. {e}"
            self.logger.error(f"Status Code: {status_code}; Issue ID: {issue_id}; {status_exception_comment}")
            changelog_dict.update(
                {"status_code": status_code, "status_exception_comment": status_exception_comment})
            return changelog_dict

    def issue_types_user(self, as_dataframe=False) -> object:
        """
        Retrieves the issue types available for the user from the API and returns them
        in the specified format. The retrieval is done via a GET request to the
        designated endpoint. The result can be returned either as a raw dictionary or
        formatted as a DataFrame. Any errors during the process are handled and logged,
        with status codes indicating success or failure.

        :param as_dataframe: Determines whether the response will be converted into
            a pandas DataFrame or returned as a dictionary. Defaults to False.
            If True, the response will be formatted as a pandas DataFrame. If False,
            a raw dictionary is returned.
        :type as_dataframe: bool
        :return: A named tuple containing the status code and the retrieved issue types.
            If an error occurs during the retrieval process, the status code in the
            returned tuple will indicate the nature of the error, and the issue types
            part of the tuple will be empty.
        :rtype: namedtuple
        """
        IssueTypes = namedtuple("issue_types", ["status_code", "issue_types"])
        url = f'{self.base_url}api/3/issuetype'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            issue_types_dict = json.loads(response.text)
            self.logger.debug(f"User Issue Types. Status Code: {response.status_code}")
            if as_dataframe:
                issue_types = pd.json_normalize(issue_types_dict, errors='ignore', sep='_')
            else:
                issue_types = issue_types_dict
            return IssueTypes(response.status_code, issue_types)
        except requests.exceptions.HTTPError as errh:
            status_code = -61.1
            logger.error(f"Status Code: {status_code}; Error retrieving user issue types; {errh}; {response.text}")
            return IssueTypes(status_code, [])
        except Exception as e:
            status_code = -61
            logger.error(f"Status Code: {status_code}; Error retrieving user issue types; {e}")
            return IssueTypes(status_code, [])

    def issue_statuses(self, projectLevel=True, as_dataframe=False) -> object:
        """
        Retrieves issue statuses for a project or globally based on the project-level flag.

        The method retrieves issue statuses data by making an HTTP GET request to the
        appropriate endpoint. If the `projectLevel` parameter is set to True, the request
        is scoped to the specific project, otherwise it retrieves the global issue statuses.
        The returned data can be optionally converted into a pandas DataFrame if the
        `as_dataframe` parameter is set to True. The result, including the HTTP status
        code and issue statuses data, is encapsulated in a named tuple `IssueStatuses`.

        :param projectLevel: A boolean indicating if the request should be scoped to the
            specific project (True) or retrieve global issue statuses (False).
        :param as_dataframe: A boolean indicating if the issue statuses data should be
            returned as a pandas DataFrame (True) or as a dictionary (False).
        :return: A named tuple `IssueStatuses`:
            -status_code
            -issue_statuses: either as a dictionary or a pandas DataFrame.
        :rtype: namedtuple
        """
        IssueStatuses = namedtuple("issue_statuses", ["status_code", "issue_statuses"])
        if projectLevel:
            url = f'{self.base_url}api/3/statuses/search?projectId={self.project_id}'
        else:
            url = f'{self.base_url}api/3/statuses/search'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            issue_statuses_dict = json.loads(response.text)
            self.logger.debug(f"Issue Statuses. Status Code: {response.status_code}")
            if as_dataframe:
                issue_statuses = pd.json_normalize(issue_statuses_dict, errors='ignore', sep='_')
            else:
                issue_statuses = issue_statuses_dict
            return IssueStatuses(response.status_code, issue_statuses)
        except requests.exceptions.HTTPError as errh:
            status_code = -71.1
            logger.error(f"Status Code: {status_code}; Error retrieving user issue statuses; {errh}; {response.text}")
            return IssueStatuses(status_code, [])
        except Exception as e:
            status_code = -71
            logger.error(f"Status Code: {status_code}; Error retrieving user issue statuses; {e}")
            return IssueStatuses(status_code, [])

    """Experimental as of 03/14/2025
    def project_issue_types(self, project_id=None, as_dataframe=False) -> object:

        IssueTypes = namedtuple("issue_types", ["status_code", "issue_types"])
        if project_id is None: project_id = self.project_id
        #url = f'{self.base_url}api/3/issuetype/project'
        url = f'{self.base_url}api/3/issuetype'
        #query_json = {"projectId": project_id }
        #query = json.dumps(query_json)
        query = {'projectId': '{10000}'}
        try:
            #response = requests.get(url, headers=self.headers, auth=self._auth, params=query)
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            issue_types_dict = json.loads(response.text)
            self.logger.debug(f"Project Issue Types. Issue ID: {project_id}; Status Code: {response.status_code}")
            if as_dataframe:
                jira_issues = pd.json_normalize(issue_types_dict, record_path=['issues'], errors='ignore', sep='_')
            else:
                issue_types = issue_types_dict
            return IssueTypes(response.status_code, issue_types)
        except requests.exceptions.HTTPError as errh:
            status_code = -36
            logger.error(f"Status Code: {status_code}; Error retrieving project issue types; Project: {project_id}; {errh}; {response.text}")
            return IssueTypes(status_code, [])
        except Exception as e:
            status_code = -36
            logger.error(f"Status Code: {status_code}; Error retrieving project issue types; Project: {project_id}; {e}")
            return IssueTypes(status_code, [])
    """

    def role_add_user(self, role_id, accountId, project_id=None) -> int:
        """
        Add a user to a specified role for a given project in the system. This method sends a POST
        request to the appropriate API endpoint with the required payload. The method will log
        relevant information and errors during the execution, returning the HTTP response status
        code or an error-specific code in case of failure.

        :param role_id: The ID of the role to which the user will be added.
        :type role_id: int
        :param accountId: The ID of the user account to be added to the role.
        :type accountId: str
        :param project_id: The ID of the project associated with the role. Defaults to the object's
            `project_id` if not specified.
        :type project_id: Optional[int]
        :return: The HTTP status code resulting from the API call. In case of errors, returns -51 for
            general exceptions or -51.1 for HTTP errors.
        :rtype: int
        """
        if project_id is None: project_id = self.project_id
        payload = json.dumps({"user": [accountId]})
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.post(url, headers=self.headers, auth=self._auth, data=payload)
            response.raise_for_status()
            self.logger.info(f"Role Add User. Role ID: {role_id}; Account ID: {accountId}; Project: {project_id}; Status Code: {response.status_code}")
            return response.status_code
        except requests.exceptions.HTTPError as errh:
            status_code = -51.1
            self.logger.error(f"Status Code: {status_code}; Error adding user to role. Role ID: {role_id}; Account ID: {accountId}; Project: {project_id}; {errh}; {response.text}")
            return status_code
        except Exception as e:
            status_code = -51
            self.logger.error(f"Status Code: {status_code}; Error adding user to role. Role ID: {role_id}; Account ID: {accountId}; Project: {project_id}; {e}")
            return status_code

    def role_get_users(self, role_id, project_id=None) -> object:
        """
        Retrieve the users associated with a specified Jira role for a given project.

        This method interacts with the Jira API to fetch details of users assigned to a specific
        role within a project. The fetched data includes detailed information about the
        users' accounts and builds a DataFrame to organize the data. If the project ID
        is not explicitly provided, the method defaults to the project's ID already
        associated with the instance of the object.

        :param role_id: The unique identifier of the Jira role.
        :type role_id: str
        :param project_id: The unique identifier of the project, defaults to the instance's project ID.
        :type project_id: str, optional
        :return: A named tuple containing:
            - status_code (int): The HTTP status code of the Jira API request.
            - jiraRole_users_df (pandas.DataFrame): A DataFrame containing user details
              associated with the role in the project.
            - jiraRole_dict (dict): Raw dictionary data retrieved from the Jira API for the role.
        :rtype: object
        """
        if project_id is None: project_id = self.project_id
        role_info = namedtuple("role_info", ["status_code", "jiraRole_users_df", "jiraRole_dict"])
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            jiraRole_dict = json.loads(response.text)
            jiraRole_users_df = pd.json_normalize(jiraRole_dict, record_path=['actors'], errors='ignore', sep='_')
            jiraRole_users_df.loc[:, "user_email"] = ""
            for ind in jiraRole_users_df.index:
                accountId = jiraRole_users_df.loc[ind, 'actorUser_accountId']
                user_info = self.get_user_info(accountId=accountId)
                jiraRole_users_df.loc[ind, "user_email"] = user_info.jira_user_email
            self.logger.debug(f"Jira Role Users. Role ID: {role_id}; Project: {project_id}; Status Code: {response.status_code}")
            return role_info(response.status_code, jiraRole_users_df, jiraRole_dict)
        except requests.exceptions.HTTPError as errh:
            status_code = -50.1
            jiraRole_dict = {}
            jiraRole_users_df = pd.DataFrame()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Users. Role ID: {role_id}; Project: {project_id}; {errh}; {response.text}")
            return role_info(status_code, jiraRole_users_df, jiraRole_dict)
        except Exception as e:
            status_code = -50
            jiraRole_dict = {}
            jiraRole_users_df = pd.DataFrame()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Users. Role ID: {role_id}; Project: {project_id}; {e}")
            return role_info(status_code, jiraRole_users_df, jiraRole_dict)

    def role_info(self, role_id, project_id=None) -> object:
        """
        Retrieves information about a specific Jira role in a given project. This includes details about
        role members and associated metadata fetched from the Jira API. The information returned is
        organized as a namedtuple containing the HTTP status code and a pandas DataFrame of role members.

        :param role_id: The unique identifier of the Jira role.
        :type role_id: int
        :param project_id: The unique identifier of the Jira project. If not provided, it defaults to None.
        :type project_id: Optional[int]
        :return: Named tuple:
            -status_code: the HTTP status code
            -jira_role_members_df: a pandas DataFrame with Jira role members.
        :rtype: namedtuple
        """
        role_info = namedtuple("role_info", ["status_code", "jira_role_members_df"])
        url = f'{self.base_url}api/3/project/{project_id}/role/{role_id}'
        try:
            response = requests.get(url, headers=self.headers, auth=self._auth)
            response.raise_for_status()
            status_code = response.status_code
            self.logger.debug(f"Role Info: {response.status_code};{response.text}")
            jira_role_json = json.loads(response.text)
            jira_role__dict = dict(response.json())
            jira_role_members_df = pd.json_normalize(jira_role_json, record_path=['actors'], errors='ignore', sep='_')
            self.logger.debug(f"Jira Role Info. Role ID: {role_id}; Project: {project_id}; Status Code: {status_code}")
            return role_info(status_code, jira_role_members_df)
        except requests.exceptions.HTTPError as errh:
            status_code = -17.1
            jira_role_members_df = pd.dataframe()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Info. Role ID: {role_id}; Project: {project_id}; {errh}; {response.text}")
            return role_info(status_code, jira_role_members_df)
        except Exception as e:
            status_code = -17
            jira_role_members_df = pd.dataframe()
            self.logger.error(f"Status Code: {status_code}; Error retrieving Jira Role Info. Role ID: {role_id}; Project: {project_id}; {e}")
            return role_info(status_code, jira_role_members_df)

    def response_type_ref(self, response_type) -> str:
        """
        Maps a response type code to its corresponding human-readable name.

        This function takes a response type code and returns the corresponding
        string representation of the human-readable name. It uses a predefined
        mapping to perform this transformation. If the provided response type
        does not exist in the mapping, it returns `None`.

        :param response_type: The code representing the type of response to be mapped.
        :type response_type: str
        :return: The human-readable name associated with the response type code,
            or `None` if the code is not found.
        :rtype: str
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
        Maps a given response type to its corresponding column reference name.

        This function takes in a response type key (as a string) and returns the
        mapped column reference name corresponding to the type. The mapping is
        defined internally within the function through a dictionary. If the
        provided response type is not found in the dictionary, the function
        returns ``None``.

        :param response_type: A string representing the type of response to be
            mapped to a column name.
        :return: The column name corresponding to the given response type. If
            the response type is not found, returns ``None``.
        :rtype: str or None
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
    Determine the MIME type (application type) of a file attachment based on its extension.

    This function evaluates the file extension to correctly classify its application type.
    If the file extension is `.mmp`, it is categorized as `application/octet-stream`.
    For other extensions, the function attempts to deduce the MIME type using the
    `mimetypes.guess_type` library. If no type is found, it defaults to `text/plain`.

    :param file_attachment: The file name or path representing the file attachment whose MIME
        type needs to be determined.
    :type file_attachment: str
    :return: The MIME type of the given file attachment.
    :rtype: str

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

def dict_as_key_value(input_dict, key_as_variable=False, as_json=False):
    """
    Converts a list of dictionaries into a key-value pair dictionary, where keys are formatted
    based on the attribute `name` and values are derived from `id`. Provides the option to
    format keys as valid variables and to return the dictionary as a JSON-formatted string.

    :param input_dict: A list of dictionaries where each dictionary must include the attributes
        `name` and `id`. Each dictionary in the list is converted and aggregated into the resulting
        key-value pair dictionary.
    :type input_dict: list[dict]

    :param key_as_variable: A boolean flag indicating whether the keys should be formatted
        as valid variable names. If set to True, the keys will be formatted as lowercase with
        spaces replaced by underscores.
    :type key_as_variable: bool, optional

    :param as_json: A boolean flag indicating whether to return the resulting dictionary
        as a JSON-formatted string or as a Python dictionary.
    :type as_json: bool, optional

    :return: The resultant dictionary containing key-value pairs derived from the input list of
        dictionaries, formatted as requested. If `as_json` is True, the result is returned as a
        JSON-formatted string.
    :rtype: Union[dict, str]
    """

    def format_key(key):
        """Helper function to format the key as lowercase with underscores for spaces."""
        return key.lower().replace(" ", "_") if key_as_variable else key

    key_value_dict = {
        format_key(val["name"]): int(val["id"]) if str(val["id"]).isdigit() else val["id"]
        for val in input_dict
    }

    if as_json:
        import json
        return json.dumps(key_value_dict, indent=4)
    else:
        return key_value_dict

if __name__ == "__main__":
    jira = JiraAPI()
    input_variable = 'This is a test issue.'
    response = jira.issue_add_comment(issue_id=10004,comment='test comment')
    print(response)
    #print(f"id: {response.id}; key: {response.key}; info:{response.issue_info}; url: {response.issue_url}")
