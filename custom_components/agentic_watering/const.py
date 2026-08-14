"""Constants for the Agentic Watering integration."""

DOMAIN = "agentic_watering"

CONF_ENGINE_URL = "engine_url"
CONF_API_TOKEN = "api_token"
CONF_APP_ID = "app_id"
CONF_TTL_SECONDS = "ttl_seconds"
CONF_ENABLED_AGENTS = "enabled_agents"
CONF_ENABLE_WEATHER_MCP = "enable_weather_mcp"
CONF_USE_REACH = "use_reach"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_ENROLL_TOKEN = "enroll_token"

DEFAULT_APP_ID = "agentic-watering"
DEFAULT_ENGINE_URL = "https://172.16.90.20:8765"
DEFAULT_TTL = 3600
DEFAULT_USE_REACH = True
DEFAULT_ENABLE_WEATHER_MCP = True

AGENT_IRRIGATION_PLANNER = "client.irrigation_planner"
AGENT_ZONE_SPECIALIST = "client.irrigation_zone_specialist"
DEFAULT_ENABLED_AGENTS = [
    AGENT_IRRIGATION_PLANNER,
    AGENT_ZONE_SPECIALIST,
]

MCP_WEATHER = "weather_mcp"
DEFAULT_GARDEN_LATITUDE = 41.0137572
DEFAULT_GARDEN_LONGITUDE = -73.8082339

SERVICE_PLAN_ZONE_MINUTES = "plan_zone_minutes"
SERVICE_PROBE_REACH = "probe_reach"
SERVICE_REFRESH_OVERLAY = "refresh_overlay"
SERVICE_PAIR = "pair"
SERVICE_CLEAR_PAIRING = "clear_pairing"
