from mock_data import MOCK_CAMPAIGNS, MOCK_SUBMISSIONS

from . import ToolError, coach_tool


def _baselines(user: dict) -> dict:
    return {
        "avg_views": user.get("baseline_avg_views"),
        "avg_like_rate": user.get("baseline_avg_like_rate"),
        "avg_comment_rate": user.get("baseline_avg_comment_rate"),
    }


def _slim_open_campaign(campaign: dict) -> dict:
    return {
        "id": campaign["id"],
        "name": campaign["name"],
        "category": campaign["category"],
        "description": campaign["description"],
        "payout_amount": campaign["payout_amount"],
        "payout_views_denominator": campaign["payout_views_denominator"],
        "minimum_views_required": campaign["minimum_views_required"],
        "mandatory_hashtags": campaign["mandatory_hashtags"],
        "end_date": campaign["end_date"],
    }


@coach_tool(
    "get_my_profile",
    {
        "description": "Get the current creator's profile, including niche and engagement baselines.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def get_my_profile(args: dict, user: dict) -> dict:
    return {
        "display_name": user.get("display_name"),
        "instagram_username": user.get("instagram_username"),
        "niche": user.get("niche"),
        "baselines": _baselines(user),
        "ig_post_count": user.get("ig_post_count"),
        "ig_oldest_post_at": user.get("ig_oldest_post_at"),
        "fraud_flag_count": user.get("fraud_flag_count"),
    }


@coach_tool(
    "list_open_campaigns",
    {
        "description": "List campaigns currently open for creator submissions.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of campaigns to return.",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
)
async def list_open_campaigns(args: dict, user: dict) -> dict:
    limit = args.get("limit", 10)
    open_campaigns = [
        c for c in MOCK_CAMPAIGNS
        if c.get("approval_status") == "approved" and c.get("visible_to_users") is True
    ]
    return {"campaigns": [_slim_open_campaign(c) for c in open_campaigns[:limit]]}


@coach_tool(
    "get_campaign_details",
    {
        "description": "Get full details for a single campaign by id.",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string", "description": "Campaign id like 'camp_001'."}
            },
            "required": ["campaign_id"],
        },
    },
)
async def get_campaign_details(args: dict, user: dict) -> dict:
    campaign_id = args["campaign_id"]
    for campaign in MOCK_CAMPAIGNS:
        if campaign["id"] == campaign_id:
            return dict(campaign)
    raise ToolError(f"Campaign {campaign_id} not found")


@coach_tool(
    "get_my_submissions",
    {
        "description": "List all submissions made by the current creator.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def get_my_submissions(args: dict, user: dict) -> dict:
    account_id = user["account_id"]
    submissions = [
        dict(s) for s in MOCK_SUBMISSIONS if s["user_account_id"] == account_id
    ]
    return {"submissions": submissions}


@coach_tool(
    "get_my_payouts",
    {
        "description": "Get payout status for each of the current creator's submissions.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def get_my_payouts(args: dict, user: dict) -> dict:
    account_id = user["account_id"]
    campaigns_by_id = {c["id"]: c for c in MOCK_CAMPAIGNS}
    payouts = []
    for sub in MOCK_SUBMISSIONS:
        if sub["user_account_id"] != account_id:
            continue
        campaign = campaigns_by_id.get(sub["campaign_id"])
        payout = sub.get("payout")
        payouts.append({
            "submission_id": sub["id"],
            "campaign_id": sub["campaign_id"],
            "campaign_name": campaign["name"] if campaign else None,
            "amount": payout["approved_payout_amount"] if payout else None,
            "status": payout["payout_status"] if payout else None,
        })
    return {"payouts": payouts}


@coach_tool(
    "get_my_baselines",
    {
        "description": "Get the current creator's engagement baselines (avg views, like rate, comment rate).",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def get_my_baselines(args: dict, user: dict) -> dict:
    return _baselines(user)
