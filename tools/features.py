"""Collect quote-only/GPU/controlled TAP evidence. No funding, payment or refund."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from touchstone.config import ROOT
from touchstone.feature_evidence import refresh_fx, summary
from touchstone.metal import node_executable


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-fx',action='store_true')
    parser.add_argument('--sample-gpu',action='store_true')
    parser.add_argument('--tap-probe',action='store_true')
    parser.add_argument('--controlled-fault-proof',action='store_true')
    parser.add_argument('--controlled-fx',action='store_true')
    args=parser.parse_args();folder=ROOT/'bench/results/features';folder.mkdir(parents=True,exist_ok=True)
    result={'label':'MEASURED','payments_sent':0,'conversions_created':0}
    if args.refresh_fx:
        try:
            from tools.run_project import environment
            from touchstone.treasury import AirwallexSandbox
            environment();fx=refresh_fx(AirwallexSandbox())
            result['fx']={'label':'MEASURED','quote_id':fx['quote']['quote_id'],'current_rate_observed':True,'dispatch_authorized':False}
        except Exception as error:result['fx']={'label':'BLOCKED','error_type':type(error).__name__}
    if args.sample_gpu:
        from touchstone.telemetry import sample
        value=sample();(folder/'telemetry.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        result['gpu']={k:value.get(k) for k in ('label','temperature_c','thermal_throttling_active','pricing_coefficients_status')}
    if args.tap_probe:
        r=subprocess.run([node_executable(),str(ROOT/'integrations/metal/tap-probe.mjs')],capture_output=True,text=True,timeout=20)
        try:
            value=json.loads(r.stdout)
            if r.returncode:raise ValueError('Probe failed')
            (folder/'tap-probe.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
            result['tap']={'label':value['label'],'signature_verified':value['signature_verified'],
                           'replay_http_status':value['replay_http_status'],'visa_approved_agent':False}
        except ValueError:result['tap']={'label':'BLOCKED'}
    if args.controlled_fault_proof:
        import os
        env={k:v for k,v in os.environ.items() if not k.startswith(('AIRWALLEX_','ANTHROPIC_','METAL_')) and k!='AGENT_PRIVATE_KEY'}
        env['TOUCHSTONE_CONTROLLED_FAULT_EVIDENCE']=str(folder/'controlled-credit-acknowledgement.json')
        r=subprocess.run([node_executable(),'--test',str(ROOT/'integrations/metal/fault-proof.test.mjs')],capture_output=True,text=True,timeout=30,env=env)
        result['controlled_fault']={'label':'MOCK','tests_passed':r.returncode==0,'refund_executed':False,'actual_credit_issued':False}
    if args.controlled_fx:
        from touchstone.fx_router import compare
        offer={'provider':'local-gpu','rail':'AIRWALLEX_CARD','price_micro':10000,'currency':'USD',
            'label':'SIMULATED','fx_fee_budget_micro':0,'rail_fee_budget_micro':0,
            'quality_lower_bound':'0.98','latency_ms':100,'qualification_current':True,
            'fees_bounded':True,'funded_fiat_account':True}
        eur={**offer,'provider':'hosted-premium','price_micro':7000,'currency':'EUR','fx_fee_budget_micro':50}
        rate={'label':'MOCK','provider_currency':'EUR','budget_currency':'USD','rate_numerator':115,
            'rate_denominator':100,'quote_id':'controlled-reference','expires_at':200,'application_fees_disclosed':True}
        cases=[compare([offer,eur],[{**rate,'rate_numerator':n,'rate_denominator':d}],
                       now=100,allow_simulated=True) for n,d in [(115,100),(2,1)]]
        if [case['preferred_provider'] for case in cases]!=['hosted-premium','local-gpu']:
            raise ValueError('Controlled FX preference did not change as expected')
        value={'label':'SIMULATED','rate_source':'MOCK','implementation_execution':'MEASURED',
            'cases':cases,'payments_sent':0,'conversions_created':0,
            'note':'Illustrative qualified/funded offers; actual local models remain ineligible.'}
        (folder/'controlled-fx.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
        result['controlled_fx']={'label':'SIMULATED','preference_switch_verified':True}
    print(json.dumps(result,indent=2));return 0


if __name__=='__main__':raise SystemExit(main())
