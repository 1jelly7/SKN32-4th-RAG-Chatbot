import pytest
from mcp_servers.data.sql_guard import validate_sql
def test_sql_guard_blocks_write():
    with pytest.raises(ValueError): validate_sql('DELETE FROM users')
