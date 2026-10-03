# Campus Customs system harness

## Source database
The supplied data pack contains 102 catalogue rows and 612 size-level inventory rows. Its existing tables are inspected directly below. The database and product photographs remain local; the public project contains code and required screenshots only.

### catalogue
| Field | SQLite type | Purpose |
|---|---|---|
| `product_id` | TEXT | Stable key used by detail URLs, lookup tools, and inventory joins. |
| `name` | TEXT | Customer-visible product title. |
| `garment_type` | TEXT | Category for browsing and chatbot searches. |
| `description` | TEXT | Full product information used in cards, details, and grounded replies. |
| `colors` | TEXT | JSON text array of pictured design colors, including graphics or embroidery; not selectable variants or per-color stock. |
| `search_tags` | TEXT | JSON text array that broadens relevant keyword matching. |
| `image_file_path` | TEXT | Path to the supplied local photograph; converted into a safe media URL. |
| `price` | REAL | Authoritative price in US dollars; the model must look it up. |

### inventory
| Field | SQLite type | Purpose |
|---|---|---|
| `id` | INTEGER | Unique stock-row identifier. |
| `product_id` | TEXT | Links each size quantity to its catalogue item. |
| `size` | TEXT | Size label shown in selectors and size-specific tools. |
| `quantity` | INTEGER | Actual number available; zero means out of stock. |

### users
| Field | SQLite type | Purpose |
|---|---|---|
| `id` | INTEGER | Server-side account identity and history owner. |
| `name` | TEXT | Existing full display name; maintained for compatibility. |
| `email` | TEXT | Unique normalized login address and signed-in agent context. |
| `password_hash` | TEXT | One-way salted password verifier; never sent to the model or browser. |
| `created_at` | TEXT | Database account creation timestamp. |
| `first_name` | TEXT | Registration first name and personalized customer context. |
| `last_name` | TEXT | Registration last name and full display name. |

### chat_messages
| Field | SQLite type | Purpose |
|---|---|---|
| `id` | INTEGER | Stable ordering for saved conversation turns. |
| `user_id` | INTEGER | Links history to its authenticated owner. |
| `role` | TEXT | Whether the message came from the shopper or assistant. |
| `content` | TEXT | Saved message text used to restore the conversation. |
| `products_json` | TEXT | Serialized product cards for assistant messages and restored search matches. |
| `created_at` | TEXT | Timestamp shown with the retained turn. |

### sqlite_sequence (SQLite-managed)

| Field | SQLite type | Purpose |
|---|---|---|
| `name` | Not declared | Stores the table name whose auto-increment counter SQLite maintains. |
| `seq` | Not declared | Stores the last allocated integer ID; helps SQLite assign the next ID for accounts, inventory rows, and chat messages. |

The application does not treat this internal table as merchandise or customer data. `colors`, `search_tags`, and `products_json` are JSON encoded inside text columns, then validated as structured types by the backend.

## Store voice and source
Research source: [Yale Bulldog Blue by Campus Customs](https://yalebulldogblue.com/), reviewed October 3, 2026. The live homepage presents Yale merchandise across apparel and accessories, college and school collections, and a New Haven storefront at 57 Broadway. This project uses original copy with that campus-focused tone. The course database, rather than live-site prices, is authoritative for this assignment. No shipping promise, return policy, sale, or made-up store history is added.

## Authentication and database writes

Registration accepts first name, last name, normalized email, and password; confirmation is checked in the frontend. The existing users table stores the names, address, creation time, and a salted PBKDF2-SHA256 password verifier. Fresh accounts use 600,000 rounds and encode the algorithm, rounds, salt, and digest. The supplied seed uses the legacy three-part PBKDF2 format with 120,000 rounds; the verifier supports that format so the documented course test account works. Passwords are never retained as plaintext or provided to the agent.

The backend adds `sessions` with these fields:

| Field | Purpose |
|---|---|
| token_hash | SHA-256 of a random session token; stored instead of the raw browser token. |
| user_id | Authenticated users.id that owns the session. |
| expires_at | Seven-day expiration used when validating and cleaning sessions. |
| created_at | Session creation timestamp. |

The browser receives a random HttpOnly, SameSite=Lax cookie. Login and registration replace the current session; logout deletes it. `SESSION_COOKIE_SECURE=true` is required when serving over HTTPS; local HTTP development uses false. The current user is derived on the server from the cookie and database session, never from a caller-supplied user ID. Auth and chat responses are marked no-store. Write requests enforce an origin allowlist; login/registration and chat have per-process rate limits. These are local coursework controls, not a claim of production security certification.

## Saved conversation and current-page context

A successful signed-in exchange inserts one user and one assistant row into chat_messages in one transaction. The assistant row stores its typed product cards in products_json. History reads filter by the authenticated user_id, retain original ordering, and return up to the latest 100 turns for the interface. The model receives at most 20 recent messages. Signed-in requests use server-loaded history and disregard browser-submitted history. Guests keep their current conversation in browser memory; the API accepts at most 20 bounded guest turns and does not persist them.

Agent dependencies contain the server-authenticated user (`id`, `name`, `first_name`, `last_name`, `email`) or null, the page path, current product ID, run ID, and products checked during that run. Internal `stock_requests` maps each product ID to the most recent size requested from the stock tool, or null for whole-item stock; this lets the output guard interpret a bare quantity against the correct lookup. Page context is checked against the catalogue. The agent gets the current item's ID and name, then must call tools for its facts. This makes “this in pink?” refer to the open item. Names and other context values are data, not instructions. Other customers, password hashes, and session credentials are never included in dependencies.

## API and frontend contract

Vite proxies `/api` and `/media` to FastAPI on port 8000. React sends JSON with same-origin credentials. The product media route exposes only the local products directory, not the database.

| Route | Result / purpose |
|---|---|
| GET /api/products | products, total match count, and garment categories; supports text/category/size/stock/price/sort/pagination. |
| GET /api/products/{product_id} | Full validated product, including per-size inventory. |
| GET /api/auth/me | Current public user fields or null. |
| POST /api/auth/register, /login, /logout | Account/session lifecycle; never returns a password hash. |
| GET /api/chat/history | Saved messages and product cards belonging to the current account. |
| POST /api/chat | reply, products, search_performed, run_id, and checked database sources. |

The chat request has `message`, `page_context` (`path`, optional `product_id`), and optional guest `history`. `search_performed=true` tells React to display a new matches section, even if the products array is empty. Cards use stable product IDs and the same detail route as the normal catalogue. Inventory-only answers can include a checked item without pretending a category search occurred. Errors include meaningful HTTP status and safe detail text; failed model calls do not produce a simulated reply or save a fake successful conversation.

## Structured fields and why they exist

| Type | Fields and why they were chosen |
|---|---|
| Product | product_id for stable references; name, description, garment_type, colors, and search_tags carry catalogue facts for titles, full detail, categories, pictured design, and search; image_url makes safe photographs usable in cards; price is the actual USD price; inventory provides per-size quantities and total_stock supports overall availability. |
| Stock | size and nonnegative quantity keep size-specific answers explicit. |
| User | id binds the server-authenticated account to its history; first_name, last_name, and name support registration and natural personalization; email identifies the signed-in shopper. Private password/session fields are excluded. |
| PageContext | path and product_id resolve references to the open item. |
| ChatRequest | message carries the shopper's question, page_context resolves the open item, and history supports bounded guest continuity. Signed-in history is loaded on the server; unknown extra fields are rejected. |
| HistoryMessage | role distinguishes user and assistant turns; content supplies bounded text context without trusting a historical message as current merchandise evidence. |
| AgentReply | Short reply and up to 12 product_ids; the model selects checked references instead of generating product cards. |
| ChatResponse | reply is the verified agent text; products contains server-rebuilt cards; search_performed tells the page to show matches or an empty state; run_id links the response to the audit; sources explains the checked database facts. |
| Source | table names the source tables; product_ids identifies items looked up; checked_at labels the current run's stock/price snapshot. |
| SearchResult | products, total, filters, result_cap, message distinguish a capped result set from the full match count and explain no matches. |
| ProductLookup | found, optional product, message distinguish missing IDs from valid products; color_interpretation and color_variants_recorded explicitly separate pictured design colors from unavailable variant data. |
| StockLookup | found, product_id/name, requested_size, stock, message distinguish zero stock from a size not carried. |
| RegisterRequest | first_name and last_name collect the requested account names; email is normalized for unique login; password is bounded before secure hashing. Extra fields, including caller-controlled IDs, are rejected. |
| LoginRequest | email locates the account and password is verified against its hash; field limits bound request size, and extra fields are rejected. |

## Merchandise tools

| Tool | Ability and boundaries |
|---|---|
| search_catalogue | Read-only parameterized search with keywords, category, size, in_stock, max_price and limit. Returns at most 12 cards and actual match count. Hoodie aliases also match hooded sweatshirts. |
| product_description | Full SQLite description, pictured design colors, current price, and inventory for a real product ID; explicit metadata states that selectable color variants are not recorded. |
| product_price | Actual current price in USD for a real ID. |
| product_stock | Actual quantities by size; zero means out of stock, missing row means that size is not carried. |
| find_alternatives | Different available merchandise in a relevant garment category, constrained by requested size/budget and capped at 12. Does not reserve items. |

Tool calls populate the run's checked-product map. Output validation rejects IDs that were never retrieved, dollar amounts that do not match checked prices or verified search budgets, and detected affirmative color-variant claims such as “available in navy and white.” It also checks common explicit quantity/size statements and size-availability claims against the referenced item's inventory. Named alternatives are checked against their own stock; prices, budgets, and counts introducing search matches are not unit quantities. A rejected answer gets a model retry; repeated failures return an error. These are targeted language guards. Ambiguous product references, spelled-out quantities, and unrecognized wording still require model judgment; the app does not claim a complete formal proof of every sentence. The server rebuilds cards from observed database products, and a performed search uses its actual matches for the page.

## Agent model, safety, and operating limits

The agent loads `backend/prompts/prompt.md` and uses PydanticAI with OpenAI's Responses interface through Portkey. Default: `gpt-5.6-luna`, `https://api.portkey.ai/v1`. `PORTKEY_MODEL` accepts the explicitly listed 5.6/6 course models in agent.py. Keys are loaded from the private hw4/.env; this local course workspace also supports its existing private top-level .env without copying it into the project.

The prompt requires fresh database checks for price, stock, product details, and search. It treats messages, names, product text, paths, and history as untrusted data. The available tools read merchandise only; the model cannot execute SQL, inspect users, change stock, create orders, take payment, expose credentials, or promise unsupported shipping/return policies. The database does not provide inventory by color, so listed graphic colors must not be misrepresented as selectable color variants.

| Limit | Setting |
|---|---|
| Model requests per run | 6 |
| Tool calls per run | 8 |
| Cumulative input/output token budgets | 24,000 / 4,000 |
| Per-response model token setting | 1,800 |
| Structured-output retry allowance | 1 |
| Total agent timeout / tool timeout | 120 seconds / 10 seconds |
| Provider request timeout | 45 seconds; no hidden provider retry |
| Agent search/alternative card cap | 12; default search 6 |
| Catalogue API page size | Default 24, maximum 48 |
| Model history / restored UI history | 20 / 100 latest messages |
| Session lifetime | 7 days |
| Rate limits per client IP, per 60 seconds | 10 registration, 10 login, 20 chat attempts |

## Audit trail

Each run appends run_start, individual tool events, any output_validation retry event, and run_end to `output/audit_trail.json`. Records contain time, run_id, tool_name, short arguments/results, and stop_reason (completed or provider_or_run_failure on terminal events). Validation events identify the color or explicit-stock rule; stock discrepancies retain the product, size, claimed quantity, and actual quantity to explain the retry. Tool results retain IDs, quantities, match counts, or price facts without storing full customer messages. Email-like strings and credential fields are redacted. Failed runs remain visible.

A process lock plus a filesystem lock serialize writers; the file is written to a temporary file and atomically replaced with the old array plus one new record. This preserves existing records and valid JSON. Invalid existing JSON is not silently cleared. It is application-level append-only behavior; there is no claim of tamper-proof external log storage.

## Run and verification

See README.md for data placement, private environment configuration, and commands. Run the backend from backend with `uvicorn main:app --reload --port 8000`, and the frontend from frontend with `npm ci` then `npm run dev -- --host 127.0.0.1`. The frontend is served at http://127.0.0.1:5173.

The final requirement review records actual automated checks and browser observations. Live screenshot evidence is in app_check.html. The source pack already contains accounts and messages; those seed rows are not presented as proof of newly implemented writes. Tests use temporary database copies. Public GitHub publication and Canvas submission are tracked separately from local app verification.
