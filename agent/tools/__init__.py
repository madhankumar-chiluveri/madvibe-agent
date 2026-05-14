"""Tool registry — single place to import ALL_TOOLS."""

from agent.tools.pages import list_pages, get_page_content, semantic_search, update_page, create_page
from agent.tools.productivity import list_reminders, list_habits
from agent.tools.ledger import list_finance_accounts, get_recent_transactions

ALL_TOOLS = [
    # Knowledge base
    list_pages,
    get_page_content,
    semantic_search,
    update_page,
    create_page,
    # Productivity
    list_reminders,
    list_habits,
    # Finance
    list_finance_accounts,
    get_recent_transactions,
]
