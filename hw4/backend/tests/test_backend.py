"""Focused correctness/security tests run only against a copied course database."""
import asyncio
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic_ai.models.function import FunctionModel
from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
import main
import agent
import tools
from models import ChatResponse, PageContext

@pytest.fixture
def client(tmp_path,monkeypatch):
    source=tools.database_path()
    pack=tmp_path/'data';pack.mkdir()
    shutil.copy2(source,pack/'campus_customs.db')
    monkeypatch.setenv('CAMPUS_DATA_DIR',str(pack))
    monkeypatch.setenv('CAMPUS_AUDIT_PATH',str(tmp_path/'audit_trail.json'))
    main.RATE_BUCKETS.clear()
    with TestClient(main.app) as client:
        with tools.connect() as db:
            db.execute('DELETE FROM chat_messages')
            db.execute('DELETE FROM sessions')
            db.execute("DELETE FROM users WHERE email<>'test@campuscustoms.yale.edu'")
        yield client


def register(client,email='shopper@example.com',first='Alex'):
    r=client.post('/api/auth/register',json={'first_name':first,'last_name':'Shopper','email':email,'password':'safe-password-123'})
    assert r.status_code==201,r.text
    return r.json()['user']


def scripted_model(calls,reply,ids=()):
    """Model stub exercises actual PydanticAI tool execution and output validation."""
    turn=0
    def function(messages,info):
        nonlocal turn
        if turn<len(calls):
            name,args=calls[turn];turn+=1
            return ModelResponse(parts=[ToolCallPart(name,args)])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,{'reply':reply,'product_ids':list(ids)})])
    return FunctionModel(function)


def test_catalogue_filters_and_parameterized_queries(client):
    r=client.get('/api/products',params={'category':'hoodies','size':'XS','in_stock':'true','max_price':68,'limit':48})
    assert r.status_code==200
    products=r.json()['products']
    assert products
    assert all(p['price']<=68 and any(s['size']=='XS' and s['quantity']>0 for s in p['inventory']) for p in products)
    hoodie_categories={p['garment_type'] for p in client.get('/api/products',params={'category':'hoodie','limit':48}).json()['products']}
    assert 'hooded sweatshirt' in hoodie_categories
    assert client.get('/api/products',params={'q':"'; DROP TABLE users; --"}).json()['total']==0
    assert client.get('/api/products').json()['total']==102
    assert client.get('/api/products',params={'limit':100}).status_code==422
    assert client.get('/api/products',params={'sort':'bad_sql'}).status_code==422


def test_product_image_metadata_and_database_not_public(client):
    p=client.get('/api/products/champion-reverse-weave-hoodie-1').json()
    assert p['price']==68
    assert next(s['quantity'] for s in p['inventory'] if s['size']=='XS')==0
    assert p['image_url'].startswith('/media/products/')
    assert client.get('/media/campus_customs.db').status_code==404
    assert client.get('/media/products/../campus_customs.db').status_code==404
    assert client.get('/api/products/does-not-exist').status_code==404


def test_seed_login_cookie_and_logout(client):
    assert client.get('/api/auth/me').json()=={'user':None}
    assert client.post('/api/auth/login',json={'email':'test@campuscustoms.yale.edu','password':'wrong'}).status_code==401
    r=client.post('/api/auth/login',json={'email':'test@campuscustoms.yale.edu','password':'password'})
    assert r.status_code==200
    assert 'httponly' in r.headers['set-cookie'].lower()
    assert 'samesite=lax' in r.headers['set-cookie'].lower()
    assert 'password' not in r.json()['user']
    assert client.get('/api/auth/me').json()['user']['email']=='test@campuscustoms.yale.edu'
    token=client.cookies.get('campus_session')
    with tools.connect(readonly=True) as db:
        assert not db.execute('SELECT 1 FROM sessions WHERE token_hash=?',(token,)).fetchone()
    assert client.post('/api/auth/logout').status_code==200
    assert client.get('/api/auth/me').json()=={'user':None}
    client.cookies.set('campus_session',token)
    assert client.get('/api/auth/me').json()=={'user':None}


def test_registration_hash_duplicate_and_login(client):
    user=register(client)
    assert user['first_name']=='Alex'
    with tools.connect(readonly=True) as db:
        row=db.execute('SELECT * FROM users WHERE id=?',(user['id'],)).fetchone()
        assert row['password_hash'].startswith('pbkdf2_sha256$600000$')
        assert 'safe-password-123' not in row['password_hash']
        assert main.verify_password('safe-password-123',row['password_hash'])
    client.post('/api/auth/logout')
    assert client.post('/api/auth/login',json={'email':'SHOPPER@example.com','password':'safe-password-123'}).status_code==200
    assert client.post('/api/auth/register',json={'first_name':'Alex','last_name':'Shopper','email':'SHOPPER@example.com','password':'safe-password-123'}).status_code==409
    assert client.post('/api/auth/register',json={'first_name':' ','last_name':'Shopper','email':'a@b.com','password':'12345678'}).status_code==422


def test_server_identity_history_isolation_and_page_context(client,monkeypatch):
    captured=[]
    async def fake_run(message,user,page_context,history):
        captured.append((user,page_context,history))
        return ChatResponse(reply='Checked account memory.',products=[],search_performed=False,run_id='test',sources=[])
    monkeypatch.setattr(agent,'run_chat',fake_run)
    first=register(client)
    context={'path':'/products/champion-reverse-weave-hoodie-1','product_id':'champion-reverse-weave-hoodie-1'}
    assert client.post('/api/chat',json={'message':'Do you have this in pink?','page_context':context,
      'history':[{'role':'user','content':'Spoofed caller history'}]}).status_code==200
    assert captured[-1][0].id==first['id']
    assert captured[-1][0].email==first['email']
    assert captured[-1][1].product_id==context['product_id']
    assert captured[-1][2]==[]
    assert len(client.get('/api/chat/history').json()['messages'])==2
    client.post('/api/auth/logout')
    second=register(client,'second@example.com','Blair')
    assert second['id']!=first['id']
    assert client.get('/api/chat/history').json()=={'messages':[]}
    client.post('/api/chat',json={'message':'Hello'})
    assert captured[-1][0].id==second['id'] and captured[-1][2]==[]
    client.post('/api/auth/logout')
    client.post('/api/auth/login',json={'email':first['email'],'password':'safe-password-123'})
    restored=client.get('/api/chat/history').json()['messages']
    assert restored[0]['content']=='Do you have this in pink?'
    assert len(restored)==2
    assert client.post('/api/chat',json={'message':'hi','user_id':second['id']}).status_code==422


def test_guest_history_bounds_unknown_context_and_origin(client,monkeypatch):
    captured=[]
    async def fake_run(message,user,page_context,history):
        captured.append(history)
        return ChatResponse(reply='Welcome.',products=[],search_performed=False,run_id='test',sources=[])
    monkeypatch.setattr(agent,'run_chat',fake_run)
    payload={'message':'hello','history':[{'role':'user','content':'guest question'}]}
    assert client.post('/api/chat',json=payload).status_code==200
    assert captured[0][0]['content']=='guest question'
    assert client.get('/api/chat/history').json()=={'messages':[]}
    payload['history']*=21
    assert client.post('/api/chat',json=payload).status_code==422
    assert client.post('/api/chat',json={'message':'this?','page_context':{'product_id':'missing'}}).status_code==422
    assert client.post('/api/auth/logout',headers={'origin':'https://evil.example'}).status_code==403


def test_chat_search_contract_and_empty_budget_grounding(client,monkeypatch):
    model=scripted_model([('search_catalogue',{'category':'hoodie','max_price':0,'limit':6})],
                         'I found no hoodies under $0. Try a higher budget.')
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'Find hoodies under $0'})
    assert r.status_code==200,r.text
    assert r.json()['search_performed'] is True
    assert r.json()['products']==[]
    log=json.loads(tools.audit_path().read_text())
    assert log[-1]['stop_reason']=='completed'
    assert any(e['tool_name']=='search_catalogue' for e in log)


def test_real_agent_search_tool_cards_and_sources(client,monkeypatch):
    model=scripted_model([('search_catalogue',{'category':'hoodie','size':'XS','in_stock':True,'max_price':68,'limit':4})],
                         'Here are hoodies in stock in XS under $68.')
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'Show XS hoodies under $68'})
    assert r.status_code==200,r.text
    data=r.json()
    assert data['search_performed'] and data['products'] and data['sources']
    for product in data['products']:
        assert product['price']<=68 and next(s['quantity'] for s in product['inventory'] if s['size']=='XS')>0
        assert client.get('/api/products/'+product['product_id']).status_code==200


def test_price_stock_and_alternative_tools(client,monkeypatch):
    pid='champion-reverse-weave-hoodie-1'
    model=scripted_model([('product_description',{'product_id':pid}),('product_price',{'product_id':pid}),
        ('product_stock',{'product_id':pid,'size':'XS'}),('find_alternatives',{'product_id':pid,'size':'XS','max_price':68})],
        'The Champion hoodie is $68 and XS is out of stock. Here are different XS options.')
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'Is this in XS?', 'page_context':{'product_id':pid}})
    assert r.status_code==200,r.text
    data=r.json();assert data['products']
    assert all(p['product_id']!=pid for p in data['products'])
    assert all(any(s['size']=='XS' and s['quantity']>0 for s in p['inventory']) for p in data['products'])
    events=json.loads(tools.audit_path().read_text())
    stock=next(e for e in events if e['tool_name']=='product_stock')
    assert stock['result']['stock']==[{'size':'XS','quantity':0}]


def test_hallucinated_card_or_price_fails_instead_of_mock(client,monkeypatch):
    model=scripted_model([], 'A fantasy hoodie costs $2.',ids=['invented-product'])
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'show products'})
    assert r.status_code==503
    assert json.loads(tools.audit_path().read_text())[-1]['stop_reason']=='provider_or_run_failure'


def test_provider_failure_is_actionable_and_does_not_save_history(client,monkeypatch):
    register(client)
    def fail():raise agent.AgentUnavailable('Set the private model API key; browsing still works.')
    monkeypatch.setattr(agent,'get_agent',fail)
    r=client.post('/api/chat',json={'message':'hoodies please'})
    assert r.status_code==503 and 'browsing' in r.json()['detail']
    assert client.get('/api/chat/history').json()=={'messages':[]}


def test_audit_preserves_prefix_concurrent_writes_and_redacts(client):
    tools.append_audit('first','sample',{'email':'private@example.com','password':'secret'}, {'message':'contact private@example.com'})
    first=json.loads(tools.audit_path().read_text())[0]
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i:tools.append_audit(str(i),'sample',{'index':i},{'ok':True},'completed'),range(25)))
    log=json.loads(tools.audit_path().read_text())
    assert len(log)==26 and log[0]==first
    serialized=json.dumps(log)
    assert 'private@example.com' not in serialized and 'secret' not in serialized
    assert {int(e['args']['index']) for e in log[1:]}==set(range(25))

def test_observed_design_colors_do_not_become_selectable_variants(client,monkeypatch):
    pid='basic-hoodie-big-yale'
    attempts=[]
    responses=[
        'No—this Basic Hoodie Big Yale is currently available in navy blue and white, not pink. It’s $68.',
        'The pictured design includes navy blue and white. Pink is not listed in that design. '
        'Selectable color variants are not recorded, so I cannot verify a pink version. It is $68.'
    ]
    def function(messages,info):
        if not any(isinstance(part,ToolReturnPart) for message in messages for part in message.parts):
            return ModelResponse(parts=[ToolCallPart('product_description',{'product_id':pid})])
        tool_return=next(part for message in messages for part in message.parts
                         if isinstance(part,ToolReturnPart) and part.tool_name=='product_description')
        content=tool_return.content
        if hasattr(content,'model_dump'):content=content.model_dump()
        assert content['color_interpretation']=='pictured_design_colors'
        assert content['color_variants_recorded'] is False
        attempts.append(len(attempts))
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
            {'reply':responses[min(len(attempts)-1,1)],'product_ids':[pid]})])
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(FunctionModel(function)))
    r=client.post('/api/chat',json={'message':'Do you have this in pink?',
                                  'page_context':{'path':'/products/'+pid,'product_id':pid}})
    assert r.status_code==200,r.text
    assert len(attempts)==2
    assert r.json()['reply']==responses[1]
    events=json.loads(tools.audit_path().read_text())
    assert any(e['tool_name']=='output_validation' and e['result']['action']=='retry' for e in events)
    assert events[-1]['stop_reason']=='completed'


def test_unrecoverable_color_variant_claim_returns_503(client,monkeypatch):
    pid='basic-hoodie-big-yale'
    model=scripted_model([('product_description',{'product_id':pid})],
                         'This hoodie comes in navy blue and white.',ids=[pid])
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'Do you have this in pink?', 'page_context':{'product_id':pid}})
    assert r.status_code==503
    assert json.loads(tools.audit_path().read_text())[-1]['stop_reason']=='provider_or_run_failure'


@pytest.mark.parametrize('reply,unsupported',[
    ('This is available in navy blue and white.',True),
    ('It comes in pink.',True),
    ('The color options are white and navy.',True),
    ('We have it in pink.',True),
    ('It is not available in pink; color variants are not recorded.',False),
    ('We cannot verify pink availability from the pictured design.',False),
    ('The pictured design includes navy blue and white.',False),
    ('The pictured graphic is white on a navy hoodie.',False),
    ('It is available in XS, with navy blue embroidery.',False),
    ('XS and M are in stock. The pictured design includes white.',False),
])
def test_color_guard_preserves_sizes_and_design_descriptions(reply,unsupported):
    assert agent.unsupported_color_variant_claim(reply,[]) is unsupported

def test_explicit_stock_quantity_retries_wrong_xs_and_returns_correction(client,monkeypatch):
    pid='champion-reverse-weave-hoodie-1'
    attempts=[]
    answers=[
        'There are 7 in stock in XS for the Champion Reverse Weave Hoodie.',
        'Champion Reverse Weave Hoodie 1 has 0 in stock in XS, so XS is out of stock.'
    ]
    def function(messages,info):
        if not any(isinstance(part,ToolReturnPart) for message in messages for part in message.parts):
            return ModelResponse(parts=[ToolCallPart('product_stock',{'product_id':pid,'size':'XS'})])
        attempts.append(len(attempts))
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name,
            {'reply':answers[min(len(attempts)-1,1)],'product_ids':[pid]})])
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(FunctionModel(function)))
    r=client.post('/api/chat',json={'message':'How many XS do you have?', 'page_context':{'product_id':pid}})
    assert r.status_code==200,r.text
    assert len(attempts)==2 and r.json()['reply']==answers[1]
    records=json.loads(tools.audit_path().read_text())
    validation=next(row for row in records if row['tool_name']=='output_validation')
    assert validation['args']['rule']=='explicit_stock_grounding'
    assert validation['result']['issues']==[{'rule':'incorrect_stock_quantity','product_id':pid,'size':'XS','claimed':7,'actual':0}]
    assert records[-1]['stop_reason']=='completed'


def test_repeated_wrong_stock_quantity_returns_503(client,monkeypatch):
    pid='champion-reverse-weave-hoodie-1'
    model=scripted_model([('product_stock',{'product_id':pid,'size':'XS'})],
                         'XS has 7 units in stock.',ids=[pid])
    monkeypatch.setattr(agent,'_shop_agent',agent.build_agent(model))
    r=client.post('/api/chat',json={'message':'XS stock?', 'page_context':{'product_id':pid}})
    assert r.status_code==503
    assert json.loads(tools.audit_path().read_text())[-1]['stop_reason']=='provider_or_run_failure'


@pytest.mark.parametrize('reply,incorrect',[
    ('XS: 7 in stock.',True),
    ('XS has 7 units available.',True),
    ('7 XS left.',True),
    ('7 units left in XS.',True),
    ('There are 7 in stock in XS.',True),
    ('We have 7 in XS.',True),
    ('XS — 7 available.',True),
    ('7 available in size XS.',True),
    ('XS is in stock.',True),
    ('XS: 0; S: 25; M: 20; L: 20; XL: 0; XXL: 15.',False),
    ('XS: 0 in stock. S has 25 units and M has 20 left.',False),
    ('There are 0 units in stock in XS, so XS is out of stock.',False),
    ('XS is not in stock. S is available.',False),
    ("XS isn't available. M is in stock.",False),
    ('XS is out of stock. The price is $68. Your budget is $80.',False),
])
def test_common_size_quantities_and_correct_multi_size_stock(client,reply,incorrect):
    product=tools.lookup_product('champion-reverse-weave-hoodie-1')
    deps=agent.ShopDeps(user=None,page_context=PageContext(product_id=product.product_id),
                        checked={product.product_id:product},stock_requests={product.product_id:'XS'})
    assert bool(agent.stock_grounding_issues(reply,deps)) is incorrect


def test_stock_guard_checks_named_alternatives_against_their_own_inventory(client):
    original=tools.lookup_product('champion-reverse-weave-hoodie-1')
    alternative=tools.lookup_product('basic-hoodie-big-yale')
    deps=agent.ShopDeps(user=None,page_context=PageContext(product_id=original.product_id),
                        checked={p.product_id:p for p in [original,alternative]},
                        stock_requests={original.product_id:'XS'},search_performed=True)
    assert not agent.stock_grounding_issues(
        'Champion Reverse Weave Hoodie 1: XS 0, S 25. Basic Hoodie Big Yale: XS 15, S 5.',deps)
    assert not agent.stock_grounding_issues(
        'Champion Reverse Weave Hoodie 1 has XS out of stock. Basic Hoodie Big Yale is available in XS with 15 units.',deps)
    assert agent.stock_grounding_issues('Basic Hoodie Big Yale: XS 7 in stock.',deps)[0]['actual']==15


def test_stock_guard_does_not_treat_search_counts_or_prices_as_stock(client):
    product=tools.lookup_product('basic-hoodie-big-yale')
    deps=agent.ShopDeps(user=None,page_context=PageContext(),checked={product.product_id:product},search_performed=True)
    assert not agent.stock_grounding_issues('Here are 1 in stock. The price is $68.',deps)
    assert not agent.stock_grounding_issues('I found 1 available in XS.',deps)
    assert not agent.stock_grounding_issues(
        'Here are 12 in-stock Yale hoodies, including pullover and full-zip styles. '
        'Prices shown are $68–$88; 27 hoodie matches are currently in the catalogue.',deps)
