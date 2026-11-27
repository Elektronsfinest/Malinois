import pytest
from security import login_rate_limiter


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    login_rate_limiter.reset()
    yield
    login_rate_limiter.reset()
