"""Run-bound simulated billing policy; all actual provider expenses stay recorded."""
POLICIES={'CUSTOMER_PAYS','MERCHANT_ABSORBS'}


def summarize(jobs, attempts, runs, rail_mode):
    results=[]
    for run in runs:
        own_jobs=[j for j in jobs if j['run_id']==run['id']]
        if not own_jobs:
            continue
        ids={j['id'] for j in own_jobs}
        own=[a for a in attempts if a['job_id'] in ids]
        policy=run.get('failed_call_policy','CUSTOMER_PAYS')
        provider=sum(a['price'] for a in own if a['receipt'])
        checks=sum(a['verify_cost'] for a in own if a['passed'] is not None)
        failures=sum(a['price']+a['verify_cost'] for a in own if a['passed']==0)
        captured=sum(j['captured'] for j in own_jobs)
        billable=sum(j['spent'] for j in own_jobs)-(failures if policy=='MERCHANT_ABSORBS' else 0)
        results.append({'run_id':run['id'],'label':'SIMULATED','provider_spend_label':'MEASURED_TESTNET' if rail_mode=='TESTNET' else 'SIMULATED',
                        'failed_call_policy':policy,'customer_captured_micro_usd':captured,
                        'provider_spend_micro_usd':provider,'check_fees_micro_usd':checks,
                        'absorbed_failures_micro_usd':failures if policy=='MERCHANT_ABSORBS' else 0,
                        'billable_completed_work_micro_usd':billable,'uncaptured_billable_micro_usd':billable-captured,
                        'modeled_margin_micro_usd':captured-provider-checks,
                        'check_fees_label':'SIMULATED_INTERNAL_COST','upstream_energy_human_costs_included':False,
                        'refunds_executed':0,'acknowledged_credit_is_not_a_refund':True})
    return {'label':'SIMULATED','by_run':results,'fiat_token_bridge':False}
