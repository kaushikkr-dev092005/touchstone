"""One-command offline mock dashboard; never loads local credentials or wallets."""
import argparse
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8088)
    parser.add_argument('--data-dir',default='data/mock-dashboard')
    args=parser.parse_args()
    if not 1024<=args.port<=65535:parser.error('Use a port from 1024 to 65535')
    os.environ['TOUCHSTONE_IGNORE_LOCAL_CONFIG']='1'
    for key in list(os.environ):
        if key.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_')) or key=='AGENT_PRIVATE_KEY':os.environ.pop(key)
    from touchstone.server import serve
    serve(args.port,args.data_dir)


if __name__=='__main__':main()
