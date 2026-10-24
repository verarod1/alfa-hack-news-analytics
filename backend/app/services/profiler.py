import pandas as pd
import os
from typing import Dict, Any

DATA_PATH = "data/raw/df_Uid_data_hack.csv"

try:
    if os.path.exists(DATA_PATH):
        df_companies = pd.read_csv(DATA_PATH)
    else:
        df_companies = None
        print(f" Файл {DATA_PATH} не найден. Проверь путь.")
except Exception as e:
    df_companies = None
    print(f" Ошибка при чтении CSV: {e}")

def safe_bool(val) -> bool | None:
    """Превращает 1.0/0.0/NaN из pandas в True/False/None"""
    if pd.isna(val):
        return None
    return bool(val)

def build_company_profile(company_id: str) -> Dict[str, Any]:
    """Собирает профиль компании по её ID из CSV."""
    if df_companies is None:
        raise ValueError("Данные не загружены")

    # Ищем компанию по SYNTHETIC_U
    row = df_companies[df_companies['SYNTHETIC_U'] == company_id]
    
    if row.empty:
        raise ValueError(f"Компания {company_id} не найдена")

    row = row.iloc[0] # Берем первую совпавшую строку

    # Собираем JSON строго по контракту Кати
    profile = {
        "id": str(row['SYNTHETIC_U']),
        "company_name": f"Компания {row['SYNTHETIC_U']}", # Условное название
        "industry": {
            "code": str(row.get('MAINOKVED_CODE', '')),
            "name": str(row.get('MAINOKVED_NAME', ''))
        },
        "region": str(row.get('REGION', '')),
        "city": str(row.get('CITY', '')),
        "age_range": str(row.get('COMPANY_AGE_YEARS_GRADATION', '')),
        "employees_range": str(row.get('AMOUNT_WORKERS_FNS_GRADATION', '')),
        "business_stage": str(row.get('ECO_MARK_LABEL', '')) if pd.notna(row.get('ECO_MARK_LABEL')) else None,
        "client_type": str(row.get('CL_TYPE', '')),
        "revenue": {
            "value": float(row['REVENUE_COMPANY']) if pd.notna(row.get('REVENUE_COMPANY')) else None,
            "unit": "unconfirmed"
        },
        "foreign_trade": {
            "has_data": safe_bool(row.get('FTS_FLAG')) or False,
            "countries": [str(row['FTS_COUNTRY_NAME'])] if pd.notna(row.get('FTS_COUNTRY_NAME')) else []
        },
        "bank_products": {
            "rko": safe_bool(row.get('CL_PRODUCT_RKO_MARK')),
            "guarantee": safe_bool(row.get('CL_PRODUCT_GAR_MARK')),
            "loan": safe_bool(row.get('CL_PRODUCT_LOA_MARK')),
            "leasing": safe_bool(row.get('CL_PRODUCT_LEA_MARK')),
            "deposit": safe_bool(row.get('CL_PRODUCT_DEP_MARK')),
            "payroll": safe_bool(row.get('CL_PRODUCT_ZPP_MARK')),
            "factoring": safe_bool(row.get('FACTORING_MARK'))
        },
        "group_id": str(row.get('GROUP_ID', '')) if pd.notna(row.get('GROUP_ID')) else None,
        "organization_type": str(row.get('ORG_TYPE', '')) if pd.notna(row.get('ORG_TYPE')) else None,
        "ownership_form": str(row.get('OKFS_NAME', '')) if pd.notna(row.get('OKFS_NAME')) else None,
        "key_owner_flag": None, # По контракту смысл не определен, ставим null
        "employees_spark_range": str(row.get('AMOUNT_WORKERS_SPARK_GRADATION', '')) if pd.notna(row.get('AMOUNT_WORKERS_SPARK_GRADATION')) else None
    }
    
    return profile


if __name__ == "__main__":
    import json
    # Замени 'U_67' на любой реальный ID из твоего CSV
    test_id = "U_67"
    try:
        result = build_company_profile(test_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"Ошибка: {e}")