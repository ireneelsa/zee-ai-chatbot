from fastapi import Header, HTTPException

from mock_data import MOCK_BRANDS, MOCK_CREATORS

_BEARER_PREFIX = "Bearer test_"


async def get_current_user(authorization: str = Header(...)):
    if not authorization.startswith(_BEARER_PREFIX):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    account_id = authorization[len(_BEARER_PREFIX):]

    for creator in MOCK_CREATORS:
        if creator["account_id"] == account_id:
            return {**creator, "account_type": "creator"}

    for brand in MOCK_BRANDS:
        if brand["account_id"] == account_id:
            return {**brand, "account_type": "company"}

    raise HTTPException(status_code=401, detail="Unknown account")
