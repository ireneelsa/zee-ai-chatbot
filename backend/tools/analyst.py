from mock_data import MOCK_CAMPAIGNS, MOCK_CREATORS, MOCK_SUBMISSIONS

from . import ToolError, analyst_tool


def _slim_analyst_campaign(campaign: dict) -> dict:
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
        "total_budget": campaign["total_budget"],
        "budget_consumed": campaign["budget_consumed"],
        "approval_status": campaign["approval_status"],
        "visible_to_users": campaign["visible_to_users"],
    }


def _owned_campaign(campaign_id: str, account_id: str) -> dict:
    for campaign in MOCK_CAMPAIGNS:
        if campaign["id"] == campaign_id and campaign["company_account_id"] == account_id:
            return campaign
    raise ToolError(f"404: campaign {campaign_id} not found or not owned")


@analyst_tool(
    "get_my_campaigns",
    {
        "description": "List all campaigns owned by the current brand.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def get_my_campaigns(args: dict, user: dict) -> dict:
    account_id = user["account_id"]
    campaigns = [
        _slim_analyst_campaign(c) for c in MOCK_CAMPAIGNS
        if c["company_account_id"] == account_id
    ]
    return {"campaigns": campaigns}


@analyst_tool(
    "get_campaign_overview",
    {
        "description": "Get a single owned campaign with submission status counts.",
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
)
async def get_campaign_overview(args: dict, user: dict) -> dict:
    campaign = _owned_campaign(args["campaign_id"], user["account_id"])
    counts = {"approved": 0, "pending": 0, "rejected": 0}
    for sub in MOCK_SUBMISSIONS:
        if sub["campaign_id"] != campaign["id"]:
            continue
        status = sub["submission_status"]
        if status in counts:
            counts[status] += 1
    return {"campaign": dict(campaign), "submission_counts": counts}


@analyst_tool(
    "get_campaign_analytics",
    {
        "description": "Aggregate submission, engagement, and spend metrics for an owned campaign.",
        "input_schema": {
            "type": "object",
            "properties": {"campaign_id": {"type": "string"}},
            "required": ["campaign_id"],
        },
    },
)
async def get_campaign_analytics(args: dict, user: dict) -> dict:
    campaign = _owned_campaign(args["campaign_id"], user["account_id"])

    submissions_total = 0
    by_status = {"approved": 0, "pending": 0, "rejected": 0}
    total_views = 0
    total_likes = 0
    total_comments = 0
    payout_total = 0

    for sub in MOCK_SUBMISSIONS:
        if sub["campaign_id"] != campaign["id"]:
            continue
        submissions_total += 1
        status = sub["submission_status"]
        if status in by_status:
            by_status[status] += 1
        snap = sub.get("latest_snapshot") or {}
        total_views += snap.get("view_count", 0)
        total_likes += snap.get("like_count", 0)
        total_comments += snap.get("comment_count", 0)
        payout = sub.get("payout")
        if payout:
            payout_total += payout.get("approved_payout_amount", 0)

    return {
        "submissions": {"total": submissions_total, **by_status},
        "metrics": {
            "total_views": total_views,
            "total_likes": total_likes,
            "total_comments": total_comments,
        },
        "spend": {
            "budget_consumed": campaign["budget_consumed"],
            "payout_total": payout_total,
            "total_budget": campaign["total_budget"],
        },
    }


@analyst_tool(
    "get_campaign_submissions",
    {
        "description": "List submissions for an owned campaign.",
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string"},
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["campaign_id"],
        },
    },
)
async def get_campaign_submissions(args: dict, user: dict) -> dict:
    campaign = _owned_campaign(args["campaign_id"], user["account_id"])
    limit = args.get("limit", 20)
    submissions = []
    for sub in MOCK_SUBMISSIONS:
        if sub["campaign_id"] != campaign["id"]:
            continue
        submissions.append({
            "id": sub["id"],
            "user_account_id": sub["user_account_id"],
            "submission_status": sub["submission_status"],
            "fraud_score": sub["fraud_score"],
            "fraud_flags": sub["fraud_flags"],
            "latest_snapshot": sub.get("latest_snapshot"),
            "payout": sub.get("payout"),
        })
        if len(submissions) >= limit:
            break
    return {"submissions": submissions}


def _find_submission_for_owner(submission_id: str, account_id: str):
    for sub in MOCK_SUBMISSIONS:
        if sub["id"] != submission_id:
            continue
        for campaign in MOCK_CAMPAIGNS:
            if campaign["id"] == sub["campaign_id"] and campaign["company_account_id"] == account_id:
                return sub, campaign
        break
    return None, None


@analyst_tool(
    "get_submission_review_signals",
    {
        "description": "Get review signals (creator baselines, fraud flags, latest metrics) for a submission to an owned campaign.",
        "input_schema": {
            "type": "object",
            "properties": {"submission_id": {"type": "string"}},
            "required": ["submission_id"],
        },
    },
)
async def get_submission_review_signals(args: dict, user: dict) -> dict:
    submission_id = args["submission_id"]
    sub, _campaign = _find_submission_for_owner(submission_id, user["account_id"])
    if sub is None:
        raise ToolError(f"404: submission {submission_id} not found or not owned")

    creator = next(
        (c for c in MOCK_CREATORS if c["account_id"] == sub["user_account_id"]),
        None,
    )
    creator_baselines = None
    if creator is not None:
        creator_baselines = {
            "avg_views": creator["baseline_avg_views"],
            "avg_like_rate": creator["baseline_avg_like_rate"],
            "avg_comment_rate": creator["baseline_avg_comment_rate"],
        }

    return {
        "submission": {
            "id": sub["id"],
            "campaign_id": sub["campaign_id"],
            "user_account_id": sub["user_account_id"],
            "platform": sub["platform"],
            "content_link": sub["content_link"],
            "submission_status": sub["submission_status"],
        },
        "creator_baselines": creator_baselines,
        "fraud": {
            "score": sub["fraud_score"],
            "flags": sub["fraud_flags"],
        },
        "metrics": sub.get("latest_snapshot"),
    }


@analyst_tool(
    "get_creator_profile",
    {
        "description": "Get public profile of a creator who has submitted to one of the current brand's campaigns.",
        "input_schema": {
            "type": "object",
            "properties": {"account_id": {"type": "string"}},
            "required": ["account_id"],
        },
    },
)
async def get_creator_profile(args: dict, user: dict) -> dict:
    target_account_id = args["account_id"]
    owned_campaign_ids = {
        c["id"] for c in MOCK_CAMPAIGNS if c["company_account_id"] == user["account_id"]
    }
    has_submitted = any(
        sub["user_account_id"] == target_account_id and sub["campaign_id"] in owned_campaign_ids
        for sub in MOCK_SUBMISSIONS
    )
    if not has_submitted:
        raise ToolError(f"403: creator {target_account_id} has not submitted to your campaigns")

    creator = next(
        (c for c in MOCK_CREATORS if c["account_id"] == target_account_id),
        None,
    )
    if creator is None:
        raise ToolError(f"404: creator {target_account_id} not found")

    return {
        "display_name": creator["display_name"],
        "instagram_username": creator["instagram_username"],
        "baselines": {
            "avg_views": creator["baseline_avg_views"],
            "avg_like_rate": creator["baseline_avg_like_rate"],
            "avg_comment_rate": creator["baseline_avg_comment_rate"],
        },
        "ig_post_count": creator["ig_post_count"],
        "ig_oldest_post_at": creator["ig_oldest_post_at"],
        "fraud_flag_count": creator["fraud_flag_count"],
    }
