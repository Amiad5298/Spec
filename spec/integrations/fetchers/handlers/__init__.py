"""Platform-specific API handlers for DirectAPIFetcher."""

from spec.integrations.fetchers.handlers.azure_devops import AzureDevOpsHandler
from spec.integrations.fetchers.handlers.base import PlatformHandler
from spec.integrations.fetchers.handlers.github import GitHubHandler
from spec.integrations.fetchers.handlers.jira import JiraHandler
from spec.integrations.fetchers.handlers.linear import LinearHandler
from spec.integrations.fetchers.handlers.monday import MondayHandler
from spec.integrations.fetchers.handlers.trello import TrelloHandler

__all__ = [
    "PlatformHandler",
    "JiraHandler",
    "LinearHandler",
    "GitHubHandler",
    "AzureDevOpsHandler",
    "TrelloHandler",
    "MondayHandler",
]
