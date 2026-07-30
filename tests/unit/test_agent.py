from app.agent.nodes import route_question
def test_router_document(): assert route_question('휴가 정책 문서를 알려줘') == 'DOCUMENT'
def test_router_data(): assert route_question('지난달 매출 알려줘') == 'DATABASE'
