"""
IBAN Decoder API。

IBAN番号を検証し、国コード・チェックディジット・BBAN(国内口座部分)に
分解して返す。ISO 13616 のチェックサム(mod-97)はアルゴリズムのみで
検証可能なので外部データ不要。国別のBBAN内訳(銀行コード等)は、
主要国のみ公開仕様(SWIFT IBAN Registry)に基づく固定テーブルを持つ。
"""

import re

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="IBAN Decoder API",
    description="IBAN番号を検証し、国コード・銀行コード等に分解します。",
    version="1.0.0",
)

# 国別のIBAN全長(桁数)。SWIFT IBAN Registry に基づく主要国一覧。
IBAN_LENGTHS = {
    "AD": 24, "AE": 23, "AT": 20, "AZ": 28, "BA": 20, "BE": 16, "BG": 22,
    "BH": 22, "BR": 29, "CH": 21, "CR": 22, "CY": 28, "CZ": 24, "DE": 22,
    "DK": 18, "DO": 28, "EE": 20, "EG": 29, "ES": 24, "FI": 18, "FO": 18,
    "FR": 27, "GB": 22, "GE": 22, "GI": 23, "GL": 18, "GR": 27, "GT": 28,
    "HR": 21, "HU": 28, "IE": 22, "IL": 23, "IQ": 23, "IS": 26, "IT": 27,
    "JO": 30, "KW": 30, "KZ": 20, "LB": 28, "LC": 32, "LI": 21, "LT": 20,
    "LU": 20, "LV": 21, "MC": 27, "MD": 24, "ME": 22, "MK": 19, "MR": 27,
    "MT": 31, "MU": 30, "NL": 18, "NO": 15, "PK": 24, "PL": 28, "PS": 29,
    "PT": 25, "QA": 29, "RO": 24, "RS": 22, "SA": 24, "SC": 31, "SE": 24,
    "SI": 19, "SK": 24, "SM": 27, "ST": 25, "SV": 28, "TL": 23, "TN": 24,
    "TR": 26, "UA": 29, "VA": 22, "VG": 24, "XK": 20,
}

# 主要国のBBAN内訳(銀行コード / 支店コード / 口座番号の桁位置)。
# ここに無い国は、有効なIBANでもBBANの内訳までは返さない。
BBAN_LAYOUTS = {
    "DE": [("bank_code", 8), ("account_number", 10)],
    "GB": [("bank_code", 4), ("sort_code", 6), ("account_number", 8)],
    "FR": [("bank_code", 5), ("branch_code", 5), ("account_number", 11), ("national_check", 2)],
    "IT": [("check_char", 1), ("bank_code", 5), ("branch_code", 5), ("account_number", 12)],
    "ES": [("bank_code", 4), ("branch_code", 4), ("check_digits", 2), ("account_number", 10)],
    "NL": [("bank_code", 4), ("account_number", 10)],
    "BE": [("bank_code", 3), ("account_number", 7), ("national_check", 2)],
    "CH": [("bank_code", 5), ("account_number", 12)],
    "AT": [("bank_code", 5), ("account_number", 11)],
    "PT": [("bank_code", 4), ("branch_code", 4), ("account_number", 11), ("national_check", 2)],
}


def _mod97_valid(iban: str) -> bool:
    """ISO 13616 のチェックサム検証。先頭4文字を末尾に回し、
    文字を数字(A=10..Z=35)に変換した数値がmod97で1になれば有効。"""
    rearranged = iban[4:] + iban[:4]
    digits = "".join(str(int(c, 36)) if c.isalpha() else c for c in rearranged)
    return int(digits) % 97 == 1


def decode_iban(raw: str) -> dict:
    iban = re.sub(r"\s+", "", raw).upper()

    if not re.fullmatch(r"[A-Z0-9]+", iban):
        return {"valid": False, "reason": "英数字以外の文字が含まれています"}

    country_code = iban[:2]
    if country_code not in IBAN_LENGTHS:
        return {"valid": False, "reason": f"未知の国コードです: {country_code}"}

    expected_len = IBAN_LENGTHS[country_code]
    if len(iban) != expected_len:
        return {
            "valid": False,
            "reason": f"{country_code} のIBANは{expected_len}桁である必要があります(入力は{len(iban)}桁)",
        }

    if not _mod97_valid(iban):
        return {"valid": False, "reason": "チェックサム(mod-97)が一致しません"}

    check_digits = iban[2:4]
    bban = iban[4:]

    result = {
        "valid": True,
        "country_code": country_code,
        "check_digits": check_digits,
        "bban": bban,
    }

    layout = BBAN_LAYOUTS.get(country_code)
    if layout:
        pos = 0
        breakdown = {}
        for field_name, length in layout:
            breakdown[field_name] = bban[pos:pos + length]
            pos += length
        result["bban_breakdown"] = breakdown
    else:
        result["bban_breakdown"] = None

    return result


class DecodeRequest(BaseModel):
    iban: str = Field(..., min_length=4, max_length=40, description="検証したいIBAN番号")


@app.get("/")
def root():
    return {"status": "ok", "service": "iban-decoder"}


@app.get("/health")
@app.head("/health")
def health():
    return {"status": "ok"}


@app.post("/decode")
def decode(req: DecodeRequest):
    return decode_iban(req.iban)
