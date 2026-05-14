import json
import os
import re
import uuid

import llm
from mock_data import MOCK_CAMPAIGNS, MOCK_SUBMISSIONS

from . import ToolError, analyst_tool, coach_tool


_JSON_FENCE_START = re.compile(r"^```(?:json)?\s*", re.IGNORECASE)
_JSON_FENCE_END = re.compile(r"\s*```$", re.IGNORECASE)


def _strip_json_fences(text: str) -> str:
    s = text.strip()
    s = _JSON_FENCE_START.sub("", s)
    s = _JSON_FENCE_END.sub("", s)
    return s.strip()


def _text_from_llm_response(resp: dict) -> str:
    parts: list[str] = []
    for block in resp.get("content") or []:
        if block.get("type") == "text":
            parts.append(block.get("text") or "")
    return "".join(parts).strip()


def _find_submission_for_owner(submission_id: str, account_id: str):
    for sub in MOCK_SUBMISSIONS:
        if sub["id"] != submission_id:
            continue
        for campaign in MOCK_CAMPAIGNS:
            if campaign["id"] == sub["campaign_id"] and campaign["company_account_id"] == account_id:
                return sub, campaign
        break
    return None, None


async def _sonnet_json_object(user_prompt: str, role: str) -> dict:
    system = (
        f"You are a {role}. Output VALID JSON only — no markdown fences."
    )
    resp = await llm.chat(
        messages=[{"role": "user", "content": user_prompt}],
        system=system,
        model=os.environ["ZEE_MODEL_SONNET"],
        tools=None,
        max_tokens=2048,
    )
    raw = _strip_json_fences(_text_from_llm_response(resp))
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ToolError(f"Model returned invalid JSON: {e}") from e


@coach_tool(
    "draft_content_concept",
    {
        "description": (
            "Draft a hook, beats, caption, and hashtags for a campaign using the creator's niche "
            "and baselines. Returns a confirmable draft."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "campaign_id": {"type": "string", "description": "Campaign id like 'camp_001'."},
                "creator_angle": {
                    "type": "string",
                    "description": "Optional angle or note from the creator.",
                    "default": "",
                },
            },
            "required": ["campaign_id"],
        },
    },
)
async def draft_content_concept(args: dict, user: dict) -> dict:
    campaign_id = args["campaign_id"]
    creator_angle = args.get("creator_angle") or ""
    campaign = next((c for c in MOCK_CAMPAIGNS if c["id"] == campaign_id), None)
    if campaign is None:
        raise ToolError(f"Campaign {campaign_id} not found")

    prompt = f"""Campaign (JSON context):
{json.dumps(campaign, indent=2)}

Creator context:
- niche: {user.get("niche")}
- baseline_avg_views: {user.get("baseline_avg_views")}
- display_name: {user.get("display_name")}
- instagram_username: {user.get("instagram_username")}
- creator_angle (optional): {creator_angle or "(none)"}

Return a single JSON object with exactly these keys:
- "hook": one compelling opening line for short video or reel
- "beats": array of 3 to 5 short bullet strings (story beats)
- "caption": string under 150 characters (not including hashtags in the count)
- "hashtags": array of hashtag strings including # where appropriate

Do not include markdown. Do not include a draft_id or actions (the server adds those)."""

    parsed = await _sonnet_json_object(prompt, "social media content coach for creator marketing")
    draft_id = str(uuid.uuid4())
    actions = [
        {"label": "Use this", "action": "handoff_to_obula"},
        {"label": "Refine", "action": "refine"},
    ]
    return {
        "draft_id": draft_id,
        "hook": parsed.get("hook"),
        "beats": parsed.get("beats"),
        "caption": parsed.get("caption"),
        "hashtags": parsed.get("hashtags"),
        "actions": actions,
    }


@coach_tool(
    "suggest_profile_improvements",
    {
        "description": (
            "Suggest profile strengths, gaps, and top actions using the creator's profile and baselines. "
            "Returns a confirmable draft."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
)
async def suggest_profile_improvements(args: dict, user: dict) -> dict:
    profile = {
        "display_name": user.get("display_name"),
        "instagram_username": user.get("instagram_username"),
        "niche": user.get("niche"),
        "baseline_avg_views": user.get("baseline_avg_views"),
        "baseline_avg_like_rate": user.get("baseline_avg_like_rate"),
        "baseline_avg_comment_rate": user.get("baseline_avg_comment_rate"),
        "ig_post_count": user.get("ig_post_count"),
        "ig_oldest_post_at": user.get("ig_oldest_post_at"),
        "fraud_flag_count": user.get("fraud_flag_count"),
    }
    prompt = f"""Creator profile (JSON):
{json.dumps(profile, indent=2)}

Return a single JSON object with exactly these keys:
- "strengths": array of short strings
- "gaps": array of short strings
- "top_3_actions": array of exactly 3 objects, each with "action" (string) and "why" (string)

Do not include markdown. Do not include draft_id or actions."""

    parsed = await _sonnet_json_object(prompt, "creator growth coach specializing in Instagram performance")
    draft_id = str(uuid.uuid4())
    actions = [{"label": "Apply suggestions", "action": "apply_profile_changes"}]
    return {
        "draft_id": draft_id,
        "strengths": parsed.get("strengths"),
        "gaps": parsed.get("gaps"),
        "top_3_actions": parsed.get("top_3_actions"),
        "actions": actions,
    }


@analyst_tool(
    "draft_campaign_brief",
    {
        "description": (
            "Draft a campaign brief (name, description, Do's, Don'ts, hashtags, suggested payout and "
            "minimum views) from a goal and brand context. Returns a confirmable draft."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "What the brand wants to achieve."},
                "category": {"type": "string", "description": "Optional category.", "default": ""},
                "budget": {"type": "number", "description": "Optional total budget hint."},
            },
            "required": ["goal"],
        },
    },
)
async def draft_campaign_brief(args: dict, user: dict) -> dict:
    goal = args["goal"]
    category = args.get("category") or ""
    budget = args.get("budget")
    brand = {
        "company_name": user.get("company_name"),
        "company_niche": user.get("company_niche"),
    }
    prompt = f"""Brand context (JSON):
{json.dumps(brand, indent=2)}

Campaign inputs:
- goal: {goal}
- category (optional): {category or "(none)"}
- budget hint (optional): {json.dumps(budget)}

Return a single JSON object with exactly these keys:
- "name": short campaign name
- "description": exactly two sentences as one string
- "Do_s": array of strings (best practices for creators)
- "Don_ts": array of strings (things to avoid)
- "mandatory_hashtags": array of hashtag strings
- "suggested_payout_per_1000_views": number (reasonable payout in same currency units as typical marketplace examples)
- "suggested_minimum_views_required": integer

Do not include markdown. Do not include draft_id or actions."""

    parsed = await _sonnet_json_object(prompt, "campaign strategist for influencer and UGC programs")
    draft_id = str(uuid.uuid4())
    actions = [
        {"label": "Save to campaign", "action": "create_campaign"},
        {"label": "Edit", "action": "refine"},
    ]
    return {
        "draft_id": draft_id,
        "name": parsed.get("name"),
        "description": parsed.get("description"),
        "Do_s": parsed.get("Do_s"),
        "Don_ts": parsed.get("Don_ts"),
        "mandatory_hashtags": parsed.get("mandatory_hashtags"),
        "suggested_payout_per_1000_views": parsed.get("suggested_payout_per_1000_views"),
        "suggested_minimum_views_required": parsed.get("suggested_minimum_views_required"),
        "actions": actions,
    }


@analyst_tool(
    "explain_submission_decision",
    {
        "description": (
            "Draft a plain-language approval recommendation for a submission on an owned campaign, "
            "with signals and concerns. Returns a confirmable draft."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"submission_id": {"type": "string"}},
            "required": ["submission_id"],
        },
    },
)
async def explain_submission_decision(args: dict, user: dict) -> dict:
    submission_id = args["submission_id"]
    sub, campaign = _find_submission_for_owner(submission_id, user["account_id"])
    if sub is None:
        raise ToolError(f"404: submission {submission_id} not found or not owned")

    context = {
        "submission": sub,
        "campaign": {
            "id": campaign["id"],
            "name": campaign["name"],
            "category": campaign["category"],
            "description": campaign["description"],
            "Do_s": campaign.get("Do_s"),
            "Don_ts": campaign.get("Don_ts"),
            "mandatory_hashtags": campaign.get("mandatory_hashtags"),
            "minimum_views_required": campaign.get("minimum_views_required"),
        },
    }
    prompt = f"""You are helping a brand manager decide on a creator submission.

Context (JSON):
{json.dumps(context, indent=2)}

Return a single JSON object with exactly these keys:
- "summary": one or two sentences in plain language
- "positive_signals": array of short strings
- "concerns": array of short strings (empty if none)
- "recommendation": one of the strings "approve", "reject", or "review_manually"
- "confidence": number between 0.0 and 1.0

Base the recommendation on fraud score, flags, engagement vs campaign minimums, and fit with campaign rules.

Do not include markdown. Do not include draft_id or actions."""

    parsed = await _sonnet_json_object(
        prompt,
        "brand safety and influencer campaign analyst",
    )
    draft_id = str(uuid.uuid4())
    actions = [
        {"label": "Approve", "action": "approve_submission"},
        {"label": "Reject", "action": "reject_submission"},
    ]
    return {
        "draft_id": draft_id,
        "summary": parsed.get("summary"),
        "positive_signals": parsed.get("positive_signals"),
        "concerns": parsed.get("concerns"),
        "recommendation": parsed.get("recommendation"),
        "confidence": parsed.get("confidence"),
        "actions": actions,
    }
