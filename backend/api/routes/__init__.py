from .auth import router as auth_router
from .config import router as config_router
from .device import router as device_router
from .discover import router as discover_router
from .firmware import router as firmware_router
from .locations import router as locations_router
from .mobile import router as mobile_router
from .modes import router as modes_router
from .pages import router as pages_router
from .render import router as render_router
from .stats import router as stats_router
from .user import router as user_router

api_routers = [
    render_router,
    config_router,
    device_router,
    modes_router,
    auth_router,
    user_router,
    mobile_router,
    stats_router,
    firmware_router,
    discover_router,
    locations_router,
]

page_routers = [pages_router]
