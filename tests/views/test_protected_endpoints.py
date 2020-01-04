import httpx
import pytest
from starlette import testclient


async def test_delete_users_by_access_to_delete_role(client: testclient.TestClient):
    pass


async def test_edit_user_details(client: testclient.TestClient):
    # account for editing regular details as well as email which require confirmation.
    pass


async def test_assign_or_edit_user_roles(client: testclient.TestClient):
    pass

