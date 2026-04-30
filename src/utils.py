import os
from contextlib import contextmanager

import kagglehub
from github import Auth, Github


@contextmanager
def gh():
    access_token = os.getenv("GITHUB_TOKEN")
    if not access_token:
        raise ValueError(
            """GITHUB_TOKEN environment variable not set. Please set it before running the script. 
            Run `cp example.env .env` and edit the .env file to add your GitHub token."""
        )

    auth = Auth.Token(access_token)
    g = Github(auth=auth)
    try:
        yield g
    finally:
        g.close()


def check_access(_):
    with gh() as g:
        # Check for access
        try:
            user = g.get_user()
            print(f"Authenticated as: {user.login}")
            print("You are good to continue!")
        except Exception as e:
            print(f"Authentication failed: {e}")


# Install dependencies as needed:
# pip install kagglehub[pandas-datasets]


def download_dataset(url: str):
    return kagglehub.dataset_download(url)
