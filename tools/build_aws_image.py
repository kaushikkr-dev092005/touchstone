"""Build a committed ARM64 image locally. Never publishes or calls AWS."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent.parent


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ref',default='HEAD')
    args=parser.parse_args()
    revision=subprocess.check_output(['git','rev-parse','--verify','--end-of-options',args.ref+'^{commit}'],cwd=ROOT,text=True).strip()
    if not re.fullmatch('[a-f0-9]{40}',revision):raise ValueError('COMMITTED_SOURCE_REQUIRED')
    environment={k:v for k,v in os.environ.items() if not k.startswith(('AWS_','AIRWALLEX_','METAL_','ANTHROPIC_','CLAUDE_')) and k!='AGENT_PRIVATE_KEY'}
    # A git archive excludes ignored wallets, .env files, local data, and Git credentials.
    with tempfile.TemporaryFile() as context:
        subprocess.run(['git','archive','--format=tar',revision],cwd=ROOT,stdout=context,check=True)
        context.seek(0)
        subprocess.run(['docker','buildx','build','--platform','linux/arm64','--load',
            '--file','deploy/operator/Dockerfile','--build-arg','SOURCE_REVISION='+revision,
            '--tag','touchstone-aws-local:'+revision,'-'],cwd=ROOT,env=environment,stdin=context,check=True)
    subprocess.run(['docker','image','inspect','--format',
        '{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{.Id}}',
        'touchstone-aws-local:'+revision],check=True)
    print('LOCAL BUILD ONLY. Image ID is not a published registry manifest digest. No AWS resources created.')


if __name__=='__main__':main()
