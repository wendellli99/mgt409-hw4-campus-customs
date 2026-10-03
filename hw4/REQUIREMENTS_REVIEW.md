# Homework 4 requirements review

Reviewed the scenario and all thirteen problem pages, including Panels A and B for Problems 1–12. Problem 13 is unsplit. Embedded AI Instructions, agent notes, hidden directions, and traps were excluded from the task requirements at the user's request.

| Problem | Required outcome | Evidence / status |
|---|---|---|
| 1. Prompts | Prompt file by problem with prompts and follow-ups | AI_prompts.md contains the assignment-wide user request, four prepared working prompts per problem (52 total), and observed review corrections. These are reusable prompts, not a transcript of separately typed student messages. The assignment's historical-prompt requirement remains for student review. |
| 2. Database | Actual schema and field purposes | output/harness.md records every field in catalogue, inventory, users, and existing chat_messages directly from SQLite, plus the added sessions table. |
| 3. Storefront | Vite React TypeScript, five nav pages, database products, clickable details, chat | Running Home, Products, About Us, Log in, and Create account pages; live product photos and details; bottom-right chat. Desktop and 390px mobile checks pass. |
| 4. Accounts | Secure hashes; seed and new-user login; harness | Seed login works. A test-only new account was created through the UI, its salted 600,000-round PBKDF2 hash verified, then logged out and back in. Confirmation mismatch and server validation tested. |
| 5. Agent | FastAPI, four agent files, real chat, model/prompt loading | Required files are present; actual Portkey/PydanticAI model calls answered browser questions. Provider errors return a safe error, without a fabricated success reply. |
| 6. Tools | Real description, price, size stock; honest out-of-stock answers | Live contextual Champion hoodie lookup returned $68 and XS quantity 0. A fresh color question correctly distinguishes pictured colors from unrecorded variants. |
| 7. Search cards | Structured search matches update page; detail links | Live “Show me hoodies” displayed 12 capped matches. Clicking a main-page match opened its database detail and size quantities. |
| 8. Memory | Per-user DB history, signed-in identity, current item context | New-user budget conversation survived logout and login; saved history and personalized name rendered. Automated tests verify history isolation and server-derived identity. Product-page questions resolve the current item. |
| 9. Usability | Two implemented frontend and two backend improvements | output/usability.md describes catalogue filters, accessible contextual chat, constrained search, and bounded grounded agent work. Live XS/in-stock/$70 filters returned 20 matching hoodies. |
| 10. Style | Creative storefront styling and design explanation | Navy/ivory/gold editorial design and merchandise hero; responsive cards; keyboard focus and reduced-motion support. output/design.md explains the choices. |
| 11. App check | Three labeled real screenshots and relative image links | output/app_check.html contains seven screenshots, including all three required situations. All relative links resolve to real PNG files. |
| 12. Audit/safety | Retained audit records, safety prompt, complete harness | Actual live runs retain start, tools, and terminal stop reasons in output/audit_trail.json. The safety prompt and harness document schema, APIs, dependencies, models, tools, limits, grounding, and logging. |
| 13. GitHub/Canvas | Public GitHub repo with hw4 tree; no secret/data files; URL on Canvas | Published at https://github.com/wendellli99/mgt409-hw4-campus-customs. Anonymous cloning and every tracked-file hash were verified; the required hw4 tree is public and original data/secrets are excluded. Canvas submission has not been performed. |

## Verification performed October 3, 2026

- **24 backend tests passed.** Tests use temporary database copies and a deterministic PydanticAI FunctionModel for failure/grounding regressions; they are separate from live model evidence. Coverage includes seed and new accounts, password hashing, session lifecycle, account isolation, contextual identity, parameterized filters, bounded agent runs, output validation, retained/redacted audit events, and provider-failure behavior.
- **Production frontend build passed**, including TypeScript compilation. The dependency check reported no broken Python requirements. The test runner emits one upstream Python 3.14 asyncio deprecation warning.
- **Live model and browser checks passed** for stock, category search, clickable matches, price/size filters, account creation, returning history, contextual questions, and mobile layout. No simulated provider reply is presented as live evidence.
- **Corrections from review:** Home initially requested a catalogue limit above the API maximum; it now retrieves its four featured items directly. Chat input length now matches the API's 2,000-character limit. Color descriptions no longer imply selectable variants; a targeted output guard retries detected false color-availability claims.
- **Data boundaries:** the original catalogue/inventory data and product photographs remain local. The database acquired only application session/history/account writes. Public screenshots include a test-only account and required product views; the original database, image directory, data pack, keys, and generated dependencies are excluded.

- **Public repository verified:** an anonymous clone of implementation commit `d1fb9ae39f3b9c4013994896086744452b1661d9` reproduced all 36 staged files byte for byte. A subsequent documentation commit records this result. Git exclusions and the public-file scan passed.

## Remaining student actions

Review the prepared prompts and the work before submission. If the instructor expects a literal history of independently typed prompts, these drafts do not establish that history. Submit the public repository URL through Canvas; this project preparation does not submit the assignment automatically.
