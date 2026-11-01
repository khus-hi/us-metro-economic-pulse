"""Keyword dictionary for tagging tools mentioned in job descriptions.

Each tool maps to one regex. Word boundaries stop false hits ("Rexcel" is not
Excel). Single-letter or ambiguous names (R, SAS, Go) are matched
case-sensitively and with extra context so "R&D" or "sas" (as in "SaaS") don't count.
Add or tweak entries here; nothing else needs to change.
"""
import re

TOOLS: dict[str, str] = {
    # languages
    "SQL": r"\bSQL\b|\bT-SQL\b|\bPL/SQL\b",
    "Python": r"\bPython\b",
    "R": r"(?-i:(?<![\w&/-])R(?![\w&/-]))(?=[\s,;)]|$)",
    "SAS": r"(?-i:\bSAS\b)",
    "Scala": r"\bScala\b",
    # spreadsheets / BI
    "Excel": r"\bExcel\b|\bspreadsheets?\b",
    "Google Sheets": r"\bGoogle Sheets\b",
    "Tableau": r"\bTableau\b",
    "Power BI": r"\bPower ?BI\b",
    "Looker": r"\bLooker\b(?! Studio)",
    "Looker Studio": r"\bLooker Studio\b|\bData Studio\b",
    "Qlik": r"\bQlik(?:View| Sense)?\b",
    "Mode": r"(?-i:\bMode Analytics\b)",
    "Sigma": r"(?-i:\bSigma Computing\b)",
    # warehouses / data stack
    "dbt": r"\bdbt\b",
    "Snowflake": r"\bSnowflake\b",
    "BigQuery": r"\bBig ?Query\b",
    "Redshift": r"\bRedshift\b",
    "Databricks": r"\bDatabricks\b",
    "Spark": r"\b(?:Py)?Spark\b",
    "Airflow": r"\bAirflow\b",
    "PostgreSQL": r"\bPostgre(?:SQL|s)\b",
    "MySQL": r"\bMySQL\b",
    # cloud
    "AWS": r"\bAWS\b|\bAmazon Web Services\b",
    "GCP": r"\bGCP\b|\bGoogle Cloud\b",
    "Azure": r"\bAzure\b",
    # analytics / product tools
    "Google Analytics": r"\bGoogle Analytics\b|\bGA4\b",
    "Amplitude": r"\bAmplitude\b",
    "Mixpanel": r"\bMixpanel\b",
    "Salesforce": r"\bSalesforce\b",
    "Alteryx": r"\bAlteryx\b",
    "SPSS": r"\bSPSS\b",
    "Stata": r"\bStata\b",
    "Git": r"\bGit(?:Hub|Lab)?\b",
    "Jira": r"\bJira\b",
    # methods often listed alongside tools
    "A/B testing": r"\bA/B test(?:s|ing)?\b|\bexperimentation\b",
    "Statistics": r"\bstatistic(?:s|al)\b",
    "Machine learning": r"\bmachine learning\b|\bML\b",
}

_COMPILED = {name: re.compile(p, re.IGNORECASE) for name, p in TOOLS.items()}


def tag_tools(text: str) -> list[str]:
    if not text:
        return []
    return [name for name, rx in _COMPILED.items() if rx.search(text)]
