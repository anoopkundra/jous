"""Separately gated disposable PostgreSQL read-only validator. Never applies DDL."""
import argparse
import asyncio
import os
from urllib.parse import urlsplit


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorized-disposable-validation',action='store_true')
    args=parser.parse_args()
    if not args.authorized_disposable_validation or os.environ.get('JOUS_V12_DISPOSABLE_AUTHORIZED')!='YES':
        raise SystemExit('Separate disposable PostgreSQL authorization required')
    raw=os.environ.get('JOUS_V12_DISPOSABLE_RUNTIME_URL','')
    parsed=urlsplit(raw)
    if parsed.hostname not in ('localhost','127.0.0.1') or not parsed.path.startswith('/jous_v12_disposable_'):
        raise SystemExit('Dedicated loopback disposable database required')
    from jous_api.config import Settings
    from jous_api.database import Database
    from jous_api.product_runtime_validation import validate_product_runtime
    from pydantic import SecretStr
    database=Database(Settings(environment='test',database_url=SecretStr(raw)),validator=validate_product_runtime)
    try:
        await database.check()
        print('Disposable catalog validation passed; no DDL applied')
    finally:await database.dispose()


if __name__=='__main__':asyncio.run(main())
