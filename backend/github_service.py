import requests
from github import Auth, Github, GithubException

from . import config


class GitHubError(Exception):
    pass


def create_repo(name: str, description: str, private: bool, topics: list[str]) -> tuple[str, str]:
    """Create the repository; returns (html_url, clone_url)."""
    if not config.GITHUB_TOKEN:
        raise GitHubError("GITHUB_TOKEN is not configured.")
    try:
        user = Github(auth=Auth.Token(config.GITHUB_TOKEN)).get_user()
        repo = user.create_repo(name, description=description, private=private, auto_init=False)
    except GithubException as e:
        if e.status == 401:
            raise GitHubError("GitHub authentication failed. Check GITHUB_TOKEN.") from None
        if e.status == 422:
            raise GitHubError(f"A repository named '{name}' already exists on your account, or the name is invalid.") from None
        if e.status == 403:
            raise GitHubError("GitHub denied the request. The token may lack the 'repo' scope, or you hit a rate limit.") from None
        raise GitHubError(f"GitHub API error (HTTP {e.status}).") from None
    except requests.exceptions.RequestException:
        raise GitHubError("Could not reach GitHub. Check your network connection.") from None
    try:
        if topics:
            repo.replace_topics(topics)
    except GithubException:
        pass
    return repo.html_url, repo.clone_url
