import httpx
import pytest


@pytest.mark.asyncio
async def test_send_email(client: httpx.AsyncClient):
    pass


@pytest.mark.asyncio
async def test_send_sms(client: httpx.AsyncClient):
    pass


@pytest.mark.asyncio
async def test_phone_verification(client: httpx.AsyncClient):
    pass


@pytest.mark.asyncio
async def test_phone_confirmation(client: httpx.AsyncClient):
    pass
