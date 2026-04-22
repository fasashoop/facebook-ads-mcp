"""
Facebook Ads MCP Server - v2
Compatible Railway deployment
"""

import json
import os
import httpx
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# ─── Config ───────────────────────────────────────────────────────────────────
ACCESS_TOKEN = os.environ.get("FB_ACCESS_TOKEN", "")
AD_ACCOUNT_ID = os.environ.get("FB_AD_ACCOUNT_ID", "")
API_VERSION = "v19.0"
BASE_URL = f"https://graph.facebook.com/{API_VERSION}"

mcp = FastMCP("facebook_ads_mcp")

# ─── Helper ───────────────────────────────────────────────────────────────────
async def fb_get(endpoint: str, params: dict = {}) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{BASE_URL}/{endpoint}",
            params={"access_token": ACCESS_TOKEN, **params}
        )
        resp.raise_for_status()
        return resp.json()

# ─── Tools ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def fb_account_summary() -> str:
    """Résumé du compte publicitaire Facebook: nom, statut, dépenses, solde."""
    try:
        data = await fb_get(AD_ACCOUNT_ID, {
            "fields": "name,account_status,currency,amount_spent,balance"
        })
        status_map = {1: "✅ Actif", 2: "⛔ Désactivé", 9: "🔒 Fermé"}
        status = status_map.get(data.get("account_status", 0), "❓ Inconnu")
        currency = data.get("currency", "USD")
        spent = float(data.get("amount_spent", 0)) / 100
        balance = float(data.get("balance", 0)) / 100
        return (
            f"🏢 {data.get('name', 'Compte Pub')}\n"
            f"Statut: {status}\n"
            f"Devise: {currency}\n"
            f"Total dépensé: {spent:.2f} {currency}\n"
            f"Solde: {balance:.2f} {currency}"
        )
    except Exception as e:
        return f"❌ Erreur: {str(e)}"


@mcp.tool()
async def fb_list_campaigns(status: str = "ACTIVE", limit: int = 10) -> str:
    """Liste les campagnes Facebook. status: ACTIVE, PAUSED, ARCHIVED ou ALL."""
    try:
        params = {
            "fields": "id,name,status,objective,daily_budget,lifetime_budget",
            "limit": limit,
        }
        if status != "ALL":
            params["effective_status"] = json.dumps([status])

        data = await fb_get(f"{AD_ACCOUNT_ID}/campaigns", params)
        campaigns = data.get("data", [])

        if not campaigns:
            return "Aucune campagne trouvée."

        lines = [f"📊 {len(campaigns)} campagne(s):\n"]
        for c in campaigns:
            budget_val = c.get("daily_budget") or c.get("lifetime_budget", "0")
            budget = f"{float(budget_val)/100:.0f}"
            btype = "jour" if c.get("daily_budget") else "total"
            lines.append(
                f"🎯 {c['name']}\n"
                f"   ID: {c['id']}\n"
                f"   Statut: {c.get('status')} | Objectif: {c.get('objective')}\n"
                f"   Budget: {budget} ({btype})\n"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Erreur: {str(e)}"


@mcp.tool()
async def fb_get_insights(object_id: str, date_preset: str = "last_7d") -> str:
    """Stats d'une campagne/adset/pub. date_preset: today, last_7d, last_30d, this_month."""
    try:
        fields = "impressions,clicks,ctr,cpm,spend,reach,frequency,actions"
        data = await fb_get(f"{object_id}/insights", {
            "fields": fields,
            "date_preset": date_preset,
        })
        insights = data.get("data", [])
        if not insights:
            return f"Pas de données pour {date_preset}."

        i = insights[0]
        spend = float(i.get("spend", 0))
        actions = {a["action_type"]: float(a["value"]) for a in i.get("actions", [])}
        leads = actions.get("lead", actions.get("onsite_conversion.lead_grouped", 0))
        messages = actions.get("onsite_conversion.messaging_conversation_started_7d", 0)
        cpl = spend / leads if leads > 0 else 0

        lines = [
            f"📈 Insights — {date_preset}\n",
            f"💰 Dépenses:    {spend:.2f} $",
            f"👁️  Impressions: {int(i.get('impressions', 0)):,}",
            f"📢 Portée:      {int(i.get('reach', 0)):,}",
            f"🖱️  Clics:       {int(i.get('clicks', 0)):,}",
            f"📊 CTR:         {float(i.get('ctr', 0)):.2f}%",
            f"💵 CPM:         {float(i.get('cpm', 0)):.2f} $",
            f"🔁 Fréquence:   {float(i.get('frequency', 0)):.2f}",
            f"📬 Leads:       {leads:.0f}",
            f"💬 Messages:    {messages:.0f}",
        ]
        if leads > 0:
            lines.append(f"🎯 CPL:         {cpl:.2f} $")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Erreur: {str(e)}"


@mcp.tool()
async def fb_list_adsets(campaign_id: str) -> str:
    """Liste les ad sets d'une campagne Facebook."""
    try:
        data = await fb_get(f"{campaign_id}/adsets", {
            "fields": "id,name,status,daily_budget,optimization_goal",
            "limit": 20
        })
        adsets = data.get("data", [])
        if not adsets:
            return "Aucun ad set trouvé."

        lines = [f"🗂️ {len(adsets)} Ad Set(s):\n"]
        for a in adsets:
            budget = f"{float(a.get('daily_budget', 0))/100:.0f}"
            lines.append(
                f"📁 {a['name']}\n"
                f"   ID: {a['id']} | Statut: {a.get('status')}\n"
                f"   Budget/jour: {budget} | Optim: {a.get('optimization_goal')}\n"
            )
        return "\n".join(lines)
    except Exception as e:
        return f"❌ Erreur: {str(e)}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="streamable-http", host="0.0.0.0", port=port)
