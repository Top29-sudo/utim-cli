"""
UTIM Terminal Web Application State & Layout Engine
----------------------------------------------------
Provides a stateful, interactive, multi-pane terminal web app experience for the UTIM Marketplace.
"""

from __future__ import annotations

import dataclasses
from typing import Any, List, Dict, Optional, Tuple, Callable


@dataclasses.dataclass
class SidebarItem:
    id: str
    section: str  # 'DISCOVER' | 'LIBRARY' | 'CATEGORIES' | 'CREATOR'
    label: str
    icon: str
    action_type: str  # 'nav' | 'category' | 'my_items' | 'publish' | 'wallet'
    value: str = ""


SIDEBAR_SECTIONS = [
    SidebarItem("home", "DISCOVER", "Home", "", "nav", "home"),
    SidebarItem("explore", "DISCOVER", "Explore Catalog", "", "nav", "explore"),
    SidebarItem("new_releases", "DISCOVER", "New Releases", "", "nav", "new"),
    SidebarItem("popular", "DISCOVER", "Popular Community", "", "nav", "popular"),
    SidebarItem("top_rated", "DISCOVER", "Top Rated", "", "nav", "top_rated"),

    SidebarItem("cat_all", "CATEGORIES", "All Categories", "", "category", "all"),
    SidebarItem("cat_prod", "CATEGORIES", "Productivity", "", "category", "productivity"),
    SidebarItem("cat_coding", "CATEGORIES", "Coding & Dev", "", "category", "coding"),
    SidebarItem("cat_ai", "CATEGORIES", "AI & Agents", "", "category", "ai"),
    SidebarItem("cat_writing", "CATEGORIES", "Writing & Docs", "", "category", "writing"),
    SidebarItem("cat_data", "CATEGORIES", "Data & Analysis", "", "category", "data"),
    SidebarItem("cat_devops", "CATEGORIES", "DevOps & Shell", "", "category", "devops"),
    SidebarItem("cat_design", "CATEGORIES", "Design & UI", "", "category", "design"),
    SidebarItem("cat_research", "CATEGORIES", "Research", "", "category", "research"),

    SidebarItem("my_items", "CREATOR", "My Extensions", "", "my_items", ""),
    SidebarItem("publish", "CREATOR", "Publish Extension", "＋", "publish", ""),
    SidebarItem("seller_hub", "CREATOR", "Seller Hub & Wallet", "", "wallet", ""),
    SidebarItem("verified", "TRUST & SAFETY", "Verified Publishers", "✓", "nav", "verified"),
]


@dataclasses.dataclass
class MarketplaceAppState:
    active_panel: str = "sidebar"  # 'sidebar' | 'content' | 'topbar'
    active_nav: str = "home"
    selected_sidebar_idx: int = 0
    selected_content_idx: int = 0

    search_query: str = ""
    category: str = "all"
    sort: str = "featured"

    home_data: Dict[str, Any] = dataclasses.field(default_factory=dict)
    listings: List[Dict[str, Any]] = dataclasses.field(default_factory=list)
    selected_item: Optional[Dict[str, Any]] = None

    loading: bool = False
    error: Optional[str] = None
