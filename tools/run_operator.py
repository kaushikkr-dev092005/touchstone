"""Initialize or run the authenticated zero-charge workspace; no financial operations."""
import argparse
import getpass
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['init','serve'])
    parser.add_argument('--config',default='data/private/operator-config.json')
    parser.add_argument('--data-dir',default='data/operator')
    parser.add_argument('--origin',default='http://127.0.0.1:8089')
    parser.add_argument('--username',default='operator')
    parser.add_argument('--environment',choices=['DEMO','SANDBOX','TESTNET'],default='DEMO')
    parser.add_argument('--bind',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=8089)
    args=parser.parse_args()
    path=Path(args.config)
    if args.action=='init':
        from touchstone.operator_auth import make_config
        if path.exists():raise ValueError('Existing configuration is not overwritten; rotate deliberately offline')
        password=getpass.getpass('New operator password (16+ characters): ')
        if password!=getpass.getpass('Repeat password: '):raise ValueError('Passwords do not match')
        config=make_config(args.origin,args.username,password,args.environment)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.parent.chmod(0o700)
        with path.open('x',encoding='utf-8') as file:json.dump(config,file,indent=2)
        path.chmod(0o600)
        print('Operator configured. No financial key or spending authority was created.')
        return
    if not 1024<=args.port<=65535:raise ValueError('Use port 1024 to 65535')
    import os
    for name in list(os.environ):
        if name.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_')) or name=='AGENT_PRIVATE_KEY':os.environ.pop(name)
    os.environ['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
    from touchstone.operator_server import make_server
    from touchstone.leases import exclusive
    with exclusive(Path(args.data_dir)/'operator-owner.sqlite'):
        server=make_server(path,args.data_dir,bind=args.bind,port=args.port)
        print('Authenticated workspace started; financial dispatch is disabled.',flush=True)
        try:server.serve_forever()
        finally:server.server_close()


if __name__=='__main__':main()
