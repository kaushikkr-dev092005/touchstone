import copy
import unittest
from touchstone.fx_router import compare, rate_observation, rebalance_plan


class FxRouterTests(unittest.TestCase):
    def setUp(self):
        self.rate={'provider_currency':'EUR','budget_currency':'USD','rate_numerator':115,'rate_denominator':100,
                   'expires_at':200,'quote_id':'q','label':'MOCK','application_fees_disclosed':True}
        self.offer={'provider':'local-gpu','rail':'AIRWALLEX_CARD','price_micro':10000,'currency':'USD','label':'SIMULATED',
                    'fx_fee_budget_micro':0,'rail_fee_budget_micro':0,'quality_lower_bound':'0.98','latency_ms':100,
                    'qualification_current':True,'fees_bounded':True,'funded_fiat_account':True}

    def test_fx_changes_preference_with_explicit_fees_and_quality(self):
        eur={**self.offer,'provider':'hosted-premium','price_micro':7000,'currency':'EUR','fx_fee_budget_micro':50}
        result=compare([self.offer,eur],[self.rate],now=100,allow_simulated=True)
        self.assertEqual(result['preferred_provider'],'hosted-premium')
        self.assertEqual(result['offers'][1]['effective_cost_micro'],8100)
        expensive={**self.rate,'rate_numerator':2,'rate_denominator':1}
        self.assertEqual(compare([self.offer,eur],[expensive],now=100,allow_simulated=True)['preferred_provider'],'local-gpu')
        self.assertFalse(result['dispatch_authorized'])

    def test_rounds_costs_up_and_never_treats_tokens_as_fiat(self):
        eur={**self.offer,'price_micro':1,'currency':'EUR'}
        self.assertEqual(compare([eur],[self.rate],now=100,allow_simulated=True)['offers'][0]['converted_cost_micro'],2)
        metal={**self.offer,'rail':'METAL_TESTNET','currency':'USDZ'}
        self.assertIsNone(compare([metal],[],now=100,allow_simulated=True)['preferred_provider'])
        with self.assertRaises(ValueError):compare([{**metal,'currency':'EUR'}],[])

    def test_stale_fx_unqualified_models_unknown_fees_and_simulated_offers_are_refused(self):
        for changes in [{'qualification_current':False},{'fees_bounded':False},{'quality_lower_bound':'0.5'}, {'funded_fiat_account':False}]:
            self.assertIsNone(compare([{**self.offer,**changes}],[],now=100,allow_simulated=True)['preferred_provider'])
        self.assertIsNone(compare([self.offer],[],now=100)['preferred_provider'])
        eur={**self.offer,'currency':'EUR'}
        self.assertEqual(compare([eur],[self.rate],now=201)['offers'][0]['reason'],'FX_QUOTE_MISSING_OR_EXPIRED')
        hidden_fees={**self.rate,'application_fees_disclosed':False}
        self.assertEqual(compare([eur],[hidden_fees],now=100,allow_simulated=True)['offers'][0]['reason'],'FX_FEES_NOT_DISCLOSED')

    def test_explicit_quote_orientation_and_no_conversion(self):
        quote={'sell_currency':'USD','buy_currency':'EUR','currency_pair':'EURUSD','client_rate':'1.15',
               'quote_id':'q','valid_to_at':'2030-01-01T00:00:00+00:00','application_fees':[]}
        r=rate_observation(quote,now=100)
        self.assertEqual((r['rate_numerator'],r['rate_denominator']),(23,20))
        quote.update(currency_pair='USDEUR',client_rate='0.8')
        r=rate_observation(quote,now=100)
        self.assertEqual((r['rate_numerator'],r['rate_denominator']),(5,4))
        quote.pop('currency_pair')
        with self.assertRaises(ValueError):rate_observation(quote,now=100)
        self.assertFalse(rebalance_plan(deficit_micro=100,threshold_micro=200,planned_sell_usd_micro=999999,quote_expires_at=200,now=100)['threshold_met'])
