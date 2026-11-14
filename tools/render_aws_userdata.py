"""Embed the reviewed local guard before bootstrap networking; no cloud calls."""
import argparse
import base64
import json
from pathlib import Path
import zlib

ROOT=Path(__file__).resolve().parent.parent


def render():
    code=(ROOT/'tools/aws_runtime_guard.py').read_bytes().replace(b'\r\n',b'\n')
    payload=base64.b64encode(zlib.compress(code,9)).decode('ascii')
    script=(ROOT/'deploy/aws/bootstrap.sh').read_text(encoding='utf-8').replace('@GUARD_PAYLOAD@',payload)
    if len(script.encode())>16384:raise ValueError('EC2_USER_DATA_TOO_LARGE')
    return script


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
    args=parser.parse_args();path=ROOT/'deploy/aws/cloudformation.json'
    template=json.loads(path.read_text(encoding='utf-8'));script=render()
    if args.check:
        if template['Resources']['Instance']['Properties']['UserData']!={'Fn::Base64':{'Fn::Sub':script}}:
            raise SystemExit('AWS_USER_DATA_STALE: run python tools/render_aws_userdata.py')
        print('AWS_USER_DATA_CURRENT');return
    template['Resources']['Instance']['Properties']['UserData']={'Fn::Base64':{'Fn::Sub':script}}
    serialized=json.dumps(template,indent=2)+'\n'
    if len(serialized.encode())>51200:raise ValueError('CFN_INLINE_TEMPLATE_TOO_LARGE')
    path.write_text(serialized,encoding='utf-8',newline='\n')


if __name__=='__main__':main()
