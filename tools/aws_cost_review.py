"""Offline Mumbai cost arithmetic; never authenticates, discounts credits or deploys."""
import json
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent


def nonnegative(value):
    if isinstance(value,bool):raise ValueError('INVALID_COST_INPUT')
    amount=Decimal(str(value))
    if not amount.is_finite() or amount<0:raise ValueError('INVALID_COST_INPUT')
    return amount


def estimate(pricing, instance_type, *, compute_hours=744, ipv4_hours=744,
             other_account_projected_gross_usd=None):
    """31-day bound; both encrypted disks and an allocated IP bill while stopped.

    Tax and variable reserves are planning assumptions, not measured account tax
    or a network spending limiter. Credits never reduce the gross-usage estimate.
    """
    hours=nonnegative(compute_hours);ip_hours=nonnegative(ipv4_hours)
    if hours>744 or ip_hours>744:raise ValueError('UNREVIEWED_MONTHLY_HOURS')
    compute=nonnegative(pricing['ec2'][instance_type]['usd_per_hour'])*hours
    ip=nonnegative(pricing['public_ipv4']['usd_per_hour'])*ip_hours
    storage=nonnegative(pricing['gp3']['usd_per_gb_month'])*16
    fixed=compute+ip+storage
    tax=fixed*nonnegative(pricing['planning']['tax_reserve_fraction'])
    variable=nonnegative(pricing['planning']['other_usage_reserve_usd'])
    total=fixed+tax+variable
    other=None if other_account_projected_gross_usd is None else nonnegative(other_account_projected_gross_usd)
    account_total=None if other is None else total+other
    return {'instance_type':instance_type,'compute_hours':str(hours),'allocated_ipv4_hours':str(ip_hours),
        'compute_usd':str(compute),'ipv4_usd':str(ip),'storage_usd':str(storage),
        'fixed_subtotal_usd':str(fixed),'tax_planning_reserve_usd':str(tax),
        'other_usage_planning_reserve_usd':str(variable),'planning_total_usd':str(total),
        'fits_ceiling_before_other_account_usage':total<=Decimal('10'),
        'other_account_projected_gross_usd':None if other is None else str(other),
        'projected_account_gross_usd':None if account_total is None else str(account_total),
        'account_gross_estimate_fits_ceiling':None if account_total is None else account_total<=Decimal('10'),
        'credit_discount_assumed_usd':'0.00','out_of_pocket_target_verified':False,
        'provisioning_authorized':False}


def main():
    pricing=json.loads((ROOT/'deploy/aws/pricing.json').read_text())
    cases={'micro_always_on':estimate(pricing,'t4g.micro'),
           'nano_always_on':estimate(pricing,'t4g.nano'),
           'micro_360_hours':estimate(pricing,'t4g.micro',compute_hours=360),
           'micro_ipv6_only_research':estimate(pricing,'t4g.micro',ipv4_hours=0)}
    print(json.dumps({'evidence':'OFFLINE_PLANNING_ONLY','pricing_date':pricing['verified_date'],
        'account_eligibility_verified':False,'monthly_gross_ceiling_usd':'10.00',
        'out_of_pocket_target_usd':'0.00','alternatives':cases},indent=2))


if __name__=='__main__':main()
