# Usability improvements

## Front end 1 — Find merchandise without scrolling through everything

The Products page combines a text query, category, size, in-stock status, price ceiling, and sorting. It shows the matching count, gives a clear empty state, and allows filters to be reset. A shopper choosing a gift or looking for a particular size can narrow the actual catalogue before opening details. Availability is taken from the database, including the selected size.

## Front end 2 — A helpful, accessible shop assistant

The floating chat includes starter questions, a visible working state, readable errors, and current-product context. Shoppers can open it from any page and ask about the item they are viewing. Keyboard labels and visible focus make the controls easier to use; compact layouts keep it usable on phones. Product matches remain clickable cards on the page, rather than forcing shoppers to copy product names from a reply.

## Agent/backend 1 — Constrained, affordable product discovery

The catalogue tool accepts a budget, size, and availability constraints in addition to category and search text. Queries are parameterized and results are capped. It can offer relevant available alternatives instead of pretending an unavailable size is in stock. This shortens the path from a vague request to merchandise the shopper can actually choose, while limiting model and database work.

## Agent/backend 2 — Grounded answers with bounded work

Price, descriptions, colors, and quantities come from read-only catalogue tools. The server rebuilds product cards from those observed lookups and validates selected IDs; it does not accept model-invented prices. Model request/tool limits and a timeout keep a conversation bounded. Provider failures produce a clear retry message rather than a made-up answer, helping customers trust the information and controlling operating cost.

See app_check.html for screenshots from the running site and REQUIREMENTS_REVIEW.md for the final verification results.
