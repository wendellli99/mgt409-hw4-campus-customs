"""Run from backend/: uvicorn main:app --reload --port 8000."""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
import sqlite3
import threading
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Literal
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import agent
import tools
from models import ChatRequest, ChatResponse, LoginRequest, RegisterRequest, User

COOKIE='campus_session'
SESSION_SECONDS=7*24*60*60
PASSWORD_ITERATIONS=600000
RATE_BUCKETS=defaultdict(deque)
RATE_LOCK=threading.Lock()


@asynccontextmanager
async def lifespan(app: FastAPI):
    tools.initialize_database()
    yield


app=FastAPI(title='Campus Customs API',version='1.0.0',lifespan=lifespan)
ORIGINS=[s.strip() for s in os.getenv('FRONTEND_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(',') if s.strip()]
app.add_middleware(CORSMiddleware,allow_origins=ORIGINS,allow_credentials=True,
                   allow_methods=['GET','POST'],allow_headers=['Content-Type'])
app.mount('/media/products',StaticFiles(directory=str(tools.data_dir() / 'products'),check_dir=False),name='product_images')


@app.middleware('http')
async def browser_write_guard(request: Request,call_next):
    # JSON endpoints plus an origin allowlist prevent cross-site cookie-backed writes.
    origin=request.headers.get('origin')
    allowed=set(ORIGINS)|{'http://localhost:8000','http://127.0.0.1:8000'}
    if request.method=='POST' and origin and origin not in allowed:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=403,content={'detail':'This request origin is not allowed.'})
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    if request.url.path.startswith('/api/auth') or request.url.path.startswith('/api/chat'):
        response.headers['Cache-Control']='no-store'
    return response


def rate_limit(request: Request,bucket: str,maximum: int):
    identifier=request.client.host if request.client else 'local'
    key=(bucket,identifier)
    timestamp=time.monotonic()
    with RATE_LOCK:
        entries=RATE_BUCKETS[key]
        while entries and timestamp-entries[0]>60:entries.popleft()
        if len(entries)>=maximum:
            raise HTTPException(429,'Too many attempts. Please wait one minute and try again.',headers={'Retry-After':'60'})
        entries.append(timestamp)


def password_hash(password: str) -> str:
    salt=secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),PASSWORD_ITERATIONS).hex()
    return f'pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest}'


def verify_password(password: str,encoded: str) -> bool:
    try:
        parts=encoded.split('$')
        if len(parts)==3 and parts[0]=='pbkdf2_sha256':
            # The supplied course seed uses this documented legacy format.
            rounds,salt,digest=120000,parts[1],parts[2]
        elif len(parts)==4 and parts[0]=='pbkdf2_sha256':
            rounds,salt,digest=int(parts[1]),parts[2],parts[3]
        else:return False
        if not 100000<=rounds<=2000000:return False
        candidate=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),rounds).hex()
        return hmac.compare_digest(candidate,digest)
    except (ValueError,TypeError):return False


_DUMMY_HASH=password_hash('a random unused password '+secrets.token_hex(16))


def public_user(row) -> User:
    first=row['first_name'] or row['name'].split(' ',1)[0]
    last=row['last_name'] or (row['name'].split(' ',1)[1] if ' ' in row['name'] else '')
    return User(id=row['id'],first_name=first,last_name=last,name=row['name'],email=row['email'])


def get_current_user(request: Request) -> User|None:
    token=request.cookies.get(COOKIE)
    if not token or len(token)>200:return None
    digest=hashlib.sha256(token.encode()).hexdigest()
    with tools.connect(readonly=True) as db:
        row=db.execute('''SELECT u.* FROM users u JOIN sessions s ON s.user_id=u.id
            WHERE s.token_hash=? AND s.expires_at>?''',(digest,tools.now())).fetchone()
        return public_user(row) if row else None


def create_session(user_id: int,response: Response,old_token: str|None = None):
    token=secrets.token_urlsafe(32)
    expires=(datetime.now(timezone.utc)+timedelta(seconds=SESSION_SECONDS)).isoformat(timespec='seconds')
    with tools.connect() as db:
        db.execute('DELETE FROM sessions WHERE expires_at<=?',(tools.now(),))
        if old_token:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(old_token.encode()).hexdigest(),))
        db.execute('INSERT INTO sessions(token_hash,user_id,expires_at) VALUES (?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(),user_id,expires))
    response.set_cookie(COOKIE,token,httponly=True,secure=os.getenv('SESSION_COOKIE_SECURE','false').lower()=='true',
                        samesite='lax',max_age=SESSION_SECONDS,path='/')


@app.get('/api/health')
def health():
    with tools.connect(readonly=True) as db:
        count=db.execute('SELECT count(*) FROM catalogue').fetchone()[0]
    return {'ok':True,'catalogue_products':count,'model':os.getenv('PORTKEY_MODEL','gpt-5.6-luna')}


@app.get('/api/products')
def products(q: Annotated[str,Query(max_length=120)]='',category: Annotated[str,Query(max_length=60)]='',
             size: Annotated[str,Query(max_length=20)]='',in_stock: bool=False,
             max_price: Annotated[float|None,Query(ge=0,le=10000)]=None,
             sort: Literal['featured','price_asc','price_desc','name']='featured',
             limit: Annotated[int,Query(ge=1,le=48)]=24,offset: Annotated[int,Query(ge=0,le=10000)]=0):
    return tools.search_products(q=q,category=category,size=size,in_stock=in_stock,max_price=max_price,
                                 sort=sort,limit=limit,offset=offset)


@app.get('/api/products/{product_id}')
def product(product_id: str):
    p=tools.lookup_product(product_id)
    if not p:raise HTTPException(404,'That product was not found.')
    return p


@app.get('/api/auth/me')
def me(user: Annotated[User|None,Depends(get_current_user)]):
    return {'user':user}


@app.post('/api/auth/register',status_code=201)
def register(payload: RegisterRequest,request: Request,response: Response):
    rate_limit(request,'register',10)
    encoded=password_hash(payload.password)
    try:
        with tools.connect() as db:
            if db.execute('SELECT 1 FROM users WHERE lower(email)=?',(payload.email,)).fetchone():
                raise HTTPException(409,'An account with that email already exists. Please log in.')
            cursor=db.execute('INSERT INTO users(name,email,password_hash,first_name,last_name) VALUES (?,?,?,?,?)',
                (payload.first_name+' '+payload.last_name,payload.email,encoded,payload.first_name,payload.last_name))
            row=db.execute('SELECT * FROM users WHERE id=?',(cursor.lastrowid,)).fetchone()
            user=public_user(row)
    except sqlite3.IntegrityError:
        raise HTTPException(409,'An account with that email already exists. Please log in.')
    create_session(user.id,response,request.cookies.get(COOKIE))
    return {'user':user}


@app.post('/api/auth/login')
def login(payload: LoginRequest,request: Request,response: Response):
    rate_limit(request,'login',10)
    with tools.connect(readonly=True) as db:
        row=db.execute('SELECT * FROM users WHERE lower(email)=?',(payload.email.strip().lower(),)).fetchone()
    valid=verify_password(payload.password,row['password_hash'] if row else _DUMMY_HASH)
    if not row or not valid:raise HTTPException(401,'Email or password is incorrect.')
    user=public_user(row)
    create_session(user.id,response,request.cookies.get(COOKIE))
    return {'user':user}


@app.post('/api/auth/logout')
def logout(request: Request,response: Response):
    token=request.cookies.get(COOKIE)
    if token:
        with tools.connect() as db:
            db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),))
    response.delete_cookie(COOKIE,path='/',httponly=True,samesite='lax')
    return {'ok':True}


@app.get('/api/chat/history')
def history(user: Annotated[User|None,Depends(get_current_user)]):
    return {'messages':tools.load_history(user.id) if user else []}


@app.post('/api/chat',response_model=ChatResponse)
async def chat(payload: ChatRequest,request: Request,user: Annotated[User|None,Depends(get_current_user)]):
    rate_limit(request,'chat',20)
    if payload.page_context.product_id and not tools.lookup_product(payload.page_context.product_id):
        raise HTTPException(422,'The current page product does not exist. Open a product and try again.')
    saved=tools.load_history(user.id,20) if user else [m.model_dump() for m in payload.history]
    try:
        result=await agent.run_chat(payload.message,user,payload.page_context,saved)
    except agent.AgentUnavailable as exc:
        raise HTTPException(503,str(exc))
    if user:tools.save_exchange(user.id,payload.message,result.reply,result.products)
    return result
