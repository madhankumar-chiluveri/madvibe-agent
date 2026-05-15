"""Tool registry — single place to import ALL_TOOLS."""

from agent.tools.pages import list_pages, get_page_content, semantic_search, update_page, create_page
from agent.tools.productivity import list_reminders, list_habits
from agent.tools.ledger import list_finance_accounts, get_recent_transactions
from agent.tools.databases import get_database_by_page, list_database_rows, get_database_with_rows

ALL_TOOLS = [
    # Knowledge base
    list_pages,
    get_page_content,
    semantic_search,
    update_page,
    create_page,
    # Databases — read schemas and rows
    get_database_with_rows,   # ← main tool: resolves column names automatically
    get_database_by_page,     # ← get schema only
    list_database_rows,       # ← raw rows by database ID
    # Productivity
    list_reminders,
    list_habits,
    # Finance
    list_finance_accounts,
    get_recent_transactions,
]
