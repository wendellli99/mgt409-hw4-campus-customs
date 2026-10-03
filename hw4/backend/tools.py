"""Read-only merchandise tools, SQLite persistence, and append-only audit storage."""
from __future__ import annotations
import fcntl
import json
import os
import re
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from models import Product, Stock, SearchResult

ROOT = Path(__file__).resolve().parent.parent
_AUDIT_LOCK = threading.Lock()
CATEGORY_ALIASES = {
    'hoodies': 'hoodie', 'hooded sweatshirt': 'hoodie',
    't-shirts': 't-shirt', 'tees': 't-shirt', 'shirts': 'shirt', 'sweatshirts': 'sweatshirt',
    'caps': 'hat', 'hats': 'hat', 'beanies': 'beanie', 'pants': 'pants',
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def data_dir() -> Path:
    configured = os.getenv('CAMPUS_DATA_DIR')
    if configured:
        path = Path(configured).expanduser()
        return (ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    for path in (ROOT / 'data', ROOT.parent / 'data'):
        if (path / 'campus_customs.db').is_file():
            return path.resolve()
    return (ROOT / 'data').resolve()


def database_path() -> Path:
    return data_dir() / 'campus_customs.db'


@contextmanager
def connect(readonly: bool = False):
    path = database_path()
    if not path.is_file():
        raise FileNotFoundError('Place the course data pack in hw4/data or set CAMPUS_DATA_DIR.')
    target = f'file:{quote(str(path))}?mode=ro' if readonly else str(path)
    connection = sqlite3.connect(target, uri=readonly, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    try:
        yield connection
        if not readonly:
            connection.commit()
    finally:
        connection.close()


def initialize_database() -> None:
    """Extend the provided pack; never replace catalogue, inventory or seed users."""
    with connect() as db:
        fields = {row['name'] for row in db.execute('PRAGMA table_info(users)')}
        for field in ('first_name', 'last_name'):
            if field not in fields:
                db.execute(f'ALTER TABLE users ADD COLUMN {field} TEXT')
        db.execute('''CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )''')
        db.execute('''CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            role TEXT NOT NULL CHECK(role IN ('user','assistant')),
            content TEXT NOT NULL,
            products_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )''')
        db.execute('CREATE INDEX IF NOT EXISTS chat_messages_user_id_idx ON chat_messages(user_id,id)')


def product_from_row(db, row) -> Product:
    stock = [Stock(size=r['size'], quantity=r['quantity']) for r in db.execute(
        'SELECT size,quantity FROM inventory WHERE product_id=? ORDER BY id', (row['product_id'],))]
    image_path = row['image_file_path'].replace('\\', '/').removeprefix('data/').lstrip('/')
    if not image_path.startswith('products/') or '..' in Path(image_path).parts:
        image_url = '/media/products/missing.jpg'
    else:
        image_url = '/media/' + quote(image_path, safe='/')
    return Product(product_id=row['product_id'], name=row['name'], garment_type=row['garment_type'],
                   description=row['description'], colors=json.loads(row['colors']),
                   search_tags=json.loads(row['search_tags']), image_url=image_url, price=row['price'],
                   inventory=stock, total_stock=sum(s.quantity for s in stock))


def lookup_product(product_id: str) -> Product | None:
    with connect(readonly=True) as db:
        row = db.execute('SELECT * FROM catalogue WHERE product_id=?', (product_id,)).fetchone()
        return product_from_row(db, row) if row else None


def _like(value: str) -> str:
    return value.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def search_products(q: str = '', category: str = '', size: str = '', in_stock: bool = False,
                    max_price: float | None = None, sort: str = 'featured', limit: int = 24,
                    offset: int = 0) -> dict:
    conditions, parameters = [], []
    for term in q.lower().strip().split()[:8]:
        # Treat plural item words as the same catalogue concept.
        term = CATEGORY_ALIASES.get(term, term)
        conditions.append("lower(c.name || ' ' || c.garment_type || ' ' || c.description || ' ' || c.colors || ' ' || c.search_tags) LIKE ? ESCAPE '\\'")
        parameters.append('%' + _like(term) + '%')
    if category:
        category = CATEGORY_ALIASES.get(category.lower().strip(), category.lower().strip())
        conditions.append("lower(c.garment_type) LIKE ? ESCAPE '\\'")
        parameters.append('%' + _like('hood' if category == 'hoodie' else category) + '%')
    if max_price is not None:
        conditions.append('c.price<=?')
        parameters.append(max_price)
    if size:
        conditions.append('EXISTS (SELECT 1 FROM inventory i WHERE i.product_id=c.product_id AND upper(i.size)=?'+(' AND i.quantity>0' if in_stock else '')+')')
        parameters.append(size.upper())
    elif in_stock:
        conditions.append('EXISTS (SELECT 1 FROM inventory i WHERE i.product_id=c.product_id AND i.quantity>0)')
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    ordering = {'featured':'c.rowid', 'price_asc':'c.price,c.name', 'price_desc':'c.price DESC,c.name', 'name':'c.name COLLATE NOCASE'}[sort]
    with connect(readonly=True) as db:
        total = db.execute('SELECT count(*) FROM catalogue c'+where, parameters).fetchone()[0]
        rows = db.execute('SELECT c.* FROM catalogue c'+where+' ORDER BY '+ordering+' LIMIT ? OFFSET ?',
                          [*parameters, min(max(limit,1),48), max(offset,0)]).fetchall()
        categories = [r[0] for r in db.execute('SELECT DISTINCT garment_type FROM catalogue ORDER BY garment_type')]
        return {'products':[product_from_row(db,r) for r in rows], 'total':total, 'categories':categories}


def load_history(user_id: int, limit: int = 100) -> list[dict]:
    with connect(readonly=True) as db:
        rows = db.execute('''SELECT role,content,products_json,created_at FROM
            (SELECT id,role,content,products_json,created_at FROM chat_messages WHERE user_id=? ORDER BY id DESC LIMIT ?)
            ORDER BY id''', (user_id, min(limit,100))).fetchall()
        return [{'role':r['role'],'content':r['content'],'products':json.loads(r['products_json'] or '[]'),
                 'created_at':r['created_at']} for r in rows]


def save_exchange(user_id: int, message: str, reply: str, products: list[Product]) -> None:
    with connect() as db:
        db.executemany('INSERT INTO chat_messages(user_id,role,content,products_json) VALUES (?,?,?,?)', [
            (user_id,'user',message,'[]'),
            (user_id,'assistant',reply,json.dumps([p.model_dump() for p in products]))])


def audit_path() -> Path:
    return Path(os.getenv('CAMPUS_AUDIT_PATH', str(ROOT / 'output' / 'audit_trail.json'))).resolve()


def _redact(value):
    if isinstance(value, str):
        return re.sub(r'[^\s@]+@[^\s@]+\.[^\s@]+','[redacted email]',value)[:500]
    if isinstance(value,dict):
        return {k:_redact(v) for k,v in value.items() if k not in {'password','password_hash','email','token','api_key'}}
    if isinstance(value,list):
        return [_redact(v) for v in value[:12]]
    return value


def append_audit(run_id: str, tool_name: str, args: dict, result: dict, stop_reason: str | None = None) -> None:
    """Preserve every record; serialize writers and atomically replace the JSON array."""
    path = audit_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    record = {'time':now(),'run_id':run_id,'tool_name':tool_name,'args':_redact(args),
              'result':_redact(result),'stop_reason':stop_reason}
    with _AUDIT_LOCK, path.with_suffix('.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(),fcntl.LOCK_EX)
        previous = json.loads(path.read_text()) if path.exists() else []
        if not isinstance(previous,list):
            raise ValueError('Audit file must be a JSON array. Existing content has been preserved.')
        previous.append(record)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,
                                             prefix='.audit-',delete=False) as output:
                temporary=Path(output.name)
                json.dump(previous,output,ensure_ascii=False,indent=2)
                output.write('\n');output.flush();os.fsync(output.fileno())
            temporary.replace(path)
        finally:
            if temporary and temporary.exists():temporary.unlink()
            fcntl.flock(lock.fileno(),fcntl.LOCK_UN)
