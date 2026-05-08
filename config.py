"""Loads private operational config from .sector_config.json (gitignored).

In the cloud, this file is reconstructed from the SECTOR_CONFIG_JSON secret at
workflow runtime. Locally, it lives on disk with chmod 600. It must NEVER be
committed — it carries identifying metadata (emails, names, board ID, doc ID)
and the business context block used in LLM prompts.
"""
import json
from pathlib import Path

_PATH = Path(__file__).parent / ".sector_config.json"
_data = json.loads(_PATH.read_text())

sender_email       = _data["sender_email"]
recipient_email    = _data["recipient_email"]
user_first_name    = _data["user_first_name"]
user_full_name     = _data["user_full_name"]
agent_name         = _data["agent_name"]
org_name           = _data["org_name"]
figma_file_key     = _data["figma_file_key"]
doc_title          = _data["doc_title"]
doc_subtitle       = _data["doc_subtitle"]
business_context   = _data["business_context"]
inference_rules    = _data["inference_rules"]
action_log_doc_id  = _data.get("action_log_doc_id")  # None on first run; gets created
processed_label_id = _data.get("processed_label_id")  # None on first run; gets created
airtable_base_id   = _data.get("airtable_base_id")
airtable_tables    = _data.get("airtable_tables", {})  # {table_name: table_id}
