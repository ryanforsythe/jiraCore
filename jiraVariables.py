import os
import keyring as kr
from dotenv import load_dotenv


class JiraVariables:
    """
    Class handling JIRA variables and configurations.

    This class manages JIRA-related variables and configurations, such as roles,
    statuses, transitions, components, priorities, issue types, and credentials.
    It loads these configurations from environment variables or keyring services
    to facilitate interaction with the JIRA API. Dictionaries are initialized to
    map human-readable identifiers to their corresponding JIRA IDs.

    :ivar base_jira_url: Base API URL of the JIRA instance loaded from the
        environment variables.
    :type base_jira_url: str or None
    :ivar log_location: Path for logging output as specified in the
        environment variables.
    :type log_location: str or None
    :ivar log_level: Log verbosity level fetched from environment variables.
    :type log_level: str or None
    :ivar jira_user_name: JIRA username fetched from a keyring service.
    :type jira_user_name: str or None
    :ivar _jira_password: JIRA password fetched securely from a keyring service.
    :type _jira_password: str or None
    :ivar default_issue_type_id: ID of the default issue type derived from the
        environment variables and initialized dictionary.
    :type default_issue_type_id: int or None
    :ivar default_priority_id: ID of the default priority derived from the
        environment variables and initialized dictionary.
    :type default_priority_id: int or None
    :ivar default_project_key: Key of the default project loaded from the
        environment variables.
    :type default_project_key: str or None
    :ivar jira_role_dict: Dictionary mapping user roles to their corresponding
        JIRA IDs.
    :type jira_role_dict: dict
    :ivar jira_status_dict: Dictionary mapping issue statuses to their
        corresponding JIRA IDs.
    :type jira_status_dict: dict
    :ivar jira_transition_dict: Dictionary mapping issue transitions to their
        corresponding JIRA IDs.
    :type jira_transition_dict: dict
    :ivar jira_components_dict: Dictionary mapping JIRA components to their
        corresponding IDs.
    :type jira_components_dict: dict
    :ivar jira_priority_dict: Dictionary mapping priority levels to their
        corresponding JIRA IDs.
    :type jira_priority_dict: dict
    :ivar jira_issue_type_dict: Dictionary mapping issue types to their
        corresponding JIRA IDs.
    :type jira_issue_type_dict: dict
    """

    def __init__(self):
        # Load environment variables
        load_dotenv()
        self.init_dicts()
        # Fetch credentials and URL from environment/keyring
        self.base_jira_url = os.getenv("JIRA_URL")
        self.log_location = os.getenv("LOG_LOCATION")
        self.log_level= os.getenv("LOG_LEVEL")
        credential_service_name = os.getenv("KEYRING_CREDENTIAL_SERVICE")
        jira_user = kr.get_credential(credential_service_name, None)
        self.jira_user_name = jira_user.username
        self._jira_password = jira_user.password
        self.default_issue_type_id = self.jira_dict_lookup("issue_type", os.getenv("DEFAULT_ISSUE_TYPE"))
        self.default_priority_id = self.jira_dict_lookup("priority", os.getenv("DEFAULT_PRIORITY"))
        self.default_project_key = os.getenv("DEFAULT_PROJECT_KEY")

    def init_dicts(self):
        """"
        Initialize dictionaries for role, status, transition, components, and priority."""
        self.jira_role_dict = {"approver": 10499}

        self.jira_status_dict = {
            "done": 10002,
            "in_progress": 10001,
            "to_do": 10000,
            "waiting_for_approval": 13001,
            "ready_to_deploy": 13002,
            "ready_for_work": 13003,
            "fail": 13004,
            "review_test": 13005,
            "waiting_for_custome": 13006,
            "approved": 13007,
            "rejected": 12001,
        }

        self.jira_transition_dict = {
            "waiting_for_approval": 111,
            "in_automation": 121,
            "ready_to_deploy": 141,
            "ready_for_work": 101,
            "fail": 131,
            "review_test": 151,
            "waiting_for_customer": 21,
            "done": 51,
            "approved": 161,
            "rejected": 171,
        }

        self.jira_components_dict = {"database": 22503}

        self.jira_priority_dict = {
            "blocker or production down": 10000,
            "highest": 1,
            "high": 2,
            "medium": 3,
            "low": 4,
            "lowest": 5,
            "none": 10100,
        }

        self.jira_issue_type_dict = {
            "subtask": 10003,
            "task": 10001,
            "story": 10004,
            "development": 10005,
            "epic": 10002}

    def jira_dict_lookup(self, dict_type: str, key: str) -> int:
        """
        Looks up a value in a dictionary corresponding to the specified type
        and key. This method supports lookup for various predefined types
        related to JIRA (e.g., roles, statuses, transitions, components,
        priorities, and issue types). The lookup is performed in a
        case-insensitive manner for the provided key.

        :param dict_type: The type of dictionary to search. Possible values are
                          "role", "status", "transition", "components",
                          "priority", and "issue_type".
        :type dict_type: str
        :param key: The key to look up in the specified dictionary. The key
                    will be normalized to lowercase for the lookup.
        :type key: str
        :return: The integer value associated with the key in the specified
                 dictionary, or None if the key is not found or the
                 dictionary type is invalid.
        :rtype: int | None
        """
        # Normalize the key
        key = key.casefold()

        # Dictionary lookup based on type
        if dict_type == "role":
            return self.jira_role_dict.get(key.lower())
        elif dict_type == "status":
            return self.jira_status_dict.get(key.lower())
        elif dict_type == "transition":
            return self.jira_transition_dict.get(key.lower())
        elif dict_type == "components":
            return self.jira_components_dict.get(key.lower())
        elif dict_type == "priority":
            return self.jira_priority_dict.get(key.lower())
        elif dict_type == "issue_type":
            return self.jira_issue_type_dict.get(key.lower())
        else:
            return None