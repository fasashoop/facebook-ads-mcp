import json
import os
import httpx
from mcp.server.fastmcp import FastMCP

ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN", "")
AD_ACCOUNT_ID = os.environ.get("FB_AD_ACCOUNT_ID", "")
BASE_URL = "https://graph.facebook.com/v19.0"

mcp = FastMCP("facebook_ads_mcp")

async def fb_get(endpoint, params={}):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{BASE_URL}/{endpoint}", params={"access_token": ACCESS_TOKEN, **params})
        resp.raise_for_status()
        return resp.json()

@mcp.tool()
async def fb_account_summary() -> str:
    """Résumé du compte publicitaire Facebook."""
    try:
        data = await fb_get(AD_ACCOUNT_ID, {"fields": "name,account_status,currency,amount_spent,balance"})
        spent = float(data.get("amount_spent", 0)) / 100
        return f"Compte: {data.get('name')}\nDépensé: {spent:.2f} {data.get('currency')}"
    except Exception as e:
        return f"Erreur: {str(e)}"

@mcp.tool()
async def fb_list_campaigns(status: str = "ACTIVE") -> str:
    """Liste les campagnes Facebook. status: ACTIVE, PAUSED ou ALL."""
    try:
        params = {"fields": "id,name,status,objective,daily_budget", "limit": 10}
        if status != "ALL":
            params["effective_status"] = json.dumps([status])
        data = await fb_get(f"{AD_ACCOUNT_ID}/campaigns", params)
        campaigns = data.get("data", [])
        if not campaigns:
            return "Aucune campagne trouvée."
        lines = []
        for c in campaigns:
            budget = float(c.get("daily_budget", 0)) / 100
            lines.append(f"- {c['name']} | {c.get('status')} | Budget: {budget:.0f}/jour | ID: {c['id']}")
        return "\n".join(lines)
    except Exception as e:
        return f"Erreur: {str(e)}"

@mcp.tool()
async def fb_get_insights(object_id: str, date_preset: str = "last_7d") -> str:
    """Stats d'une campagne. date_preset: today, last_7d, last_30d."""
    try:
        data = await fb_get(f"{object_id}/insights", {"fields": "impressions,clicks,ctr,cpm,spend,reach", "date_preset": date_preset})
        i = data.get("data", [{}])[0]
        return f"Dépenses: {i.get('spend')}$\nImpressions: {i.get('impressions')}\nClics: {i.get('clicks')}\nCTR: {i.get('ctr')}%\nCPM: {i.get('cpm')}$"
    except Exception as e:
        return f"Erreur: {str(e)}"

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
