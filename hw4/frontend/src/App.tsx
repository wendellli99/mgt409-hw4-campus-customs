import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, NavLink, Route, Routes, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ArrowDown, ArrowRight, Check, ChevronLeft, ChevronRight, CircleHelp, LoaderCircle, Menu, MessageCircle, Search, Send, SlidersHorizontal, Sparkles, UserRound, X } from 'lucide-react';

export type Product = { product_id: string; name: string; garment_type: string; description: string; colors: string[]; search_tags: string[]; image_url: string; price: number; inventory: { size: string; quantity: number }[]; total_stock: number };
type User = { id: number; name: string; first_name: string; last_name: string; email: string };
type Message = { role: 'user' | 'assistant'; content: string; products?: Product[]; created_at?: string };
type SearchResults = { query: string; products: Product[] };
const money = (price: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(price);

async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, { ...options, credentials: 'include', headers: { 'Content-Type': 'application/json', ...options.headers } });
  let body: any;
  try { body = await response.json(); } catch { throw new Error('The shop is temporarily unavailable. Please try again.'); }
  if (!response.ok) {
    const detail = body.detail;
    throw new Error(typeof detail === 'string' ? detail : body.error || 'We could not complete that request. Please try again.');
  }
  return body as T;
}

function ProductImage({ product, className = '', eager = false }: { product: Product; className?: string; eager?: boolean }) {
  const [failed, setFailed] = useState(false);
  return failed ? <div className={`image-fallback ${className}`}><span>Image unavailable</span></div> : <img className={className} src={product.image_url} alt={product.name} loading={eager ? 'eager' : 'lazy'} onError={() => setFailed(true)} />;
}

function ProductCard({ product, compact = false }: { product: Product; compact?: boolean }) {
  return <Link to={`/products/${product.product_id}`} className={`product-card ${compact ? 'compact-card' : ''}`}>
    <div className="product-photo"><ProductImage product={product} /><span className="view-product" aria-hidden="true"><ArrowRight size={18} /></span>{product.total_stock === 0 && <span className="stock-badge">Out of stock</span>}</div>
    <div className="product-meta"><span>{product.garment_type}</span><span>{money(product.price)}</span></div>
    <h3>{product.name}</h3>
    {!compact && <p>{product.description}</p>}
  </Link>;
}

function ErrorState({ text, retry }: { text: string; retry?: () => void }) {
  return <div className="error-state" role="alert"><CircleHelp size={21} /><p>{text}</p>{retry && <button className="text-button" onClick={retry}>Try again <ArrowRight size={16} /></button>}</div>;
}

function SkeletonCards() {
  return <div className="product-grid" aria-label="Loading products">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton-card"><div /><span /><span /></div>)}</div>;
}

function Home() {
  const [products, setProducts] = useState<Product[]>([]);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const ids = ['champion-reverse-weave-crewneck', 'district-vit-hoodie-vintage-bulldog', 'hype-and-vice-yale-university-premium-crewneck', 'brooks-brothers-bomber-jacket-yale'];
    Promise.all(ids.map(id => api<Product>(`/api/products/${id}`, { signal: controller.signal }))).then(setProducts).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => controller.abort();
  }, [attempt]);
  const hero = products.find(p => p.product_id === 'champion-reverse-weave-crewneck');
  const side = products.find(p => p.product_id === 'district-vit-hoodie-vintage-bulldog');
  const featuredIds = ['champion-reverse-weave-crewneck', 'district-vit-hoodie-vintage-bulldog', 'hype-and-vice-yale-university-premium-crewneck', 'brooks-brothers-bomber-jacket-yale'];
  const featured = featuredIds.map(id => products.find(p => p.product_id === id)).filter((p): p is Product => !!p);
  return <>
    <section className="home-hero page-width">
      <div className="hero-copy"><div className="eyebrow"><span className="small-line" /> THE CAMPUS COLLECTION</div><h1>For the days<br />you call <em>Yale.</em></h1><p>From the first day on campus to the long way home.<br className="desktop-break" /> Find the classics that feel like you.</p><Link className="button button-navy" to="/products">Find your everyday <ArrowRight size={19} /></Link><div className="hero-footnote"><span className="tiny-star">✧</span> A little Bulldog pride goes a long way.</div></div>
      <div className="hero-art">
        <div className="hero-orbit" /><span className="hero-background-letter" aria-hidden="true">Y</span>
        {hero ? <Link to={`/products/${hero.product_id}`} className="hero-main-image" aria-label={`Explore ${hero.name}`}><ProductImage product={hero} eager /></Link> : <div className="hero-image-loading" />}
        <div className="hero-stamp" aria-hidden="true">NEW HAVEN<br /><strong>YALE</strong><span>STATE OF MIND</span></div>
        {side && <Link to={`/products/${side.product_id}`} className="hero-small-product"><ProductImage product={side} eager /><span>THE WEEKEND LAYER <ArrowRight size={15} /></span></Link>}
        {hero && <Link className="hero-product-caption" to={`/products/${hero.product_id}`}><span>THE CAMPUS CLASSIC</span><strong>{hero.name}</strong><span>{money(hero.price)} <ArrowRight size={17} /></span></Link>}
      </div>
    </section>
    <div className="values-strip"><div className="page-width"><span>Made for your Yale story</span><span><span aria-hidden="true">✧</span> Campus classics</span><span><span aria-hidden="true">✧</span> College &amp; team spirit</span><span><span aria-hidden="true">✧</span> New Haven roots</span></div></div>
    <section className="shop-section page-width"><div className="section-heading"><div><span className="eyebrow">THE EVERYDAY ROTATION</span><h2>Good days. Great layers.</h2></div><Link className="text-link" to="/products">Explore the collection <ArrowRight size={19} /></Link></div>{error ? <ErrorState text={error} retry={() => { setError(''); setAttempt(x => x + 1); }} /> : featured.length ? <div className="product-grid">{featured.map(p => <ProductCard product={p} key={p.product_id} />)}</div> : <SkeletonCards />}</section>
    <section className="collections-section page-width"><Link to="/products?q=hoodie" className="collection-block"><span>01 / THE COMFORT COLLECTION</span><h2>Hoodie season.<br />Any season.</h2><div>Find your layer <ArrowRight size={21} /></div></Link><Link to="/products?q=shirt" className="collection-block collection-light"><span>02 / THE CAMPUS UNIFORM</span><h2>Your college.<br />Your colors.</h2><div>Wear your story <ArrowRight size={21} /></div></Link></section>
    <section className="home-story page-width"><span className="story-monogram" aria-hidden="true">CC</span><div><span className="eyebrow">A PIECE OF THIS PLACE</span><h2>Rooted in New Haven.<br />Ready for everywhere.</h2><p>A familiar letter. A favorite college. A memory you can wear. Campus Customs brings Yale spirit to the everyday, with apparel for students, alumni, families, and the people cheering them on.</p><Link className="text-link" to="/about">Meet Campus Customs <ArrowRight size={19} /></Link></div></section>
  </>;
}

type Filters = { q: string; category: string; size: string; in_stock: boolean; max_price: string; sort: string; offset: number };
function Products() {
  const [searchParams] = useSearchParams();
  const [filters, setFilters] = useState<Filters>({ q: searchParams.get('q') || '', category: '', size: '', in_stock: false, max_price: '', sort: 'featured', offset: 0 });
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [attempt, setAttempt] = useState(0);
  useEffect(() => { setFilters(f => ({ ...f, q: searchParams.get('q') || '', offset: 0 })); }, [searchParams]);
  const update = (change: Partial<Filters>) => setFilters(f => ({ ...f, ...change, offset: 0 }));
  useEffect(() => {
    const controller = new AbortController(); setLoading(true); setError('');
    const timer = window.setTimeout(() => {
      const params = new URLSearchParams({ limit: '24', offset: String(filters.offset), sort: filters.sort });
      if (filters.q) params.set('q', filters.q); if (filters.category) params.set('category', filters.category); if (filters.size) params.set('size', filters.size); if (filters.in_stock) params.set('in_stock', 'true'); if (filters.max_price) params.set('max_price', filters.max_price);
      api<{ products: Product[]; total: number; categories: string[] }>(`/api/products?${params}`, { signal: controller.signal }).then(data => { setProducts(old => filters.offset ? [...old, ...data.products] : data.products); setTotal(data.total); setCategories(data.categories); setLoading(false); }).catch(err => { if (!controller.signal.aborted) { setError(err.message); setLoading(false); } });
    }, 240);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [filters, attempt]);
  const active = !!(filters.q || filters.category || filters.size || filters.in_stock || filters.max_price);
  return <section className="catalogue-page page-width"><div className="page-intro"><span className="eyebrow">FIND YOUR CAMPUS CLASSIC</span><h1>The collection.</h1><p>Layers for lecture. Colors for game day. Yale for every day.</p></div>
    <div className="catalogue-toolbar"><div className="filter-title"><SlidersHorizontal size={18} /><span>Make it yours</span>{active && <button className="text-button clear-filters" onClick={() => setFilters({ q: '', category: '', size: '', in_stock: false, max_price: '', sort: 'featured', offset: 0 })}>Reset filters</button>}</div>
      <div className="filter-row"><label className="search-field"><Search size={19} /><span className="sr-only">Search products</span><input placeholder="Search the collection…" value={filters.q} onChange={e => update({ q: e.target.value })} /></label><label>Category<select value={filters.category} onChange={e => update({ category: e.target.value })}><option value="">All categories</option>{categories.map(c => <option key={c} value={c}>{c}</option>)}</select></label><label>Size<select value={filters.size} onChange={e => update({ size: e.target.value })}><option value="">Any size</option>{['XS', 'S', 'M', 'L', 'XL', 'XXL', 'One Size'].map(s => <option key={s}>{s}</option>)}</select></label><label>Price<select value={filters.max_price} onChange={e => update({ max_price: e.target.value })}><option value="">Any price</option><option value="40">Up to $40</option><option value="70">Up to $70</option><option value="100">Up to $100</option></select></label><label>Sort by<select value={filters.sort} onChange={e => update({ sort: e.target.value })}><option value="featured">Featured</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="name">Name: A to Z</option></select></label></div>
      <div className="filter-bottom"><label className="checkbox-label"><input type="checkbox" checked={filters.in_stock} onChange={e => update({ in_stock: e.target.checked })} /> In stock only</label><span role="status">{loading ? 'Finding your favorites…' : `${total} ${total === 1 ? 'piece' : 'pieces'} in the collection`}</span></div>
    </div>
    {error ? <ErrorState text={error} retry={() => setAttempt(x => x + 1)} /> : loading && !products.length ? <SkeletonCards /> : !products.length ? <div className="empty-state"><Search size={30} /><h2>No pieces found.</h2><p>Try a broader search or remove a filter to discover something new.</p><button className="button button-navy" onClick={() => setFilters({ q: '', category: '', size: '', in_stock: false, max_price: '', sort: 'featured', offset: 0 })}>Explore all products <ArrowRight size={18} /></button></div> : <div className={`product-grid catalogue-grid ${loading ? 'is-loading' : ''}`} aria-busy={loading}>{products.map(p => <ProductCard product={p} key={p.product_id} />)}</div>}
    {!error && products.length > 0 && products.length < total && <div className="load-more"><p>Showing {products.length} of {total} pieces</p><button className="button button-outline" disabled={loading} onClick={() => setFilters(f => ({ ...f, offset: f.offset + 24 }))}>{loading ? <LoaderCircle className="spin" size={18} /> : <ArrowDown size={18} />} {loading ? 'Loading…' : 'Discover more'}</button></div>}
  </section>;
}

function ProductDetail({ onAsk, onProduct }: { onAsk: (question: string) => void; onProduct: (product: Product | null) => void }) {
  const { id } = useParams(); const [product, setProduct] = useState<Product | null>(null); const [size, setSize] = useState(''); const [error, setError] = useState(''); const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController(); setProduct(null); setSize(''); setError(''); onProduct(null);
    api<Product>(`/api/products/${encodeURIComponent(id || '')}`, { signal: controller.signal }).then(p => { setProduct(p); onProduct(p); }).catch(err => { if (!controller.signal.aborted) setError(err.message); });
    return () => { controller.abort(); onProduct(null); };
  }, [id, attempt, onProduct]);
  const selected = product?.inventory.find(i => i.size === size);
  return <section className="detail-page page-width"><Link className="back-link" to="/products"><ChevronLeft size={17} /> Back to the collection</Link>{error ? <ErrorState text={error} retry={() => setAttempt(x => x + 1)} /> : !product ? <div className="detail-loading" role="status"><LoaderCircle className="spin" size={30} /><span>Loading this campus classic…</span></div> : <div className="detail-grid"><div className="detail-photo"><ProductImage product={product} eager /></div><div className="detail-copy"><span className="eyebrow">{product.garment_type}</span><h1>{product.name}</h1><div className="detail-price">{money(product.price)} <span>USD</span></div><p className="detail-description">{product.description}</p><div className="detail-colors"><span className="field-heading">Catalogue colors</span>{product.colors.length ? <div>{product.colors.map(c => <span className="color-label" key={c}>{c}</span>)}</div> : <p>Colors are not recorded for this item.</p>}</div><div className="size-heading"><span className="field-heading">Find your size</span><span>{product.total_stock > 0 ? `${product.total_stock} total in stock` : 'Currently out of stock'}</span></div><div className="size-options" aria-label="Available sizes">{product.inventory.map(i => <button key={i.size} type="button" disabled={i.quantity === 0} aria-pressed={size === i.size} className={size === i.size ? 'selected' : ''} onClick={() => setSize(i.size)}><strong>{i.size}</strong><span>{i.quantity > 0 ? `${i.quantity} in stock` : 'Sold out'}</span></button>)}</div><p className="selection-status" role="status">{selected ? <><Check size={16} /> Size {selected.size}: {selected.quantity} available.</> : 'Choose a size to check its availability.'}</p><button className="button button-navy ask-product" onClick={() => onAsk(size ? `How many of this item do you have in size ${size}?` : 'What sizes of this item are in stock?')}><MessageCircle size={19} /> Ask about this item <ArrowRight size={18} /></button><div className="detail-note"><CircleHelp size={17} /><p>Browse with confidence. Your shop assistant can check current stock, colors, and product details.</p></div></div></div>}</section>;
}

function About() {
  return <section className="about-page page-width"><div className="page-intro"><span className="eyebrow">CAMPUS CUSTOMS / NEW HAVEN</span><h1>A place.<br />A people.<br /><em>A little pride.</em></h1></div><div className="about-story"><div className="about-art" aria-hidden="true"><span>Y</span><p>NEW HAVEN, CONNECTICUT<br />A YALE STATE OF MIND</p></div><div><span className="eyebrow">YOUR STORY, WELL WORN</span><h2>More than a letter<br />on a sweatshirt.</h2><p>Yale is a place you carry with you. The college that felt like home. The team you never stopped cheering for. The people who made it yours.</p><p>Campus Customs celebrates those connections through Yale apparel and accessories. From comfortable everyday layers to college and team designs, there is a piece for students, alumni, families, and every kind of Bulldog fan.</p><p>Our inspiration comes from the Campus Customs shop at <strong>57 Broadway, New Haven, Connecticut</strong>. Explore the collection here, and let our shop assistant help you find the right item and check availability.</p><Link className="button button-navy" to="/products">Find your piece of Yale <ArrowRight size={19} /></Link></div></div></section>;
}

function AuthPage({ register, onAuthenticated }: { register: boolean; onAuthenticated: (user: User) => void }) {
  const navigate = useNavigate(); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [fields, setFields] = useState({ first_name: '', last_name: '', email: '', password: '', confirm: '' });
  useEffect(() => { setError(''); setFields({ first_name: '', last_name: '', email: '', password: '', confirm: '' }); }, [register]);
  async function submit(e: FormEvent) {
    e.preventDefault(); setError('');
    if (register && fields.password !== fields.confirm) { setError('Your passwords do not match. Please check them and try again.'); return; }
    setBusy(true);
    try { const data = await api<{ user: User }>(`/api/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(register ? { first_name: fields.first_name, last_name: fields.last_name, email: fields.email, password: fields.password } : { email: fields.email, password: fields.password }) }); onAuthenticated(data.user); navigate('/products'); }
    catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  const field = (name: keyof typeof fields, label: string, type = 'text', autoComplete: string = name) => <label>{label}<input required type={type} name={name} autoComplete={autoComplete} value={fields[name]} onChange={e => setFields(f => ({ ...f, [name]: e.target.value }))} minLength={name === 'password' && register ? 8 : undefined} maxLength={name === 'email' ? 254 : name === 'password' || name === 'confirm' ? 128 : 60} /></label>;
  return <section className="auth-page page-width"><div className="auth-story"><span className="eyebrow">YOUR OWN CORNER OF CAMPUS</span><h1>{register ? <>Make yourself<br /><em>at home.</em></> : <>Good to have<br /><em>you back.</em></>}</h1><p>A familiar face. A conversation that carries on. Sign in to keep your shop assistant history with you.</p><span className="auth-monogram" aria-hidden="true">Y</span></div><div className="auth-form-card"><span className="eyebrow">CAMPUS CUSTOMS</span><h2>{register ? 'Create your account' : 'Welcome back'}</h2><p>{register ? 'A few details, and you are part of the conversation.' : 'Log in to pick up where you left off.'}</p><form onSubmit={submit}>{register && <div className="name-fields">{field('first_name', 'First name', 'text', 'given-name')}{field('last_name', 'Last name', 'text', 'family-name')}</div>}{field('email', 'Email address', 'email', 'email')}{field('password', 'Password', 'password', register ? 'new-password' : 'current-password')}{register && <><span className="form-hint">Use at least 8 characters.</span>{field('confirm', 'Confirm password', 'password', 'new-password')}</>}{error && <div className="form-error" role="alert">{error}</div>}<button className="button button-navy" type="submit" disabled={busy}>{busy && <LoaderCircle size={18} className="spin" />}{busy ? 'One moment…' : register ? 'Create account' : 'Log in'}{!busy && <ArrowRight size={18} />}</button></form><p className="auth-switch">{register ? 'Already have an account?' : 'New to Campus Customs?'} <Link to={register ? '/login' : '/register'}>{register ? 'Log in' : 'Create account'}</Link></p></div></section>;
}

function Chat({ user, authReady, product, open, setOpen, starter, consumeStarter, onResults }: { user: User | null; authReady: boolean; product: Product | null; open: boolean; setOpen: (open: boolean) => void; starter: string; consumeStarter: () => void; onResults: (r: SearchResults) => void }) {
  const location = useLocation(); const [messages, setMessages] = useState<Message[]>([]); const [draft, setDraft] = useState(''); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [historyLoading, setHistoryLoading] = useState(false); const [failedQuestion, setFailedQuestion] = useState(''); const [historyAttempt, setHistoryAttempt] = useState(0);
  const endRef = useRef<HTMLDivElement>(null); const inputRef = useRef<HTMLTextAreaElement>(null); const sendController = useRef<AbortController | null>(null); const launchRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!authReady) return;
    sendController.current?.abort(); setMessages([]); setDraft(''); setError(''); setBusy(false); setFailedQuestion('');
    if (!user) { setHistoryLoading(false); return; }
    const controller = new AbortController(); setHistoryLoading(true);
    api<{ messages: Message[] }>('/api/chat/history', { signal: controller.signal }).then(data => { setMessages(data.messages); setHistoryLoading(false); }).catch(err => { if (!controller.signal.aborted) { setError(`We could not load your saved conversation. ${err.message}`); setHistoryLoading(false); } });
    return () => controller.abort();
  }, [user?.id, authReady, historyAttempt]);
  useEffect(() => { if (open) { inputRef.current?.focus(); const handleKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setOpen(false); launchRef.current?.focus(); } }; document.addEventListener('keydown', handleKey); return () => document.removeEventListener('keydown', handleKey); } }, [open, setOpen]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'nearest' }); }, [messages, busy, open]);
  useEffect(() => { if (starter) { setDraft(starter); consumeStarter(); inputRef.current?.focus(); } }, [starter, consumeStarter]);
  async function send(question: string, retry = false) {
    const message = question.trim(); if (!message || busy || historyLoading || !authReady) return;
    const prior = retry ? messages.slice(0, -1) : messages;
    if (!retry) setMessages(old => [...old, { role: 'user', content: message }]); setDraft(''); setBusy(true); setError(''); setFailedQuestion('');
    const controller = new AbortController(); sendController.current = controller;
    try {
      const data = await api<{ reply: string; products: Product[]; search_performed: boolean; run_id: string }>('/api/chat', { method: 'POST', signal: controller.signal, body: JSON.stringify({ message, page_context: { path: location.pathname, ...(product ? { product_id: product.product_id } : {}) }, ...(!user ? { history: prior.slice(-12).map(({ role, content }) => ({ role, content })) } : {}) }) });
      if (controller.signal.aborted) return;
      setMessages(old => [...old, { role: 'assistant', content: data.reply, products: data.products }]);
      if (data.search_performed) onResults({ query: message, products: data.products });
    } catch (err) { if (!controller.signal.aborted) { setError((err as Error).message); setFailedQuestion(message); } } finally { if (!controller.signal.aborted) setBusy(false); }
  }
  const chips = product ? ['What sizes are in stock?', 'Do you have this in pink?', 'Show me similar items'] : ['Show me hoodies', 'Find something under $40', 'Help me find a crewneck'];
  return <>
    <button ref={launchRef} className={`chat-launcher ${open ? 'chat-launcher-open' : ''}`} aria-label={open ? 'Close shop assistant' : 'Open shop assistant'} aria-expanded={open} aria-controls="shop-assistant" onClick={() => setOpen(!open)}>{open ? <X size={23} /> : <MessageCircle size={22} />}<span>{open ? 'Close' : 'Ask the shop'}</span>{!open && <span className="launcher-dot" />}</button>
    {open && <section className="chat-panel" id="shop-assistant" aria-label="Campus Customs shop assistant"><header className="chat-header"><div className="assistant-icon"><Sparkles size={22} /></div><div><h2>Your campus companion</h2><p>Let’s find your kind of Yale.</p></div><button className="icon-button" aria-label="Close shop assistant" onClick={() => { setOpen(false); launchRef.current?.focus(); }}><X size={19} /></button></header><div className="chat-context">{product ? <><span className="context-dot" /><span>Viewing: <strong>{product.name}</strong></span></> : <><span className="context-dot" /><span>{user ? `Welcome, ${user.first_name || user.name.split(' ')[0]}. Your conversation is saved.` : 'Browsing as a guest · Log in to save your chat'}</span></>}</div><div className="chat-messages" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text">
      {historyLoading ? <div className="chat-history-status" role="status"><LoaderCircle className="spin" size={18} /> Loading your saved conversation…</div> : !messages.length && <div className="chat-welcome"><span className="eyebrow">A LITTLE HELP FROM THE SHOP</span><h3>{user ? `Hi, ${user.first_name || user.name.split(' ')[0]}.` : 'Hey there, Bulldog.'}</h3><p>Ask me about a product, find your favorite layer, or check which sizes are in stock.</p><div className="chat-chips">{chips.map(chip => <button key={chip} disabled={busy || !authReady} onClick={() => send(chip)}>{chip} <ArrowRight size={14} /></button>)}</div></div>}
      {messages.map((m, i) => <div className={`chat-message ${m.role}`} key={`${i}-${m.created_at || ''}`}><span className="message-author">{m.role === 'user' ? 'You' : 'Campus companion'}</span><p>{m.content}</p>{m.products && m.products.length > 0 && <div className="chat-product-list">{m.products.map(p => <Link key={p.product_id} className="chat-product" to={`/products/${p.product_id}`}><ProductImage product={p} /><span><strong>{p.name}</strong><span>{money(p.price)} · View details</span></span><ChevronRight size={16} /></Link>)}</div>}</div>)}
      {busy && <div className="chat-thinking" role="status"><span /><span /><span /><p>Checking the shop…</p></div>}
      {error && <div className="chat-error" role="alert"><p>{error}</p><button onClick={() => failedQuestion ? send(failedQuestion, true) : setHistoryAttempt(n => n + 1)} disabled={busy}>{failedQuestion ? 'Retry this question' : 'Reload saved chat'} <ArrowRight size={14} /></button></div>}<div ref={endRef} />
    </div>{messages.length > 0 && !historyLoading && <div className="chat-followups">{chips.slice(0, 2).map(chip => <button key={chip} disabled={busy} onClick={() => { setDraft(chip); inputRef.current?.focus(); }}>{chip}</button>)}</div>}<form className="chat-composer" onSubmit={e => { e.preventDefault(); send(draft); }}><label className="sr-only" htmlFor="chat-question">Ask the shop assistant</label><textarea ref={inputRef} id="chat-question" rows={1} value={draft} maxLength={2000} placeholder={product ? 'Ask about this item…' : 'What are you looking for?'} disabled={busy || historyLoading || !authReady} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(draft); } }} /><button type="submit" aria-label="Send message" disabled={!draft.trim() || busy || historyLoading || !authReady}>{busy ? <LoaderCircle size={19} className="spin" /> : <Send size={19} />}</button></form><div className="chat-footer">Stock &amp; prices checked against the shop catalogue.</div></section>}
  </>;
}

export default function App() {
  const location = useLocation(); const navigate = useNavigate(); const [user, setUser] = useState<User | null>(null); const [authReady, setAuthReady] = useState(false); const [mobileMenu, setMobileMenu] = useState(false); const [accountError, setAccountError] = useState(''); const [chatOpen, setChatOpen] = useState(false); const [starter, setStarter] = useState(''); const [contextProduct, setContextProduct] = useState<Product | null>(null); const [results, setResults] = useState<SearchResults | null>(null);
  useEffect(() => { api<{ user: User | null }>('/api/auth/me').then(data => setUser(data.user)).catch(() => { /* Guest browsing remains usable when the account service is unavailable. */ }).finally(() => setAuthReady(true)); }, []);
  useEffect(() => { setMobileMenu(false); setResults(null); setContextProduct(null); window.scrollTo({ top: 0, behavior: 'instant' }); }, [location.pathname]);
  useEffect(() => { setResults(null); }, [user?.id]);
  async function logout() { try { await api('/api/auth/logout', { method: 'POST' }); setUser(null); setAccountError(''); navigate('/'); } catch (err) { setAccountError((err as Error).message); } }
  const askProduct = (question: string) => { setStarter(question); setChatOpen(true); };
  return <><a href="#main-content" className="skip-link">Skip to content</a><div className="announcement-bar"><div className="page-width"><span>A YALE STATE OF MIND</span><span>NEW HAVEN, CONNECTICUT <span aria-hidden="true">✧</span></span></div></div><header className="site-header"><div className="nav-inner page-width"><Link className="wordmark" to="/" aria-label="Campus Customs home"><span className="brand-symbol" aria-hidden="true">C<span>C</span></span><span>CAMPUS<br /><strong>CUSTOMS</strong></span></Link><nav className="desktop-nav" aria-label="Main navigation"><NavLink to="/" end>Home</NavLink><NavLink to="/products">Products</NavLink><NavLink to="/about">About Us</NavLink></nav><div className="account-nav">{user ? <><span className="account-name"><UserRound size={16} /> Hi, {user.first_name || user.name.split(' ')[0]}</span><button className="text-button" onClick={logout}>Log out</button></> : <><NavLink to="/login" className="login-link">Log in</NavLink><NavLink to="/register" className="create-account-link">Create account <ArrowRight size={15} /></NavLink></>}</div><button className="mobile-menu-button icon-button" aria-label={mobileMenu ? 'Close navigation' : 'Open navigation'} aria-expanded={mobileMenu} onClick={() => setMobileMenu(!mobileMenu)}>{mobileMenu ? <X size={24} /> : <Menu size={24} />}</button></div>{mobileMenu && <nav className="mobile-nav" aria-label="Mobile navigation"><NavLink to="/" end>Home</NavLink><NavLink to="/products">Products</NavLink><NavLink to="/about">About Us</NavLink>{user ? <><span>Hi, {user.first_name || user.name}</span><button className="text-button" onClick={logout}>Log out</button></> : <><NavLink to="/login">Log in</NavLink><NavLink to="/register">Create account</NavLink></>}</nav>}</header>{accountError && <div className="page-width"><ErrorState text={accountError} retry={logout} /></div>}
    <main id="main-content">{results && <section className="chat-results-section page-width" aria-label="Shop assistant matches"><div className="section-heading"><div><span className="eyebrow"><Sparkles size={14} /> HANDPICKED BY YOUR CAMPUS COMPANION</span><h2>Matches from your chat.</h2><p>“{results.query}” · {results.products.length} {results.products.length === 1 ? 'match' : 'matches'}</p></div><button className="text-button" onClick={() => setResults(null)}>Dismiss <X size={16} /></button></div>{results.products.length ? <div className="product-grid">{results.products.map(p => <ProductCard key={p.product_id} product={p} compact />)}</div> : <div className="empty-state"><p>No products matched this request. Try a different category, size, or price.</p><Link className="text-link" to="/products">Browse the collection <ArrowRight size={18} /></Link></div>}</section>}
    <Routes><Route path="/" element={<Home />} /><Route path="/products" element={<Products />} /><Route path="/products/:id" element={<ProductDetail onAsk={askProduct} onProduct={setContextProduct} />} /><Route path="/about" element={<About />} /><Route path="/login" element={<AuthPage register={false} onAuthenticated={setUser} />} /><Route path="/register" element={<AuthPage register onAuthenticated={setUser} />} /><Route path="*" element={<section className="page-width empty-state"><h1>This page took the scenic route.</h1><Link className="button button-navy" to="/">Back home <ArrowRight size={18} /></Link></section>} /></Routes></main>
    <footer className="site-footer"><div className="footer-main page-width"><div><Link className="footer-brand" to="/">Campus Customs.</Link><p>A little Yale, wherever life takes you.</p></div><div><span className="eyebrow">COME ON BY</span><p>57 Broadway<br />New Haven, CT 06511</p></div><div><span className="eyebrow">KEEP EXPLORING</span><Link to="/products">The collection <ArrowRight size={15} /></Link><Link to="/about">Our story <ArrowRight size={15} /></Link><a href="https://yalebulldogblue.com" target="_blank" rel="noreferrer">Visit the original shop <ArrowRight size={15} /></a></div></div><div className="footer-bottom page-width"><span>© 2026 Campus Customs coursework storefront</span><span>Educational catalogue experience · No online checkout</span></div></footer>
    <Chat user={user} authReady={authReady} product={contextProduct} open={chatOpen} setOpen={setChatOpen} starter={starter} consumeStarter={() => setStarter('')} onResults={setResults} />
  </>;
}
