from mcp_servers.document.acl import filter_allowed
def test_acl_filters_document():
    docs=[{'id':'1','allowed_roles':['admin']}]
    assert filter_allowed(docs, {'role':'user'}) == []
