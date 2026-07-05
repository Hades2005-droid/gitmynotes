"""
Asana API client wrapper with authentication, rate limiting, and retry logic.
Provides simplified CRUD operations for portfolios, projects, tasks, and custom fields.
"""

import requests
import time
from typing import Dict, List, Optional, Any
from datetime import datetime


class AsanaClient:
    """
    Wrapper around Asana REST API.
    Handles authentication, retries, and common operations.
    """

    BASE_URL = "https://app.asana.com/api/1.0"
    DEFAULT_RETRY_COUNT = 3
    DEFAULT_RETRY_DELAY = 1.0  # seconds

    def __init__(
        self,
        api_token: str,
        workspace_id: str,
        retry_count: int = DEFAULT_RETRY_COUNT,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """
        Initialize Asana API client.

        Args:
            api_token: Asana Personal Access Token
            workspace_id: Workspace GID
            retry_count: Number of retries on failure
            retry_delay: Base delay in seconds between retries
        """
        self.api_token = api_token
        self.workspace_id = workspace_id
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with authentication headers."""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "User-Agent": "NWW-Asana-Connector/0.1.0",
        })
        return session

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make an API request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            data: Request body data
            params: Query parameters

        Returns:
            Response JSON as dict

        Raises:
            Exception: If all retries exhausted
        """
        url = f"{self.BASE_URL}{endpoint}"
        attempt = 0

        while attempt < self.retry_count:
            try:
                if method == "GET":
                    response = self.session.get(url, params=params)
                elif method == "POST":
                    response = self.session.post(url, json={"data": data}, params=params)
                elif method == "PUT":
                    response = self.session.put(url, json={"data": data}, params=params)
                elif method == "DELETE":
                    response = self.session.delete(url, params=params)
                else:
                    raise ValueError(f"Unsupported method: {method}")

                # Raise for HTTP errors
                response.raise_for_status()
                return response.json().get("data", {})

            except requests.exceptions.RequestException as e:
                attempt += 1
                if attempt >= self.retry_count:
                    raise Exception(f"Asana API error after {self.retry_count} retries: {e}")
                # Exponential backoff
                wait_time = self.retry_delay * (2 ** (attempt - 1))
                time.sleep(wait_time)

    # ============ Portfolio Operations ============

    def create_portfolio(self, name: str, description: Optional[str] = None) -> Dict:
        """Create a new portfolio."""
        data = {"name": name}
        if description:
            data["description"] = description
        return self._request("POST", f"/portfolios", data=data)

    def get_portfolio(self, portfolio_id: str) -> Dict:
        """Get portfolio details."""
        return self._request("GET", f"/portfolios/{portfolio_id}")

    def update_portfolio(
        self,
        portfolio_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """Update a portfolio."""
        data = {}
        if name:
            data["name"] = name
        if description:
            data["description"] = description
        return self._request("PUT", f"/portfolios/{portfolio_id}", data=data)

    # ============ Project Operations ============

    def create_project(
        self,
        name: str,
        description: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> Dict:
        """Create a new project in the workspace."""
        data = {
            "name": name,
            "workspace": self.workspace_id,
        }
        if description:
            data["notes"] = description
        if team_id:
            data["team"] = team_id
        return self._request("POST", f"/projects", data=data)

    def get_project(self, project_id: str) -> Dict:
        """Get project details."""
        return self._request("GET", f"/projects/{project_id}")

    def update_project(
        self,
        project_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Dict:
        """Update a project."""
        data = {}
        if name:
            data["name"] = name
        if description:
            data["notes"] = description
        return self._request("PUT", f"/projects/{project_id}", data=data)

    def list_projects(self, team_id: Optional[str] = None) -> List[Dict]:
        """List all projects in workspace or team."""
        params = {"workspace": self.workspace_id}
        if team_id:
            params["team"] = team_id
        return self._request("GET", f"/projects", params=params)

    # ============ Task Operations ============

    def create_task(
        self,
        name: str,
        project_id: str,
        description: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Create a new task in a project."""
        data = {
            "name": name,
            "projects": [project_id],
        }
        if description:
            data["notes"] = description
        if custom_fields:
            data["custom_fields"] = custom_fields
        return self._request("POST", f"/tasks", data=data)

    def get_task(self, task_id: str) -> Dict:
        """Get task details."""
        return self._request("GET", f"/tasks/{task_id}")

    def update_task(
        self,
        task_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        custom_fields: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        """Update a task."""
        data = {}
        if name:
            data["name"] = name
        if description:
            data["notes"] = description
        if custom_fields:
            data["custom_fields"] = custom_fields
        return self._request("PUT", f"/tasks/{task_id}", data=data)

    def add_task_comment(self, task_id: str, text: str) -> Dict:
        """Add a comment to a task."""
        data = {"text": text}
        return self._request("POST", f"/tasks/{task_id}/stories", data=data)

    def list_tasks(self, project_id: str) -> List[Dict]:
        """List all tasks in a project."""
        params = {"project": project_id}
        return self._request("GET", f"/tasks", params=params)

    # ============ Custom Field Operations ============

    def create_custom_field(
        self,
        name: str,
        type: str,
        workspace_id: Optional[str] = None,
        options: Optional[List[str]] = None,
    ) -> Dict:
        """Create a custom field in a workspace."""
        ws_id = workspace_id or self.workspace_id
        data = {
            "name": name,
            "type": type,
            "workspace": ws_id,
        }
        if options and type == "enum":
            data["enum_options"] = [{"name": opt} for opt in options]
        return self._request("POST", f"/custom_fields", data=data)

    def get_custom_field(self, field_id: str) -> Dict:
        """Get custom field details."""
        return self._request("GET", f"/custom_fields/{field_id}")

    def list_custom_fields(self, workspace_id: Optional[str] = None) -> List[Dict]:
        """List all custom fields in a workspace."""
        ws_id = workspace_id or self.workspace_id
        params = {"workspace": ws_id}
        return self._request("GET", f"/custom_fields", params=params)

    # ============ User Operations ============

    def get_me(self) -> Dict:
        """Get current user information."""
        return self._request("GET", f"/users/me")

    def list_users(self, workspace_id: Optional[str] = None) -> List[Dict]:
        """List all users in a workspace."""
        ws_id = workspace_id or self.workspace_id
        params = {"workspace": ws_id}
        return self._request("GET", f"/users", params=params)

    # ============ Health Check ============

    def test_connection(self) -> bool:
        """Test that API credentials and workspace are valid."""
        try:
            user = self.get_me()
            projects = self.list_projects()
            return bool(user and projects is not None)
        except Exception as e:
            print(f"Connection test failed: {e}")
            return False
