import os
import keyring as kr
from dotenv import load_dotenv


class JiraVariables:
    """
    A class to encapsulate Jira-related dictionaries and environment configurations.
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
    # Define dictionaries
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
        Lookup ID's for roles, statuses, transitions, components, and priorities.

        :param dict_type: Options are role; status; transition; components; priority
        :param key: The key to look up in the specified dictionary
        :return: ID corresponding to the key, or None if not found
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