#!/usr/bin/env python3
"""Load non-secret instance settings; never infer a personal Git identity."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
LOCAL_CONFIG = ROOT / '.greenhouse.local.json'
LOGIN = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\Z')
REPO = re.compile(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?/[A-Za-z0-9_.-]{1,100}\Z')
NOREPLY = re.compile(r'(?:[0-9]+\+)?([A-Za-z0-9-]+)@users\.noreply\.github\.com\Z', re.I)
FIELDS = {'version','timezone','start_date','author_name','author_email','repository','reviewer','review_enabled'}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate configuration key')
        result[key] = value
    return result


@dataclass(frozen=True)
class Settings:
    timezone: str = 'UTC'
    start_date: date | None = None
    author_name: str = ''
    author_email: str = ''
    repository: str = ''
    reviewer: str = ''
    review_enabled: bool = False
    configured: bool = False

    @property
    def zone(self):
        return ZoneInfo(self.timezone)

    def to_dict(self):
        return {'version':1, 'timezone':self.timezone,
                'start_date':self.start_date.isoformat() if self.start_date else None,
                'author_name':self.author_name, 'author_email':self.author_email,
                'repository':self.repository, 'reviewer':self.reviewer,
                'review_enabled':self.review_enabled}


def parse_config(raw):
    if not isinstance(raw, str) or len(raw.encode('utf-8')) > 16384:
        raise ValueError('Configuration is missing or too large')
    try:
        data = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        raise ValueError('Invalid configuration JSON') from None
    if not isinstance(data,dict) or set(data)-FIELDS:
        raise ValueError('Unknown configuration fields; never put credentials in configuration')
    if data.get('version',1) != 1 or type(data.get('version',1)) is not int:
        raise ValueError('Unsupported configuration version')
    zone = data.get('timezone','UTC')
    if not isinstance(zone,str) or not zone or len(zone)>100:
        raise ValueError('Invalid timezone')
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError('Unknown timezone; use an IANA timezone name') from None
    day = data.get('start_date')
    if day is not None:
        if not isinstance(day,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',day):
            raise ValueError('Start date must be an explicit YYYY-MM-DD date')
        try:
            parsed = date.fromisoformat(day)
        except ValueError:
            raise ValueError('Invalid start date') from None
        if parsed.isoformat()!=day:raise ValueError('Invalid start date')
        day=parsed
    values={}
    for key in ('author_name','author_email','repository','reviewer'):
        value=data.get(key,'')
        if not isinstance(value,str) or len(value)>200 or any(ord(c)<32 for c in value):
            raise ValueError('Invalid identity or repository setting')
        values[key]=value
    enabled=data.get('review_enabled',False)
    if type(enabled) is not bool:raise ValueError('review_enabled must be a boolean')
    return Settings(timezone=zone,start_date=day,review_enabled=enabled,configured=True,**values)


def load_config():
    raw=os.environ.get('GREENHOUSE_CONFIG_JSON')
    if raw:
        return parse_config(raw)
    location=Path(os.environ.get('GREENHOUSE_CONFIG_FILE',str(LOCAL_CONFIG)))
    if location.is_file():
        if location.stat().st_size>16384:raise ValueError('Configuration is too large')
        return parse_config(location.read_text(encoding='utf-8'))
    return Settings()


def require_automation(settings):
    if not settings.configured or settings.start_date is None:
        raise ValueError('Configure your own instance with scripts/setup.py first')
    if not REPO.fullmatch(settings.repository) or settings.repository.split('/')[1] in {'.','..'}:
        raise ValueError('Configure an explicit OWNER/REPOSITORY target')
    if not LOGIN.fullmatch(settings.author_name):
        raise ValueError('Use your GitHub login as author_name')
    match=NOREPLY.fullmatch(settings.author_email)
    if not match or match[1].lower()!=settings.author_name.lower():
        raise ValueError('Use the author account GitHub noreply email; real email addresses are refused')
    if settings.review_enabled and not LOGIN.fullmatch(settings.reviewer):
        raise ValueError('Configure a GitHub user login for the optional reviewer')
    if settings.start_date>datetime.now(settings.zone).date():
        raise ValueError('The configured start date cannot be in the future')
    target=os.environ.get('GITHUB_REPOSITORY')
    if target and target.lower()!=settings.repository.lower():
        raise ValueError('The running repository does not match the configured instance')
